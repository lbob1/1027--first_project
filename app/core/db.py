"""数据库基础设施（M-S1-T02）。

- engine/sessionmaker 懒创建（模块导入时绝不建连接）；
- get_session 为上下文管理器：成功 commit，异常 rollback，始终 close。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """懒创建全局 engine（首次调用才读配置并初始化连接池）。"""
    return create_engine(get_settings().DATABASE_URL)


@lru_cache
def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """会话上下文管理器。

    service 层函数显式接收 Session 参数（便于 S1-T04 隔离测试注入），
    事务边界由调用方通过本上下文管理。
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
