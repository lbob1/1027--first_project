"""SSE 流式问答端点（M-S3-T04）。

POST /api/v1/workspaces/{workspace_id}/chat，body {question, top_k?}：
- 成员判定：非 workspace 成员 → KN-404（细则 1，不泄露跨区存在性）；
  question 空 → KN-400；
- StreamingResponse（text/event-stream）事件序列：
  event: sources（JSON 溯源：六字段+rrf_score+relevance_score）→
  多个 event: token → event: budget（T04）→ event: trace（T06，done 前）
  → event: done；审批挂起 run 专有 event: approval_required（T05，
  随后 trace→done，无 token/budget）；
- 身份：JWT 认证（M-S5-T02 起）——Authorization: Bearer →
  get_current_user_id 依赖注入，过渡身份头已退役（即使传入也不读取，
  身份唯一来源是 Bearer token）——
  user_id 在流外解析完成才进 generator，SSE 流内部零改动；
- **messages 落库**：答案流出完成后同事务写一条（thread_id=本请求 uuid，
  role='assistant'，content=完整答案，citations=sources）；落库失败不影响
  已流出的答案（catch 后 log）；
- SSE 断连（客户端中断）不崩服务：generator 内 try/except GeneratorExit；
- 不打印 query/答案全文/凭据（细则 9），日志只记事件条数与落库结果。
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth import get_current_user_id
from app.core.db import get_session
from app.core.errors import AppError
from app.models.models import Message, WorkspaceMember
from app.graphs.agent_graph import stream_answer  # M-S4-T03：Agent Graph（Router）切换

router = APIRouter(prefix="/api/v1")  # 与 status/documents 路由同前缀
log = logging.getLogger("app.api.chat")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    thread_id: str | None = Field(default=None)  # 传入则复用会话历史（多轮指代）
    # M-S4-T05：None=新请求；bool=恢复删除审批（thread_id 必传，缺失 KN-400）
    confirm: bool | None = Field(default=None)


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
    user_id: uuid.UUID = Depends(get_current_user_id),  # M-S5-T02：JWT 依赖注入
):
    if not body.question.strip():
        raise AppError("KN-400")
    with get_session() as session:
        _require_member(session, user_id=user_id, workspace_id=workspace_id)

    thread_id = body.thread_id or uuid.uuid4().hex

    # 预取第一个事件：router/retrieve 阶段的预算超限（KN-429）与恢复请求
    # 校验（KN-400）在此抛出——此时 StreamingResponse 尚未发出任何字节，
    # AppError 冒泡到全局异常处理器返回对应 HTTP 状态码 JSON。
    gen = stream_answer(
        workspace_id, body.question,
        thread_id=thread_id, top_k=body.top_k,
        user_id=user_id, confirm=body.confirm,  # T05：删除审批链路
    )
    first = next(gen)
    tokens: list[str] = []
    sources: list[dict] | None = None
    suspended = False  # T05：本 run 以 approval_required 挂起（不落库答案行）

    def event_stream():
        try:
            payload_iter = iter([first])
            for payload in payload_iter:
                yield _dispatch(payload)
            for payload in gen:
                yield _dispatch(payload)
            # 问答完成 → messages 落库（失败不影响已流出的答案）；
            # 一条记录同时承载问题与完整答案（任务书 T04 要求）；
            # 审批挂起 run 不落答案行（答案尚未产生，审计行由 ApprovalManager 写）
            if not suspended:
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
        except AppError as exc:
            # 生成中途预算超限（第二种流出形态）：SSE 已流出无法改状态码，
            # 追加 event: error 后正常收尾 done（服务不崩，下一请求正常）
            log.warning("run 中断 thread_id=%s code=%s", thread_id, exc.code)
            yield _sse("error", {"code": exc.code, "message": exc.message})
            yield _sse("done", {})
        except GeneratorExit:  # 客户端断连：记日志后正常关闭，不崩服务
            log.warning("SSE 客户端断连 thread_id=%s tokens=%d", thread_id, len(tokens))
            raise

    def _dispatch(payload: dict) -> str:
        nonlocal sources, suspended
        if "approval_required" in payload:  # T05：删除审批挂起（本 run 无 token/budget）
            suspended = True
            return _sse("approval_required", payload["approval_required"])
        if "trace" in payload:  # T06：结构化 Trace（done 前最后事件，转发即可）
            return _sse("trace", payload["trace"])
        if "sources" in payload:
            sources = payload["sources"]
            return _sse("sources", {"sources": sources})
        if "budget" in payload:  # T04：预算观测事件（T06 Trace 复用）
            return _sse("budget", payload["budget"])
        tokens.append(payload["token"])
        return _sse("token", {"token": payload["token"]})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
