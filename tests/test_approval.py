"""审批组测试（M-S4-T05 行为固化，M-S5-T03）——不调真实 LLM。

**绕 router 取舍（任务书两选一，选 graph.stream + gateway mock）**：
router 节点无条件覆盖 intent，无法经初始 state 注入 delete 意图绕过；
interrupt() 必须在图执行上下文内调用，直接调节点函数不可行。故
monkeypatch ModelGateway.chat（按 system prompt 区分三处调用：router→
"delete"、文件名提取→目标文件名、生成→桩 token）：真实图路径
（delete_prepare→interrupt 挂起→恢复→审计落库→删除执行→generate）全
走到，仅 LLM 桩化——审批闭环测的是 interrupt/恢复/审计/删除，不需要真生成。

**隔离与清理**：InMemorySaver 每 thread 独立，各用例独立 thread_id；
图内节点经 get_session() 独立连接读写（audit 落库、删除执行），看不见
savepoint 未提交数据——造数走真实提交 + fixture finally 清理（同 smoke
两阶段纪律），messages 审计行（role='system'，[APPROVAL] 前缀）在清理范围。
"""

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.core.db import get_session
from app.core.errors import AppError
from app.core.gateway import ModelGateway
from app.graphs.agent_graph import stream_answer
from app.models.models import (
    Chunk, Document, DocumentVersion, Message, User, Workspace, WorkspaceMember,
)
from app.services import document as doc_svc
from app.services import storage
from app.services import workspace as ws_svc


def _llm(text: str):
    """gateway.chat 非 stream 返回 OpenAI 响应对象——节点消费
    resp.choices[0].message.content，桩须同构（str 会 AttributeError）。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _fake_gateway_chat(target_filename: str):
    """ModelGateway.chat 桩：按 system prompt 与 stream kwarg 区分三处调用。"""

    def fake_chat(self, messages, **kwargs):
        if kwargs.get("stream"):  # _generate 的流式生成（逐 token 字符串）
            return iter(["已按确认删除。"])
        system = messages[0]["content"]
        if "意图分类" in system:  # _ROUTER_SYSTEM → 恒 delete 意图
            return _llm("delete")
        if "提取要删除的文档文件名" in system:  # _EXTRACT_SYSTEM → 目标文件名
            return _llm(target_filename)
        return _llm("ok")

    return fake_chat


@pytest.fixture()
def approval_ws():
    """真提交造 user+ws；结束清理 messages（审计行）与全部相关行 + MinIO。"""
    with get_session() as s:
        user = User(username=f"t03-appr-{uuid.uuid4().hex[:8]}",
                    password_hash="not-a-real-hash")
        s.add(user)
        s.flush()
        ws = ws_svc.create_workspace(
            s, user_id=user.user_id, name=f"ws-t03appr-{uuid.uuid4().hex[:8]}")
        s.flush()
        uid, wsid = user.user_id, ws.workspace_id
    yield uid, wsid
    keys = storage.list_object_keys(prefix=str(wsid))
    for k in keys:
        storage.remove_object(k)
    with get_session() as s:
        s.execute(delete(Message).where(Message.workspace_id == wsid))
        s.execute(Chunk.__table__.delete().where(Chunk.workspace_id == wsid))
        s.execute(Document.__table__.update().where(Document.workspace_id == wsid)
                  .values(active_version=None))
        s.execute(DocumentVersion.__table__.delete().where(
            DocumentVersion.document_id.in_(
                select(Document.document_id).where(Document.workspace_id == wsid))))
        s.execute(delete(Document).where(Document.workspace_id == wsid))
        s.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == wsid))
        s.execute(delete(Workspace).where(Workspace.workspace_id == wsid))
        s.execute(delete(User).where(User.user_id == uid))


def _approval_rows(wsid) -> list[dict]:
    """本 workspace 全部审批审计行 → 解析后的 JSON 列表（保持落库顺序）。"""
    with get_session() as s:
        rows = s.execute(
            select(Message).where(Message.workspace_id == wsid)
        ).scalars().all()
    return [
        json.loads(m.content[len("[APPROVAL] "):])
        for m in rows if m.content.startswith("[APPROVAL]")
    ]


def _make_doc(uid, wsid, filename) -> uuid.UUID:
    with get_session() as s:
        doc = doc_svc.create_document(
            s, user_id=uid, workspace_id=wsid, filename=filename)
        return doc.document_id


def test_approval_suspend_then_approve(approval_ws, monkeypatch):
    """挂起 → pending 审计行；resume=True → 文档被删 + approved 行（闭环）。"""
    uid, wsid = approval_ws
    filename = f"t03-del-{uuid.uuid4().hex[:8]}.txt"
    doc_id = _make_doc(uid, wsid, filename)
    tid = uuid.uuid4().hex  # 每 thread 独立（InMemorySaver 隔离）
    monkeypatch.setattr(ModelGateway, "chat", _fake_gateway_chat(filename))

    # --- 第一段：发起删除 → interrupt 挂起 ---
    events = list(stream_answer(wsid, f"删除 {filename}",
                                thread_id=tid, user_id=uid))
    kinds = [next(iter(e)) for e in events]
    assert "approval_required" in kinds, f"事件序列: {kinds}"
    apr = next(e["approval_required"] for e in events if "approval_required" in e)
    assert apr["tool"] == "delete_document"
    assert apr["filename"] == filename
    assert apr["risk"]  # 风险文案在位
    assert "token" not in kinds and "budget" not in kinds  # 挂起 run 无答案
    audits = _approval_rows(wsid)
    assert [a["event"] for a in audits] == ["pending"]

    # --- 第二段：confirm=True 恢复 → 删除执行 + generate 转述 ---
    events2 = list(stream_answer(wsid, f"删除 {filename}",
                                 thread_id=tid, user_id=uid, confirm=True))
    kinds2 = [next(iter(e)) for e in events2]
    assert kinds2[:1] == ["sources"]  # 恢复 run 正常走 generate（空 hits）
    assert {"token": "已按确认删除。"} in events2
    assert "budget" in kinds2 and kinds2[-1] == "trace"
    with get_session() as s:
        assert s.get(Document, doc_id) is None, "批准后文档应已删除"
    audits = _approval_rows(wsid)
    assert [a["event"] for a in audits] == ["pending", "approved"]
    assert audits[1]["filename"] == filename  # payload 与挂起一致


def test_approval_reject(approval_ws, monkeypatch):
    """resume=False → 文档保留 + rejected 行 + 不执行删除。"""
    uid, wsid = approval_ws
    filename = f"t03-keep-{uuid.uuid4().hex[:8]}.txt"
    doc_id = _make_doc(uid, wsid, filename)
    tid = uuid.uuid4().hex
    monkeypatch.setattr(ModelGateway, "chat", _fake_gateway_chat(filename))

    list(stream_answer(wsid, f"删除 {filename}", thread_id=tid, user_id=uid))
    events2 = list(stream_answer(wsid, f"删除 {filename}",
                                 thread_id=tid, user_id=uid, confirm=False))
    kinds2 = [next(iter(e)) for e in events2]
    assert "token" in kinds2  # 拒绝结论经 generate 转述
    with get_session() as s:
        assert s.get(Document, doc_id) is not None, "拒绝后文档必须仍在"
    audits = _approval_rows(wsid)
    assert [a["event"] for a in audits] == ["pending", "rejected"]


def test_resume_without_pending_kn400(approval_ws):
    """无挂起 thread resume → KN-400（get_state 预检，防重跑图重复挂起）。"""
    uid, wsid = approval_ws
    ghost_tid = uuid.uuid4().hex  # 从未发起删除的 thread
    with pytest.raises(AppError) as ei:
        list(stream_answer(wsid, "随便说说", thread_id=ghost_tid,
                           user_id=uid, confirm=True))
    assert ei.value.code == "KN-400"
    assert "没有待确认的删除审批" in ei.value.message
    assert _approval_rows(wsid) == []  # 预检失败零审计副作用
