"""上传 API（M-S2-T06，S2 收尾）：POST /api/v1/workspaces/{ws}/documents。

- multipart/form-data：file 必填 + document_id 可选；
- 身份：X-User-ID 请求头（O-7 dev 过渡，S5 换 JWT——全局唯一替换点）；
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

from fastapi import APIRouter, File, Form, Header, UploadFile

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.services import document as doc_svc
from app.services.upload import register_upload
from app.workers.ingestion import ingest_version

log = logging.getLogger("app.api.documents")
router = APIRouter(prefix="/api/v1", tags=["documents"])

# 与 app/services/parser.py 支持集一致（含 txt 直读）
ALLOWED_EXTS = {".pdf", ".docx", ".md", ".txt"}


def _parse_user_id(x_user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(x_user_id)
    except (ValueError, AttributeError, TypeError):
        raise AppError("KN-400")


@router.post("/workspaces/{workspace_id}/documents")
async def upload_document(
    workspace_id: uuid.UUID,
    x_user_id: str = Header(...),
    file: UploadFile = File(...),
    document_id: uuid.UUID | None = Form(None),
):
    user_id = _parse_user_id(x_user_id)
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
    log.info("upload api done document=%s status=%s", document_id, result["status"])
    return {"code": "KN-000", "message": "ok", "data": result}
