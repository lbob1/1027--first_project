"""摄取状态查询路由（M-S2-T03，本项目第一个 API 路由）。

契约（00 文件 API 表）：
GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/status
→ 统一 {code, message, data}；data 含该文档各版本的 status（四态）。

- 身份：JWT 认证（M-S5-T02 起）——Authorization: Bearer →
  get_current_user_id 依赖注入，过渡身份头已退役（即使传入也不读取，
  身份唯一来源是 Bearer token）；
  角色判定只查 workspace_members（细则 3）；
- 隔离：workspace_id + document_id 直接进 SQL WHERE；非成员与不存在的
  文档一律 KN-404（细则 1，不泄露跨区存在性）；
- staging 版本附 pending 提示（S2-AC-5 不静默失败）：文案覆盖"处理中
  或 Worker 未运行"两种情况——**方案说明：不做 Celery inspect ping**，
  理由：每请求同步 inspect 有阻塞开销，且 T04 摄取任务落库后 status
  自然离开 staging，dev 阶段的歧义靠文案消除足够；
- 失败原因：document_versions 表无 reason 字段（00 第四节固定字段），
  failure_reason 恒为 null，仅 status=failed 显式暴露（细则 6：不静默）；
  若需持久化失败原因需表变更，届时先报告再动。
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id
from app.core.db import get_session
from app.core.errors import AppError
from app.models.models import Document, DocumentVersion, WorkspaceMember

log = logging.getLogger("app.api.status")

router = APIRouter(prefix="/api/v1/workspaces", tags=["ingestion"])

STAGING_NOTE = (
    "processing_or_pending: 摄取处理中，或 Worker 未运行"
    "（Windows 启动: uv run celery -A app.workers.celery_app worker --pool=solo -l info）"
)


def _require_member(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """成员判定（细则 1/3；非成员 KN-404，不泄露存在性）。"""
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")


@router.get("/{workspace_id}/documents/{document_id}/status")
def get_ingestion_status(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # M-S5-T02：JWT 依赖注入
):
    with get_session() as session:
        _require_member(session, user_id=user_id, workspace_id=workspace_id)
        doc = session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.document_id == document_id,
            )
        ).scalar_one_or_none()
        if doc is None:
            raise AppError("KN-404")
        versions = session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_no)
        ).scalars()
        data = {
            "document_id": str(document_id),
            "active_version": (
                str(doc.active_version) if doc.active_version else None
            ),
            "versions": [
                {
                    "version_id": str(v.version_id),
                    "version_no": v.version_no,
                    "status": v.status,
                    "failure_reason": None,  # 表无字段（见模块 docstring）
                    **({"note": STAGING_NOTE} if v.status == "staging" else {}),
                }
                for v in versions
            ],
        }
        log.info(
            "status queried document=%s workspace=%s", document_id, workspace_id
        )
        return {"code": "KN-000", "message": "ok", "data": data}
