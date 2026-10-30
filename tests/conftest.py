"""M-S1-T04 测试 fixture 体系。

隔离策略选择（两种候选：显式逆序清理 vs 事务回滚）——选**事务回滚**
（savepoint 模式）：每个测试在独立 savepoint 事务中运行，结束时整体
rollback，数据天然消失。理由：① 零残留由机制保证而非靠清理代码；
② T02/T03 的手工逆序清理已两次踩 FK 顺序坑；③ 实现更简单。

连接的是真实本地 PG（miniknora_li），不建新库、不动表结构。

**模型 API 依赖说明（M-S5-T03）**：检索/摄取组测试走百炼真实 API
（embedding/LLM），key 从 .env 读——本文件不对任何模型密钥做兜底注入；
CI / 无网环境该两组用例预期失败，属已知取舍（各测试文件 docstring 注明）。
下方 JWT_SECRET_KEY setdefault 仅测试进程兜底（.env 已配置则不覆盖，
不触 .env 文件本体）。

M-S5-T02 补充（JWT 化）：
- smoke 测试改走 HTTP + Bearer（TestClient），需 decode_token——密钥从
  配置读；此处 env setdefault 仅测试进程兜底（用户 .env 已配置则不覆盖，
  不触 .env 文件本体）；
- smoke_password_hash（session 级）：bcrypt hash 一次全 session 复用，
  避免每用例重复 ~100ms 的 hash_password（任务书要求）；
- issue_jwt（session 级）：token 签发器直接暴露（HMAC 亚毫秒级，无需缓存）。
"""

import os
import uuid
from collections.abc import Iterator

os.environ.setdefault("JWT_SECRET_KEY", "s5t02-test-only-secret")  # 测试兜底

import pytest  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.db import get_engine  # noqa: E402
from app.core.security import hash_password, issue_token  # noqa: E402
from app.models.models import User  # noqa: E402
from app.services import document as doc_svc  # noqa: E402
from app.services import version as ver_svc  # noqa: E402
from app.services import workspace as ws_svc  # noqa: E402


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


@pytest.fixture(scope="session")
def smoke_password_hash() -> str:
    """session 级 bcrypt hash：一次计算全 session 复用（M-S5-T02）。"""
    return hash_password("s5t02-smoke-password")


@pytest.fixture(scope="session")
def issue_jwt():
    """token 签发器：issue(user_id) -> str（HMAC 亚毫秒级，无需缓存）。"""
    return issue_token
