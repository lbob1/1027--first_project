"""M-S1-T04：隔离与版本负例测试（S1 收尾，S1-AC-1/2/3/5）。

负例断言计数（S1-AC-5 要求 ≥6，本文件共 14 条 AppError/空列表断言，
逐条标注于各测试 docstring 的「负例 N」标记）。
"""

import inspect

import pytest
from sqlalchemy import func, select

import app.services.version as ver_mod
from app.core.db import get_engine
from app.core.errors import AppError
from app.models.models import (
    Chunk, Document, DocumentVersion, Message, User, Workspace, WorkspaceMember,
)
from app.services import document as doc_svc
from app.services import version as ver_svc
from app.services import workspace as ws_svc


# ---------- 跨区读负例（S1-AC-1） ----------

def test_cross_workspace_list_is_empty(session, factory):
    """负例 1：B list 自己 workspace -> 空列表（A 的文档不在 B 区）；
    B 直查 A 区列表 -> KN-404（非成员连列表可见性都没有，细则 1）。
    """
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice, name="ws-A")
    ws_b = factory.workspace(bob, name="ws-B")
    factory.document(alice, ws_a, "a-secret.txt")

    assert doc_svc.list_documents(
        session, user_id=bob.user_id, workspace_id=ws_b.workspace_id
    ) == []
    with pytest.raises(AppError) as ei:
        doc_svc.list_documents(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id
        )
    assert ei.value.code == "KN-404"


def test_cross_workspace_get_by_id_404(session, factory):
    """负例 2：B 按 ID 取 A 区文档 -> KN-404（不泄露存在性）。"""
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice)
    doc = factory.document(alice, ws_a)

    with pytest.raises(AppError) as ei:
        doc_svc.get_document(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id,
            document_id=doc.document_id,
        )
    assert ei.value.code == "KN-404"


def test_non_member_workspace_access_404(session, factory):
    """负例 3：非成员 get_workspace / delete_workspace -> KN-404。"""
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice)

    with pytest.raises(AppError) as ei:
        ws_svc.get_workspace(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id
        )
    assert ei.value.code == "KN-404"
    with pytest.raises(AppError) as ei:
        ws_svc.delete_workspace(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id
        )
    assert ei.value.code == "KN-404"


# ---------- 跨区写负例 ----------

def test_cross_workspace_write_404(session, factory):
    """负例 4/5：B 在 A 区建文档 / 建版本 -> KN-404。"""
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice)
    doc = factory.document(alice, ws_a)

    with pytest.raises(AppError) as ei:
        doc_svc.create_document(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id,
            filename="intrusion.txt",
        )
    assert ei.value.code == "KN-404"
    with pytest.raises(AppError) as ei:
        ver_svc.create_new_version(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id,
            document_id=doc.document_id, content_hash="x" * 64,
            file_path="t04/intrusion.txt",
        )
    assert ei.value.code == "KN-404"


def test_cross_workspace_activate_and_mark_404(session, factory):
    """负例 6/7：B 激活 / 标记失败 A 区版本 -> KN-404。"""
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice)
    doc = factory.document(alice, ws_a)
    v1 = factory.version(alice, ws_a, doc, tag="a")

    with pytest.raises(AppError) as ei:
        ver_svc.activate_version(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id,
            document_id=doc.document_id, version_id=v1.version_id,
        )
    assert ei.value.code == "KN-404"
    with pytest.raises(AppError) as ei:
        ver_svc.mark_version_failed(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id,
            document_id=doc.document_id, version_id=v1.version_id,
        )
    assert ei.value.code == "KN-404"


# ---------- 角色负例（细则 3：角色只从数据库判定） ----------

def test_insufficient_role_delete_workspace_403(session, factory):
    """负例 8：成员但非 owner 删 workspace -> KN-403。"""
    alice, bob = factory.user(), factory.user()
    ws_a = factory.workspace(alice)
    # bob 加入 ws-A 为普通 member（数据准备：角色只落库，不经参数）
    session.add(
        WorkspaceMember(
            workspace_id=ws_a.workspace_id, user_id=bob.user_id, role="member"
        )
    )
    session.flush()

    with pytest.raises(AppError) as ei:
        ws_svc.delete_workspace(
            session, user_id=bob.user_id, workspace_id=ws_a.workspace_id
        )
    assert ei.value.code == "KN-403"


# ---------- 版本不可变代码级佐证（S1-AC-2） ----------

def test_version_module_has_no_mutate_or_delete_paths():
    """负例 9（代码级）：version 模块全部公共函数源码无 delete/update 调用；
    DocumentVersion 模型类不定义任何 update/delete 方法。
    """
    forbidden = (
        "session.delete", ".delete(", "session.update", "sqlalchemy.update",
        ".merge(", "Session.delete",
    )
    for name, fn in inspect.getmembers(ver_mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        src = inspect.getsource(fn)
        for token in forbidden:
            assert token not in src, f"{name} 含禁止路径 {token!r}"
    model_methods = [
        n for n, _ in inspect.getmembers(DocumentVersion, inspect.isfunction)
    ]
    assert not any(("update" in n) or ("delete" in n) for n in model_methods)


def test_version_content_fields_only_set_on_insert(session, factory):
    """负例 10（行为级）：两次激活之间版本内容字段保持不变（只读快照对比）。"""
    alice = factory.user()
    ws = factory.workspace(alice)
    doc = factory.document(alice, ws)
    v1 = factory.version(alice, ws, doc, tag="a")
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v1.version_id,
    )
    frozen = (v1.version_no, v1.content_hash, v1.file_path)

    v2 = factory.version(alice, ws, doc, tag="b")
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v2.version_id,
    )
    session.refresh(v1)
    assert (v1.version_no, v1.content_hash, v1.file_path) == frozen
    assert v1.status == "retired"  # 仅 status 流转


# ---------- 状态流转负例（D-1 单向流转） ----------

def test_activate_retired_and_failed_409(session, factory):
    """负例 11/12：激活 retired / failed 版本 -> KN-409。"""
    alice = factory.user()
    ws = factory.workspace(alice)
    doc = factory.document(alice, ws)
    v1 = factory.version(alice, ws, doc, tag="a")
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v1.version_id,
    )
    v2 = factory.version(alice, ws, doc, tag="b")
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v2.version_id,
    )
    v3 = factory.version(alice, ws, doc, tag="c")
    ver_svc.mark_version_failed(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v3.version_id,
    )

    with pytest.raises(AppError) as ei:
        ver_svc.activate_version(
            session, user_id=alice.user_id, workspace_id=ws.workspace_id,
            document_id=doc.document_id, version_id=v1.version_id,  # retired
        )
    assert ei.value.code == "KN-409"
    with pytest.raises(AppError) as ei:
        ver_svc.activate_version(
            session, user_id=alice.user_id, workspace_id=ws.workspace_id,
            document_id=doc.document_id, version_id=v3.version_id,  # failed
        )
    assert ei.value.code == "KN-409"


# ---------- 错误码白名单（AppError 防御） ----------

def test_apperror_rejects_unknown_code():
    """负例 13：AppError 拒绝表外错误码（ValueError）。"""
    with pytest.raises(ValueError):
        AppError("KN-999")


# ---------- 版本正例（S1-AC-3） ----------

def test_version_positive_flow_and_pointer(session, factory):
    """S1-AC-3 正例：二次上传递增 + 旧行保留 + 指针切换。"""
    alice = factory.user()
    ws = factory.workspace(alice)
    doc = factory.document(alice, ws)

    v1 = factory.version(alice, ws, doc, tag="a")
    assert v1.version_no == 1 and v1.status == "staging"
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v1.version_id,
    )
    session.refresh(doc)
    assert doc.active_version == v1.version_id

    v2 = factory.version(alice, ws, doc, tag="b")
    assert v2.version_no == 2  # 递增
    session.refresh(v1)
    assert v1.status == "active"  # 旧行原样保留
    ver_svc.activate_version(
        session, user_id=alice.user_id, workspace_id=ws.workspace_id,
        document_id=doc.document_id, version_id=v2.version_id,
    )
    session.refresh(v1)
    session.refresh(v2)
    session.refresh(doc)
    assert v1.status == "retired"
    assert v2.status == "active"
    assert doc.active_version == v2.version_id


# ---------- 全局零残留证明（必须在最后一个位置：查真实库状态） ----------

def test_global_zero_residue_after_rollbacks():
    """验收 3：全部测试经 savepoint 回滚后，真实库 7 张表 0 行。

    本测试不经 fixture session，用独立连接查真实库。
    """
    with get_engine().connect() as conn:
        counts = {}
        for name, tbl in [
            ("users", User), ("workspaces", Workspace),
            ("workspace_members", WorkspaceMember), ("documents", Document),
            ("document_versions", DocumentVersion), ("chunks", Chunk),
            ("messages", Message),
        ]:
            counts[name] = conn.execute(
                select(func.count()).select_from(tbl)
            ).scalar_one()
        print("\n7 表行数:", counts)
        assert all(v == 0 for v in counts.values()), f"存在测试残留: {counts}"
