"""上传 API（M-S2-T06，S2 收尾）：POST /api/v1/workspaces/{ws}/documents。

- multipart/form-data：file 必填 + document_id 可选；
- 身份：JWT 认证（M-S5-T02 起）——Authorization: Bearer →
  get_current_user_id 依赖注入，过渡身份头已退役（即使传入也不读取，
  身份唯一来源是 Bearer token）；
  成员判定在 service 层（create_document/register_upload 内
  _require_member，身份源变化判定逻辑零变化）；
- 表单语义（任务书规则）：带 document_id → 向既有文档追加版本（增量判定）；
  不带 → 先 create_document（filename 作文档名）再 register_upload；
- 早期快速失败（不写 MinIO 不派任务）：扩展名白名单（parser 支持集：
  pdf/docx/md/txt）→ KN-422；大小超 MAX_UPLOAD_MB → KN-400（12 码表中
  无专用"文件过大"码，取通用请求无效语义，未发明新码）；
- 竞态修复配套：register_upload 落库返回后（事务已提交）才 .delay()；
- 响应统一 {code, message, data}：unchanged / accepted（version_id、
  version_no、task_id）两种 data，立即返回不阻塞（S2-AC-1）；
- API 不解析文件内容（解析在 worker 异步）。
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.models.models import Document, DocumentVersion, WorkspaceMember
from app.services import document as doc_svc
from app.services.upload import register_upload
from app.workers.ingestion import ingest_version

log = logging.getLogger("app.api.documents")
router = APIRouter(prefix="/api/v1", tags=["documents"])

# 与 app/services/parser.py 支持集一致（含 txt 直读）
ALLOWED_EXTS = {".pdf", ".docx", ".md", ".txt"}


@router.post("/workspaces/{workspace_id}/documents")
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    document_id: uuid.UUID | None = Form(None),
    user_id: uuid.UUID = Depends(get_current_user_id),  # M-S5-T02：JWT 依赖注入
):
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    # 早期快速失败（不碰 MinIO / 不建版本 / 不派任务）
    if ext not in ALLOWED_EXTS:
        raise AppError("KN-422")
    data = await file.read()
    if len(data) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("KN-400")  # 错误码表无"文件过大"专用码，取通用请求无效

    with get_session() as session:
        if document_id is None:
            doc = doc_svc.create_document(
                session, user_id=user_id, workspace_id=workspace_id, filename=filename
            )
            document_id = doc.document_id
        result = register_upload(
            session, user_id=user_id, workspace_id=workspace_id,
            document_id=document_id, filename=filename, data=data,
        )
    # 事务已提交（get_session 正常退出即 commit）——此刻派发才安全
    if result["status"] == "accepted":
        task = ingest_version.delay(result["version_id"])
        result["task_id"] = task.id
    # T06 事件③复核修复：补 document_id（00 契约未细定义 data 字段，
    # 属向后兼容增强——客户端需凭它追加版本/查状态，缺它链路断）
    result["document_id"] = str(document_id)
    log.info("upload api done document=%s status=%s", document_id, result["status"])
    return {"code": "KN-000", "message": "ok", "data": result}


@router.get("/workspaces/{workspace_id}/documents")
def list_documents(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """工作区文档列表（只读，前端 P4 联调新增）。

    - 成员判定与隔离口径同 status.py：非成员一律 KN-404（不泄露存在性）；
    - 每文档返回最新版本状态（staging/active/retired/failed）+ 是否有激活
      版本；演示规模文档量小，两步查询（documents → versions）在 Python
      侧按 version_no 取最新，不引入窗口函数；
    - 只读，不触碰 MinIO 与 worker。
    """
    with get_session() as session:
        _require_member(session, user_id=user_id, workspace_id=workspace_id)
        docs = (
            session.execute(
                select(Document)
                .where(Document.workspace_id == workspace_id)
                .order_by(Document.created_at.desc(), Document.document_id)
            )
            .scalars()
            .all()
        )
        latest: dict[uuid.UUID, DocumentVersion] = {}
        if docs:
            rows = session.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id.in_([d.document_id for d in docs])
                )
            ).scalars()
            for v in rows:
                cur = latest.get(v.document_id)
                if cur is None or v.version_no > cur.version_no:
                    latest[v.document_id] = v
        data = [
            {
                "document_id": str(d.document_id),
                "filename": d.filename,
                "created_at": d.created_at.isoformat(),
                "active_version": str(d.active_version) if d.active_version else None,
                "version_no": latest[d.document_id].version_no,
                "status": latest[d.document_id].status,
            }
            for d in docs
            if d.document_id in latest
        ]
        log.info("documents listed workspace=%s count=%d", workspace_id, len(data))
        return {"code": "KN-000", "message": "ok", "data": data}


def _require_member(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """成员判定（同 status.py 口径：非成员 KN-404，不泄露存在性）。"""
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")
