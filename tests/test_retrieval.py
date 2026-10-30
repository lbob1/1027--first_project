"""检索组测试（M-S3 行为固化，M-S5-T03）。

**真实 API 依赖（沿用既有"真实 API"先例并注明）**：摄取 .apply() 与
search_vec 的 query 向量化均调百炼真实 embedding API（与
test_ingestion_smoke 同款取舍）——模型 key 从 .env 读（conftest 只对
JWT_SECRET_KEY 做测试进程兜底，不注入任何模型密钥）；CI / 无网环境
本文件用例预期失败，属已知取舍，不计入覆盖率硬指标。

- 造数经 service 正例路径 + .apply() 同步 + 真实提交（ingest 任务经
  get_session 独立连接，看不见 savepoint 未提交数据——同 smoke 两阶段
  清理纪律，fixture finally 清理）；
- hybrid 命中断言消费 M-S3-T01/T02 六字段 + rrf_score + sources 契约；
- retired 版本不可见 / B 区隔离 / top_k 生效（隔离过滤在 SQL WHERE）；
- rerank 降级为纯单元：monkeypatch httpx.post 抛 TimeoutError → 原序
  返回不抛异常（不依赖真实 rerank 端点；get_settings 一并桩化，隔离
  RERANK_ENABLED 配置差异）。
"""

import uuid

import pytest
from sqlalchemy import delete, func, select

from app.core.db import get_session
from app.models.models import (
    Chunk, Document, DocumentVersion, User, Workspace, WorkspaceMember,
)
from app.services import document as doc_svc
from app.services import rerank as rerank_mod
from app.services import storage
from app.services import workspace as ws_svc
from app.services.retrieval_hybrid import search_hybrid
from app.services.upload import register_upload
from app.workers.ingestion import ingest_version

# ~1100 字 → CHUNK_SIZE=400/overlap=50 滑动窗口产出多块
_DOC_BODY = (
    "光合作用是植物利用光能将二氧化碳和水转化为有机物并释放氧气的过程。"
    "叶绿体中的叶绿素吸收光能，驱动光反应与暗反应两个阶段，将光能转化为化学能。"
) * 10
_DOC_V2_BODY = (
    "橙子富含维生素C，柑橘类水果的果皮含有挥发油，常被用于提取精油与调味。"
) * 10
_KEYWORD = "光合作用"


@pytest.fixture()
def retrieval_ws():
    """真提交造 user+ws；结束按 ws 前缀清理 MinIO 对象与全部相关行。"""
    with get_session() as s:
        user = User(username=f"t03-ret-{uuid.uuid4().hex[:8]}",
                    password_hash="not-a-real-hash")
        s.add(user)
        s.flush()
        ws = ws_svc.create_workspace(
            s, user_id=user.user_id, name=f"ws-t03ret-{uuid.uuid4().hex[:8]}")
        s.flush()
        uid, wsid = user.user_id, ws.workspace_id
    yield uid, wsid
    keys = storage.list_object_keys(prefix=str(wsid))
    for k in keys:
        storage.remove_object(k)
    with get_session() as s:
        s.execute(Chunk.__table__.delete().where(Chunk.workspace_id == wsid))
        s.execute(Document.__table__.update().where(Document.workspace_id == wsid)
                  .values(active_version=None))
        s.execute(DocumentVersion.__table__.delete().where(
            DocumentVersion.document_id.in_(
                select(Document.document_id).where(Document.workspace_id == wsid))))
        s.execute(delete(Document).where(Document.workspace_id == wsid))
        # 按属主清理（用例内可能另造 ws_b——按 wsid 只删 ws_a 会 FK 阻断）
        s.execute(delete(WorkspaceMember).where(WorkspaceMember.user_id == uid))
        s.execute(delete(Workspace).where(Workspace.owner_user_id == uid))
        s.execute(delete(User).where(User.user_id == uid))


def _ingest(uid, wsid, filename, body, document_id=None):
    """service 正例路径上传 + .apply() 同步摄取；返回 document_id。"""
    with get_session() as s:
        if document_id is None:
            doc = doc_svc.create_document(
                s, user_id=uid, workspace_id=wsid, filename=filename)
            document_id = doc.document_id
        r = register_upload(
            s, user_id=uid, workspace_id=wsid, document_id=document_id,
            filename=filename, data=body.encode("utf-8"))
    assert r["status"] == "accepted", r
    ar = ingest_version.apply(args=[r["version_id"]])
    assert ar.successful(), f"摄取失败: {ar.result}"
    return document_id


# ---------- hybrid 命中契约（六字段 + rrf_score + sources） ----------

def test_hybrid_hit_fields_and_rrf_contract(retrieval_ws):
    uid, wsid = retrieval_ws
    _ingest(uid, wsid, "photosynthesis.txt", _DOC_BODY)
    with get_session() as s:
        hits = search_hybrid(s, workspace_id=wsid, query=_KEYWORD, top_k=5)
    assert hits, "预期至少命中一条"
    for h in hits:
        for f in ("chunk_id", "seq_no", "content", "rank", "filename", "version_no"):
            assert f in h, f"六字段缺 {f}: {sorted(h)}"
        assert 0 < h["rrf_score"] <= 2 / 61  # 单路 1/(60+r)，双路相加上限 2/61
        assert h["sources"] and set(h["sources"]) <= {"fts", "vec"}
        assert h["filename"] == "photosynthesis.txt"
    assert hits[0]["rrf_score"] >= hits[-1]["rrf_score"]  # 降序


# ---------- B 区隔离（隔离过滤在 SQL WHERE，细则 1） ----------

def test_cross_workspace_search_isolation(retrieval_ws):
    uid, wsid_a = retrieval_ws
    _ingest(uid, wsid_a, "photosynthesis.txt", _DOC_BODY)
    with get_session() as s:
        ws_b = ws_svc.create_workspace(
            s, user_id=uid, name=f"ws-b-{uuid.uuid4().hex[:8]}")
        wsid_b = ws_b.workspace_id
    with get_session() as s:
        hits = search_hybrid(s, workspace_id=wsid_b, query=_KEYWORD, top_k=10)
    assert hits == [], "B 区不应检索到 A 区 chunk"


# ---------- retired 版本不可见（只检索 active 版本） ----------

def test_retired_version_invisible(retrieval_ws):
    uid, wsid = retrieval_ws
    doc_id = _ingest(uid, wsid, "fruit.txt", _DOC_BODY)     # v1：光合作用
    _ingest(uid, wsid, "fruit.txt", _DOC_V2_BODY, document_id=doc_id)  # v2：橙子
    with get_session() as s:
        hits_v1 = search_hybrid(s, workspace_id=wsid, query=_KEYWORD, top_k=10)
    assert all(h["version_no"] == 2 for h in hits_v1), \
        f"retired v1 不应可见: {sorted({h['version_no'] for h in hits_v1})}"
    assert all("光合作用" not in h["content"] for h in hits_v1)
    with get_session() as s:
        hits_v2 = search_hybrid(s, workspace_id=wsid, query="维生素C", top_k=10)
    assert hits_v2 and all(h["version_no"] == 2 for h in hits_v2)


# ---------- top_k 生效 ----------

def test_top_k_respected(retrieval_ws):
    uid, wsid = retrieval_ws
    _ingest(uid, wsid, "photosynthesis.txt", _DOC_BODY)
    with get_session() as s:
        n_chunks = s.execute(
            select(func.count()).select_from(Chunk)
            .where(Chunk.workspace_id == wsid)).scalar_one()
    assert n_chunks >= 2, f"造数应产出多块，实际 {n_chunks}"
    with get_session() as s:
        hits1 = search_hybrid(s, workspace_id=wsid, query=_KEYWORD, top_k=1)
        hits_all = search_hybrid(s, workspace_id=wsid, query=_KEYWORD, top_k=10)
    assert len(hits1) == 1
    assert 1 <= len(hits_all) <= 10
    assert hits1[0]["chunk_id"] == hits_all[0]["chunk_id"]  # 截断不改变排名


# ---------- rerank 降级（纯单元，不依赖真实端点） ----------

def test_rerank_degrade_on_timeout(monkeypatch):
    class _StubSettings:
        RERANK_ENABLED = True
        RERANK_MODEL = "stub-rerank"
        OPENAI_API_KEY = "stub-key"

    monkeypatch.setattr(rerank_mod, "get_settings", lambda: _StubSettings())

    def _boom(*args, **kwargs):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(rerank_mod.httpx, "post", _boom)
    docs = [{"content": f"doc{i}", "rrf_score": 0.1 - i * 0.01} for i in range(3)]
    out = rerank_mod.rerank_documents("query", docs, top_n=2)
    assert out == docs[:2]  # 超时 → 按 rrf_score 原序截断返回，不抛异常
