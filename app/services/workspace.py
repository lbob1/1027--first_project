"""workspace 增/查/删 service（M-S1-T02）。

- 身份以参数传入（O-7，S5 前无 JWT）；角色一律查 workspace_members 表判定
  （细则 3），不信任调用方自报角色；
- 非成员访问返回 KN-404（不泄露 workspace 是否存在，细则 1）；
  成员但角色不足返回 KN-403；
- 删除为阻断式（D-2：本层无审批包装，S4-T05 才加；子资源非空时 KN-409，
  不做隐式级联——本轮已确认）；list 不分页（本轮已确认）；
- service 函数显式接收 Session，由调用方经 app.core.db.get_session() 管理事务；
  日志只输出 ID 等非敏感值。
"""

import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import Document, User, Workspace, WorkspaceMember

log = logging.getLogger("app.services.workspace")

OWNER_ROLE = "owner"  # 创建者角色（约定值；细则 3：角色只存数据库）


def _require_member(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> WorkspaceMember:
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")
    return member


def _require_role(member: WorkspaceMember, allowed: set[str]) -> None:
    if member.role not in allowed:
        raise AppError("KN-403")


def create_workspace(
    session: Session, *, user_id: uuid.UUID, name: str
) -> Workspace:
    """创建 workspace；创建者登记为 owner 成员（细则 3）。"""
    if session.get(User, user_id) is None:
        raise AppError("KN-404")
    ws = Workspace(name=name, owner_user_id=user_id)
    session.add(ws)
    session.flush()  # 先取 workspace_id 供成员表引用
    session.add(
        WorkspaceMember(workspace_id=ws.workspace_id, user_id=user_id, role=OWNER_ROLE)
    )
    log.info("workspace created id=%s by user=%s", ws.workspace_id, user_id)
    return ws


def get_workspace(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> Workspace:
    _require_member(session, user_id=user_id, workspace_id=workspace_id)
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise AppError("KN-404")
    return ws


def list_workspaces(session: Session, *, user_id: uuid.UUID) -> list[Workspace]:
    """返回用户为成员的全部 workspace（S1 不分页，已确认）。"""
    return list(
        session.execute(
            select(Workspace)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.workspace_id,
            )
            .where(WorkspaceMember.user_id == user_id)
        ).scalars()
    )


def delete_workspace(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """阻断式删除：仅 owner 可删；workspace 下仍有文档时 KN-409（本轮已确认）。"""
    member = _require_member(session, user_id=user_id, workspace_id=workspace_id)
    _require_role(member, {OWNER_ROLE})
    doc_count = session.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.workspace_id == workspace_id)
    ).scalar_one()
    if doc_count:
        raise AppError("KN-409", "workspace 下仍有文档，禁止删除（阻断式）")
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise AppError("KN-404")
    session.execute(
        delete(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    session.delete(ws)
    log.info("workspace deleted id=%s by user=%s", workspace_id, user_id)
