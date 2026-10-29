"""版本不可变约束与激活指针 service（M-S1-T03）。

核心不变量（00 第四节 / D-1）：
- 版本行一经写入，version_no / content_hash / file_path 永不修改，行永不删除；
- 唯一可变的是版本 status 流转（staging→active→retired / staging→failed，
  单向；已确认仅 staging 可激活）与 documents.active_version 指针；
- 本模块不定义任何修改版本内容或删除版本行的通用方法，status 流转只经
  三个显式入口：create_new_version / activate_version / mark_version_failed
  （S1-AC-2 代码级佐证：全文件无 session.delete / delete() / update() 调用）。

约定：
- 身份参数传入（O-7）；成员判定沿用 T02 的 _require_member 模式（细则 3）；
- 文档归属一律以 workspace_id + document_id 进 SQL WHERE（细则 1，KN-404）；
- version_no 递增：先 SELECT ... FOR UPDATE 锁 documents 行（同文档版本
  创建串行化，本轮已确认；不改表结构）；
- 指针切换与状态变更由调用方经同一 Session 在同一事务内完成。
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import Document, DocumentVersion, WorkspaceMember

log = logging.getLogger("app.services.version")


def _require_member(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """成员判定（T02 模式沿用；非成员 KN-404，不泄露存在性）。"""
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")


def _get_document(
    session: Session, *, workspace_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    """文档归属过滤（细则 1），不存在 KN-404。"""
    doc = session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_id == document_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise AppError("KN-404")
    return doc


def create_new_version(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID,
    document_id: uuid.UUID, content_hash: str, file_path: str,
) -> DocumentVersion:
    """同文档上传新文件：version_no = 当前最大值 + 1，插入 staging 新行。

    旧行原样保留不动（不可变）；file_path 本阶段为字符串 object key 占位，
    S2 才真实上传 MinIO。FOR UPDATE 锁文档行保证同文档并发递增安全。
    """
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    # FOR UPDATE：锁定文档行，串行化同文档的版本号分配（本轮已确认）
    doc = session.execute(
        select(Document)
        .where(
            Document.workspace_id == workspace_id,
            Document.document_id == document_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if doc is None:
        raise AppError("KN-404")
    current_max = session.execute(
        select(DocumentVersion.version_no)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    version = DocumentVersion(
        workspace_id=workspace_id,
        document_id=document_id,
        version_no=(current_max or 0) + 1,
        content_hash=content_hash,
        file_path=file_path,
        status="staging",
    )
    session.add(version)
    session.flush()
    log.info(
        "version created id=%s document=%s version_no=%d",
        version.version_id, document_id, version.version_no,
    )
    return version


def _get_version_in_document(
    session: Session, *, document_id: uuid.UUID, version_id: uuid.UUID
) -> DocumentVersion:
    """版本必须属于指定文档，否则 KN-404（不泄露存在性）。"""
    version = session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_id == version_id,
        )
    ).scalar_one_or_none()
    if version is None:
        raise AppError("KN-404")
    return version


def activate_version(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID,
    document_id: uuid.UUID, version_id: uuid.UUID,
) -> DocumentVersion:
    """将 staging 版本置为 active 并切换 documents.active_version 指针。

    同一事务内完成：旧 active 版本（若有）置 retired，指针切到目标版本。
    非 staging 版本激活 → KN-409（单向流转，本轮已确认）。
    """
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    doc = _get_document(session, workspace_id=workspace_id, document_id=document_id)
    version = _get_version_in_document(
        session, document_id=document_id, version_id=version_id
    )
    if version.status != "staging":
        raise AppError(
            "KN-409", f"版本状态为 {version.status}，仅 staging 可激活（单向流转）"
        )
    # 旧 active 版本置 retired（唯一允许的 status 流转路径之一）
    if doc.active_version is not None:
        old_active = _get_version_in_document(
            session, document_id=document_id, version_id=doc.active_version
        )
        old_active.status = "retired"
        log.info(
            "version retired id=%s document=%s", old_active.version_id, document_id
        )
    # 指针切换：documents.active_version 是该表唯一可变字段（00 第四节）
    doc.active_version = version.version_id
    version.status = "active"
    session.flush()
    log.info(
        "version activated id=%s document=%s version_no=%d",
        version.version_id, document_id, version.version_no,
    )
    return version


def mark_version_failed(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID,
    document_id: uuid.UUID, version_id: uuid.UUID,
) -> DocumentVersion:
    """将 staging 版本置为 failed（D-1 四态；S2 摄取失败入口，本任务不接管线）。

    仅 staging → failed（单向流转）；active/retired 版本不允许置 failed。
    """
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    _get_document(session, workspace_id=workspace_id, document_id=document_id)
    version = _get_version_in_document(
        session, document_id=document_id, version_id=version_id
    )
    if version.status != "staging":
        raise AppError(
            "KN-409", f"版本状态为 {version.status}，仅 staging 可标记失败"
        )
    version.status = "failed"
    session.flush()
    log.info(
        "version marked failed id=%s document=%s", version.version_id, document_id
    )
    return version
