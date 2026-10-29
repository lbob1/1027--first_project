"""摄取冒烟测试（M-S2-T06，S2-AC-6）。

- 三种格式（pdf/docx/md）各一用例，Celery 用 .apply() 同步模式（不起 worker）；
- **不用 conftest 的 savepoint 事务回滚 fixture**：ingest 任务内部经
  app.core.db.get_session() 走独立连接/事务，看不见本测试 savepoint 里
  未提交的数据——故本文件用真实提交 + fixture finally 清理（DBA 通道：
  先断 active_version 指针再删版本行，T03 已知 FK 顺序）；
- 测试连真实 PG/MinIO，embedding 走真实 API（小文件成本可忽略）；
- 全部测试数据零残留（表 + MinIO 双清理）。
"""

import hashlib
import uuid

import fitz
import pytest
from docx import Document as DocxBuilder
from sqlalchemy import delete, func, select

from app.core.db import get_session
from app.models.models import (
    Chunk,
    Document,
    DocumentVersion,
    User,
    Workspace,
    WorkspaceMember,
)
from app.services import storage
from app.services import document as doc_svc
from app.services import workspace as ws_svc
from app.services.upload import register_upload
from app.workers.ingestion import ingest_version

_TEXT = (
    "MiniKnora 冒烟测试文档。本文用于验证上传注册与摄取编排的全链路。"
    "摄取任务会解析文本、按四百字滑动窗口切块、批量调用向量化接口，"
    "并在同一数据库事务内写入块行与版本状态流转。"
) * 4


@pytest.fixture()
def smoke_ws():
    """真提交造 user+workspace，测试结束按 ws 前缀全清（表+MinIO）。"""
    with get_session() as s:
        user = User(username=f"smoke-{uuid.uuid4().hex[:8]}", password_hash="not-a-real-hash")
        s.add(user)
        s.flush()
        ws = ws_svc.create_workspace(s, user_id=user.user_id, name=f"ws-smoke-{uuid.uuid4().hex[:8]}")
        s.flush()
        uid, wsid = user.user_id, ws.workspace_id
    yield uid, wsid
    # ---- 清理（零残留双保险）----
    keys = storage.list_object_keys(prefix=str(wsid))
    for k in keys:
        storage.remove_object(k)
    with get_session() as s:
        s.execute(Document.__table__.update().where(Document.workspace_id == wsid)
                  .values(active_version=None))
        s.execute(Chunk.__table__.delete().where(Chunk.workspace_id == wsid))
        s.execute(DocumentVersion.__table__.delete().where(DocumentVersion.document_id.in_(
            select(Document.document_id).where(Document.workspace_id == wsid))))
        s.execute(delete(Document).where(Document.workspace_id == wsid))
        s.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == wsid))
        s.execute(delete(Workspace).where(Workspace.workspace_id == wsid))
        s.execute(delete(User).where(User.user_id == uid))
        s.flush()
        # 断言作用域：仅本 fixture 造的数据（ws/user 范围）——全表可能含
        # 其他测试/实证的合法共存数据，全局零残留由 test_isolation 的
        # 专门用例在干净库上负责
        n_ws = s.execute(select(func.count()).select_from(Workspace)
                         .where(Workspace.workspace_id == wsid)).scalar_one()
        n_doc = s.execute(select(func.count()).select_from(Document)
                          .where(Document.workspace_id == wsid)).scalar_one()
        n_ver = s.execute(select(func.count()).select_from(DocumentVersion)
                          .join(Document, Document.document_id == DocumentVersion.document_id)
                          .where(Document.workspace_id == wsid)).scalar_one()
        n_chunk = s.execute(select(func.count()).select_from(Chunk)
                            .where(Chunk.workspace_id == wsid)).scalar_one()
        n_user = s.execute(select(func.count()).select_from(User)
                           .where(User.user_id == uid)).scalar_one()
        assert not any([n_ws, n_doc, n_ver, n_chunk, n_user]), \
            f"smoke 残留: ws={n_ws} doc={n_doc} ver={n_ver} chunk={n_chunk} user={n_user}"


def _pdf_bytes() -> bytes:
    d = fitz.open()
    p = d.new_page()
    for i in range(0, len(_TEXT), 40):
        y = 50 + (i // 40) * 12
        if y > 780:
            break
        p.insert_text((40, y), _TEXT[i : i + 40], fontsize=8, fontname="china-s")
    return d.tobytes()


def _docx_bytes() -> bytes:
    import io

    d = DocxBuilder()
    for para in (_TEXT[i : i + 200] for i in range(0, len(_TEXT), 200)):
        d.add_paragraph(para)
    bio = io.BytesIO()
    d.save(bio)
    return bio.getvalue()


def _run_one(uid, wsid, filename, data, ext_tag):
    with get_session() as s:
        doc = doc_svc.create_document(
            s, user_id=uid, workspace_id=wsid, filename=f"smoke-{ext_tag}.{filename.split('.')[-1]}"
        )
        s.flush()
        r = register_upload(
            s, user_id=uid, workspace_id=wsid, document_id=doc.document_id,
            filename=filename, data=data,
        )
    assert r["status"] == "accepted", r
    # 同步执行摄取任务（不起 worker）
    ar = ingest_version.apply(args=[r["version_id"]])
    assert ar.successful(), f"task 失败: {ar.result}"
    with get_session() as s:
        v = s.get(DocumentVersion, uuid.UUID(r["version_id"]))
        assert v.status == "active", v.status
        chunks = s.execute(select(Chunk).where(Chunk.version_id == v.version_id)).scalars().all()
        assert len(chunks) > 0, "chunks 为空"
        c0 = chunks[0]
        assert c0.embedding and len(c0.embedding) == 1024, "embedding 1024 维"
        assert c0.tsv is not None and len(str(c0.tsv)) > 10, "tsv 生成列非空"
    return r


def test_smoke_pdf(smoke_ws):
    uid, wsid = smoke_ws
    r = _run_one(uid, wsid, "smoke.pdf", _pdf_bytes(), "pdf")
    assert r["version_no"] == 1


def test_smoke_docx(smoke_ws):
    uid, wsid = smoke_ws
    r = _run_one(uid, wsid, "smoke.docx", _docx_bytes(), "docx")
    assert r["version_no"] == 1


def test_smoke_md(smoke_ws):
    uid, wsid = smoke_ws
    r = _run_one(uid, wsid, "smoke.md", ("# 标题\n\n" + _TEXT).encode("utf-8"), "md")
    assert r["version_no"] == 1
