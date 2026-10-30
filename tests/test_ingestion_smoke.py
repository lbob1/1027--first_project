"""摄取冒烟测试（M-S2-T06，S2-AC-6；M-S5-T02 起 JWT 化）。

- 三种格式（pdf/docx/md）各一用例，Celery 用 .apply() 同步模式（不起 worker）；
- **上传改走 HTTP + Bearer JWT（TestClient，M-S5-T02）**：验证 get_current_user_id
  依赖注入下的全链路（token→user_id→service 成员判定→注册→派发）——
  fixture 造用户（session 级 bcrypt hash 入库）→ issue_token → 请求带
  Authorization: Bearer；上传端点的 .delay() 被 autouse fixture 换为
  记录桩（不起 worker、不写 Redis），摄取本体仍由测试内 .apply() 同步执行；
- **不用 conftest 的 savepoint 事务回滚 fixture**：ingest 任务内部经
  app.core.db.get_session() 走独立连接/事务，看不见本测试 savepoint 里
  未提交的数据——故本文件用真实提交 + fixture finally 清理（DBA 通道：
  先断 active_version 指针再删版本行，T03 已知 FK 顺序）；
- 测试连真实 PG/MinIO，embedding 走真实 API（小文件成本可忽略）；
- 全部测试数据零残留（表 + MinIO 双清理）。
"""

import hashlib
import io
import uuid
from types import SimpleNamespace

import fitz
import pytest
from docx import Document as DocxBuilder
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.main import app as api_app
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
from app.services import workspace as ws_svc
from app.workers.ingestion import ingest_version

_TEXT = (
    "MiniKnora 冒烟测试文档。本文用于验证上传注册与摄取编排的全链路。"
    "摄取任务会解析文本、按四百字滑动窗口切块、批量调用向量化接口，"
    "并在同一数据库事务内写入块行与版本状态流转。"
) * 4


@pytest.fixture(autouse=True)
def _sync_ingest(monkeypatch):
    """上传端点经 .delay() 派发——测试内换记录桩（不起 worker、不写 Redis）。"""
    monkeypatch.setattr(
        ingest_version, "delay",
        lambda version_id: SimpleNamespace(id=f"sync-{version_id}"),
    )


@pytest.fixture()
def smoke_ws(smoke_password_hash, issue_jwt):
    """真提交造 user+workspace（真实 bcrypt hash）并签发 JWT；结束按 ws 前缀全清。"""
    with get_session() as s:
        user = User(username=f"smoke-{uuid.uuid4().hex[:8]}",
                    password_hash=smoke_password_hash)
        s.add(user)
        s.flush()
        ws = ws_svc.create_workspace(s, user_id=user.user_id,
                                     name=f"ws-smoke-{uuid.uuid4().hex[:8]}")
        s.flush()
        uid, wsid = user.user_id, ws.workspace_id
    token = issue_jwt(uid)
    yield uid, wsid, token
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
    d = DocxBuilder()
    for para in (_TEXT[i : i + 200] for i in range(0, len(_TEXT), 200)):
        d.add_paragraph(para)
    bio = io.BytesIO()
    d.save(bio)
    return bio.getvalue()


def _upload_one(wsid, token, filename, data, ext_tag):
    """HTTP 上传（Bearer JWT）→ 同步摄取 → 断言 chunks/向量/tsv。"""
    client = TestClient(api_app)
    r = client.post(
        f"/api/v1/workspaces/{wsid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, data)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "KN-000" and body["message"] == "ok", body
    d = body["data"]
    assert d["status"] == "accepted", d
    assert d["task_id"].startswith("sync-")  # .delay() 桩（见 _sync_ingest）
    assert d["document_id"]  # T06 事件③：document_id 在响应中
    # 同步执行摄取任务（不起 worker）
    ar = ingest_version.apply(args=[d["version_id"]])
    assert ar.successful(), f"task 失败: {ar.result}"
    with get_session() as s:
        v = s.get(DocumentVersion, uuid.UUID(d["version_id"]))
        assert v.status == "active", v.status
        chunks = s.execute(select(Chunk).where(Chunk.version_id == v.version_id)).scalars().all()
        assert len(chunks) > 0, "chunks 为空"
        c0 = chunks[0]
        assert c0.embedding and len(c0.embedding) == 1024, "embedding 1024 维"
        assert c0.tsv is not None and len(str(c0.tsv)) > 10, "tsv 生成列非空"
    return d


def test_smoke_pdf(smoke_ws):
    uid, wsid, token = smoke_ws
    d = _upload_one(wsid, token, "smoke.pdf", _pdf_bytes(), "pdf")
    assert d["version_no"] == 1


def test_smoke_docx(smoke_ws):
    uid, wsid, token = smoke_ws
    d = _upload_one(wsid, token, "smoke.docx", _docx_bytes(), "docx")
    assert d["version_no"] == 1


def test_smoke_md(smoke_ws):
    uid, wsid, token = smoke_ws
    d = _upload_one(wsid, token, "smoke.md", ("# 标题\n\n" + _TEXT).encode("utf-8"), "md")
    assert d["version_no"] == 1
