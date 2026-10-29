"""上传注册与增量判定（M-S2-T05）。

选型说明：独立 services/upload.py（非塞进 version.py）——version.py 是
纯版本状态域（create/activate/mark_failed），本模块是跨域编排
（比对 + MinIO 存储 + Celery 派发），职责分离。

流程 register_upload(session, user_id, workspace_id, document_id,
filename, data)：
1. 成员判定（细则 1/3，KN-404 模式与 document.py 一致）；
2. 文档存在性（ws+doc 双 WHERE，KN-404 不泄露跨区存在性）；
3. sha256 全文指纹 vs **当前 active 版本** content_hash（任务书已定：
   与 active 比对；无 active 版本视为变更）；
4. 未变 → 返回 unchanged，**零写入**（版本行/MinIO/chunks 三者都不动，
   S2-AC-3）；
5. 变更 → put_object（version_no 预查 max+1，与 create_new_version 内部
   分配一致；dev 单 worker 下竞态窗口可接受，注释在案）→
   create_new_version（staging）→ 派发 ingest_version（返回 task id
   供前端跟踪）。

chunk 级去重（S2-AC-3 关联）落在 ingestion.py 组装处：**仅限单版本内**
（跨版本复用 chunk 行会破坏"检索按 version 状态过滤"模型，O-2）。
"""

import hashlib
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import Document, DocumentVersion, WorkspaceMember
from app.services import storage
from app.services import version as version_svc
from app.workers.ingestion import ingest_version

log = logging.getLogger("app.services.upload")


def _require_member(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")


def register_upload(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> dict:
    """增量上传入口：未变零写入，变更走完整摄取链。"""
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    doc = session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_id == document_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise AppError("KN-404")

    digest = hashlib.sha256(data).hexdigest()

    active = None
    if doc.active_version is not None:
        active = session.get(DocumentVersion, doc.active_version)

    if active is not None and active.content_hash == digest:
        log.info(
            "upload unchanged document=%s active_version_no=%s",
            document_id, active.version_no,
        )
        return {
            "status": "unchanged",
            "message": "内容未变，未创建新版本",
            "active_version_id": str(active.version_id),
            "active_version_no": active.version_no,
        }

    # 变更：vno 预查（与 create_new_version 的 max+1 分配保持一致）
    current_max = session.execute(
        select(func.max(DocumentVersion.version_no)).where(
            DocumentVersion.document_id == document_id
        )
    ).scalar() or 0
    vno = current_max + 1
    object_key = storage.put_object(
        workspace_id, document_id, vno, data, filename
    )
    version = version_svc.create_new_version(
        session,
        user_id=user_id, workspace_id=workspace_id,
        document_id=document_id,
        content_hash=digest, file_path=object_key,
    )
    task = ingest_version.delay(str(version.version_id))
    log.info(
        "upload accepted document=%s new_version_no=%s task=%s",
        document_id, version.version_no, task.id,
    )
    return {
        "status": "accepted",
        "version_id": str(version.version_id),
        "version_no": version.version_no,
        "task_id": task.id,  # 供前端经状态端点跟踪
    }
