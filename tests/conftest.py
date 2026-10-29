"""M-S1-T04 测试 fixture 体系。

隔离策略选择（两种候选：显式逆序清理 vs 事务回滚）——选**事务回滚**
（savepoint 模式）：每个测试在独立 savepoint 事务中运行，结束时整体
rollback，数据天然消失。理由：① 零残留由机制保证而非靠清理代码；
② T02/T03 的手工逆序清理已两次踩 FK 顺序坑；③ 实现更简单。

连接的是真实本地 PG（miniknora_li），不建新库、不动表结构。
"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_engine
from app.models.models import User
from app.services import document as doc_svc
from app.services import version as ver_svc
from app.services import workspace as ws_svc


@pytest.fixture
def session() -> Iterator[Session]:
    """每测试独立 savepoint 事务：结束整体 rollback，天然零残留。"""
    connection = get_engine().connect()
    transaction = connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transaction.rollback()
        connection.close()


class Factory:
    """测试数据工厂：所有实体经 service 创建（正例路径）。"""

    def __init__(self, s: Session) -> None:
        self._s = s
        self._n = 0

    def user(self) -> User:
        self._n += 1
        u = User(
            username=f"t04-{self._n}-{uuid.uuid4().hex[:8]}",
            password_hash="not-a-real-hash",
        )
        self._s.add(u)
        self._s.flush()
        return u

    def workspace(self, user: User, name: str = "ws"):
        return ws_svc.create_workspace(
            self._s, user_id=user.user_id, name=name
        )

    def document(self, user: User, ws, filename: str = "doc.txt"):
        return doc_svc.create_document(
            self._s, user_id=user.user_id, workspace_id=ws.workspace_id,
            filename=filename,
        )

    def version(self, user: User, ws, doc, tag: str = "v"):
        return ver_svc.create_new_version(
            self._s, user_id=user.user_id, workspace_id=ws.workspace_id,
            document_id=doc.document_id, content_hash=tag * 64,
            file_path=f"t04/{tag}.txt",
        )


@pytest.fixture
def factory(session: Session) -> Factory:
    return Factory(session)
