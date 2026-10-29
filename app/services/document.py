"""document 增/查/删 service（M-S1-T02）。

- 每个方法强制 workspace_id 参数并直接进 SQL WHERE（P-S1 硬性约束：
  禁止先查全表再内存过滤）；
- 资源不存在或调用者非该 workspace 成员一律 KN-404（不泄露跨区存在性，
  细则 1 / KN-404 语义）；
- 不触碰 document_versions 的写入（版本逻辑属 S1-T03；删除前的存在性
  计数为只读）；
- 删除为阻断式（有版本时 KN-409，本轮已确认）；list 不分页。
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import Document, DocumentVersion, WorkspaceMember

log = logging.getLogger("app.services.document")


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


def create_document(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID, filename: str
) -> Document:
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    doc = Document(workspace_id=workspace_id, filename=filename)
    session.add(doc)
    session.flush()
    log.info("document created id=%s in workspace=%s", doc.document_id, workspace_id)
    return doc


def get_document(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    doc = session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_id == document_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise AppError("KN-404")
    return doc


def list_documents(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> list[Document]:
    """返回该 workspace 全部文档（S1 不分页，已确认）。"""
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    return list(
        session.execute(
            select(Document).where(Document.workspace_id == workspace_id)
        ).scalars()
    )


def delete_document(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """阻断式删除：文档仍有版本时 KN-409（本轮已确认）。"""
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    doc = session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_id == document_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise AppError("KN-404")
    version_count = session.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
    ).scalar_one()
    if version_count:
        raise AppError("KN-409", "文档仍有版本，禁止删除（阻断式）")
    session.delete(doc)
    log.info("document deleted id=%s in workspace=%s", document_id, workspace_id)
