"""七张核心表 ORM 模型（M-S1-T01）。

字段定义逐字照抄 00 文件第四节（表名/字段名/主键/外键不得增删改）：
users / workspaces / workspace_members / documents / document_versions /
chunks / messages。

设计要点：
- 主键全部 UUID；
- document_versions.status 四态 {staging, active, retired, failed}（D-1 决策，
  在 00 三态基础上扩展 failed）；
- chunks 不加 status 列（O-2）；tsv 为生成列（GENERATED ALWAYS ... STORED）
  + GIN 索引；embedding 为 pgvector 列 + HNSW 索引；
- 版本不可变（00 第四节核心不变量）：本模块不为 document_versions 提供任何
  update/delete 方法（S1-T04 以测试证明）；
- 业务表全部带 workspace_id 列（细则 1：每查询必带 workspace 过滤）。
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

# Vector(N) 的 N 写死在 DDL 中，运行时从配置读取（00 第五节：与 embedding 模型一致）
EMBEDDING_DIM = get_settings().EMBEDDING_DIM


class Base(DeclarativeBase):
    pass


class User(Base):
    """认证主体。"""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Workspace(Base):
    """隔离边界。"""

    __tablename__ = "workspaces"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkspaceMember(Base):
    """用户-工作区授权（多对多）。"""

    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(64))


class Document(Base):
    """文档元信息，每查询必带 workspace_id 过滤（细则 1）。"""

    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.workspace_id"))
    filename: Mapped[str] = mapped_column(String(512))
    # 激活指针：documents 中唯一可变字段（00 第四节）；指向 document_versions，
    # 循环外键用 use_alter 让建表 DDL 分两步执行
    active_version: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.version_id", use_alter=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentVersion(Base):
    """不可变版本：一经写入不允许 UPDATE/DELETE（00 第四节核心不变量）。

    本模块不提供任何 update/delete 方法或可变辅助路径（S1-T04 以测试证明）。
    """

    __tablename__ = "document_versions"

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.workspace_id"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.document_id"))
    version_no: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(String(1024))  # MinIO object key
    # 四态枚举（D-1）：staging / active / retired / failed
    status: Mapped[str] = mapped_column(String(16), default="staging")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Chunk(Base):
    """切块记录；向量与全文索引同表（00 第二节：PG 一库三职）。"""

    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv_gin", "tsv", postgresql_using="gin"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.workspace_id"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.version_id"))
    seq_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # 生成列：由 content 自动维护，插入/更新时不可显式写值
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Message(Base):
    """问答记录；thread_id 继承 W14 会话隔离（LangGraph thread_id 为字符串）。"""

    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.workspace_id"))
    thread_id: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
