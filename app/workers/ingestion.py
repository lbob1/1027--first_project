"""摄取任务编排（M-S2-T04）：MinIO 取件 → 解析 → 切块 → 向量化 → 入库。

- 任务参数只传 version_id（最小参数原则），workspace/document 信息从库查；
- **同一事务**内完成：chunks 批量插入 + activate_version（新版→active、
  旧 active→retired，细则 5）——任一步失败整体回滚；
- 失败显式暴露（细则 6）：回滚后 mark_version_failed 置 failed（新事务），
  禁止把失败版本留在 staging 悬挂；
- 版本行禁止任何 UPDATE/DELETE——状态流转只走 version.py 既有入口；
  worker 以 workspace owner 身份调用（从 workspace_members 查库取得，
  非 worker 自报，保持 _require_member 语义不变）；
- 幂等：非 staging 版本直接跳过（防重复摄取）；
- 日志禁止出现 API key / 连接串 / 文件正文内容（细则 9）。
"""

import hashlib
import logging
import uuid

from sqlalchemy import select

from app.core.db import get_session
from app.models.models import (
    Chunk,
    Document,
    DocumentVersion,
    User,
    WorkspaceMember,
)
from app.services import chunker, storage
from app.services import version as version_svc
from app.services import workspace as workspace_svc
from app.services.embedding import embed_texts
from app.services.parser import parse_document
from app.workers.celery_app import celery_app

log = logging.getLogger("app.workers.ingestion")


def _load_owner_and_version(session, version_id: uuid.UUID):
    """查版本行 + 文档 + owner user_id（worker 的系统身份来源）。"""
    version = session.get(DocumentVersion, version_id)
    if version is None:
        raise LookupError(f"version {version_id} 不存在")
    doc = session.get(Document, version.document_id)
    if doc is None:
        raise LookupError(f"document {version.document_id} 不存在")
    owner = session.execute(
        select(User.user_id)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.user_id)
        .where(
            WorkspaceMember.workspace_id == version.workspace_id,
            WorkspaceMember.role == workspace_svc.OWNER_ROLE,
        )
        .limit(1)
    ).scalar_one_or_none()
    if owner is None:
        raise LookupError(f"workspace {version.workspace_id} 无 owner")
    return version, doc, owner


@celery_app.task(name="miniknora.ingest.ingest_version", bind=True)
def ingest_version(self, version_id: str) -> dict:
    """摄取任务；失败时显式置 failed（细则 6）后原样抛出。"""
    try:
        return _do_ingest(version_id)
    except Exception as exc:
        _mark_failed(version_id, exc)
        raise


def _mark_failed(version_id: str, exc: Exception) -> None:
    """失败收尾：此时原事务已由 get_session 兜底回滚，新事务置 failed。"""
    try:
        vid = uuid.UUID(version_id)
        with get_session() as session:
            version, _doc, owner = _load_owner_and_version(session, vid)
            if version.status == "staging":
                version_svc.mark_version_failed(
                    session, user_id=owner, workspace_id=version.workspace_id,
                    document_id=version.document_id, version_id=vid,
                )
                log.info(
                    "摄取失败已置 failed version=%s err=%s", vid, type(exc).__name__
                )
    except Exception as nested:
        log.error(
            "mark_version_failed 自身失败 version=%s err=%s",
            version_id, type(nested).__name__,
        )


def _do_ingest(version_id: str) -> dict:
    vid = uuid.UUID(version_id)

    # 幂等闸门：非 staging 直接跳过
    with get_session() as session:
        version, doc, owner = _load_owner_and_version(session, vid)
        if version.status != "staging":
            log.info(
                "version=%s status=%s 非 staging，跳过摄取", version_id, version.status
            )
            return {"version_id": version_id, "skipped": True, "status": version.status}
        ws_id, doc_id = version.workspace_id, version.document_id

    log.info("摄取开始 version=%s document=%s", version_id, doc_id)

    # a. 取原件 bytes（MinIO）
    data = storage.get_object(version.file_path)
    log.info("取件完成 bytes=%d", len(data))

    # c. 文档级指纹对照（建版本时存的 sha256，此处只读重算对照）
    digest = hashlib.sha256(data).hexdigest()
    if digest != version.content_hash:
        raise ValueError(
            "content_hash 对照失败：对象存储内容与版本指纹不一致"
        )

    # b. 解析（扫描件自动过 OCR，parser 已保证）
    text = parse_document(data, doc.filename)
    log.info("解析完成 chars=%d", len(text))

    # d. 切块 + 向量化（embedding 失败在此显式抛出）
    pieces = chunker.chunk_text(text)
    if not pieces:
        raise ValueError("切块结果为空：文档解析文本无有效内容")
    vectors = embed_texts(pieces)
    log.info("向量化完成 chunks=%d", len(pieces))

    # e. 同一事务：chunks 批量插入 + activate_version（细则 5）
    with get_session() as session:
        fresh, _doc, _owner = _load_owner_and_version(session, vid)
        if fresh.status != "staging":  # 双保险：并发摄取已被其他 worker 完成
            return {"version_id": version_id, "skipped": True, "status": fresh.status}
        rows = []
        for seq, (piece, vec) in enumerate(zip(pieces, vectors)):
            rows.append(
                Chunk(
                    workspace_id=ws_id,
                    version_id=vid,  # document 归属经 version 间接（chunks 表无 document_id）
                    seq_no=seq,
                    content=piece,
                    content_hash=hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                    embedding=vec,  # tsv 由生成列自动填充，不显式写
                )
            )
        session.add_all(rows)
        session.flush()
        version_svc.activate_version(
            session, user_id=owner, workspace_id=ws_id,
            document_id=doc_id, version_id=vid,
        )
    log.info("摄取完成 version=%s chunks=%d 状态流转 active", version_id, len(pieces))

    return {"version_id": version_id, "chunks": len(pieces), "status": "active"}
