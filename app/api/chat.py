"""SSE 流式问答端点（M-S3-T04）。

POST /api/v1/workspaces/{workspace_id}/chat，body {question, top_k?}：
- 成员判定：非 workspace 成员 → KN-404（细则 1，不泄露跨区存在性）；
  question 空 → KN-400；
- StreamingResponse（text/event-stream）三段事件：
  event: sources（JSON 溯源：六字段+rrf_score+relevance_score）→
  多个 event: token → event: done；
- X-User-ID dev 过渡头（S5 换 JWT，与既有 API 一致）；
- **messages 落库**：答案流出完成后同事务写一条（thread_id=本请求 uuid，
  role='assistant'，content=完整答案，citations=sources）；落库失败不影响
  已流出的答案（catch 后 log）；
- SSE 断连（客户端中断）不崩服务：generator 内 try/except GeneratorExit；
- 不打印 query/答案全文/凭据（细则 9），日志只记事件条数与落库结果。
"""

import json
import logging
import uuid

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import get_session
from app.core.errors import AppError
from app.models.models import Message, WorkspaceMember
from app.graphs.rag_graph import stream_answer

router = APIRouter(prefix="/api/v1")  # 与 status/documents 路由同前缀
log = logging.getLogger("app.api.chat")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def _require_member(session, *, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
    member = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError("KN-404")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/workspaces/{workspace_id}/chat")
async def chat(
    workspace_id: uuid.UUID,
    body: ChatRequest,
    x_user_id: str = Header(...),
):
    if not body.question.strip():
        raise AppError("KN-400")
    user_id = uuid.UUID(x_user_id)
    with get_session() as session:
        _require_member(session, user_id=user_id, workspace_id=workspace_id)

    thread_id = uuid.uuid4().hex

    def event_stream():
        tokens: list[str] = []
        sources: list[dict] | None = None
        try:
            for payload in stream_answer(workspace_id, body.question, body.top_k):
                if "sources" in payload:
                    sources = payload["sources"]
                    yield _sse("sources", {"sources": sources})
                else:
                    tokens.append(payload["token"])
                    yield _sse("token", {"token": payload["token"]})
            # 问答完成 → messages 落库（失败不影响已流出的答案）；
            # 一条记录同时承载问题与完整答案（任务书 T04 要求）
            try:
                with get_session() as session:
                    session.add(
                        Message(
                            workspace_id=workspace_id,
                            thread_id=thread_id,
                            role="assistant",
                            content=f"问题：{body.question}\n答案：{''.join(tokens)}",
                            citations=sources,
                        )
                    )
                log.info("message saved thread_id=%s tokens=%d", thread_id, len(tokens))
            except Exception:
                log.exception("messages 落库失败 thread_id=%s（答案不受影响）", thread_id)
            yield _sse("done", {})
        except GeneratorExit:  # 客户端断连：记日志后正常关闭，不崩服务
            log.warning("SSE 客户端断连 thread_id=%s tokens=%d", thread_id, len(tokens))
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")
