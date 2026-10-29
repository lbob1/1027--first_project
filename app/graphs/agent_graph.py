"""Agent Graph：Router 模式单 Agent + 工具（M-S4-T03，M-S4-T04 接预算）。

S4 控制层组件接线：ModelGateway（模型调用）、ContextManager（上下文装配）、
ToolRegistry（工具执行）、PolicyEngine（策略判定）、BudgetManager（预算，
T04 接入）——只消费不复制逻辑。

图结构（三节点两分支）：
    START → router ──(need_retrieval=true)──→ retrieve → generate → END
                └─────(false，闲聊)───────────→ generate → END

- router：Gateway 调 CHAT_MODEL 结构化判断是否需要查知识库；**解析失败
  保守默认 true**（多检索一次的代价小于答非所问）；
- retrieve：PolicyEngine.check 放行 → ToolRegistry.execute 调 hybrid_search
  （框架层注入 workspace_id，细则 1）；policy 拦截时 hits=[] 并 log.warning
  记拦截 reason（供观测，正常只读工具不会被拦）；
- generate：load_history(thread_id) → ContextManager.build 装配 →
  Gateway.chat(stream=True) 逐 token 经 custom writer 发出；事件协议：
  {"sources": hits} → {"token": ...}×N → **{"budget": snapshot}（T04）**。

**run 级实例（M-S4-T04 修正既有隐患）**：T01 时 _gateway 是模块级单例，
其 total_tokens 会跨 run 累加——与"本轮 run 的 token 计数"语义偏离。
现改为 stream_answer 每 run 创建 ModelGateway + BudgetManager 实例，经
graph.stream 的 config["configurable"] 注入节点；**图仍保持模块级编译
常量**（不每次请求重建），运行时差异全部走 config 注入——这是 LangGraph
的标准做法。Gateway client 经 _get_client 懒创建共享，无连接浪费。

**预算检查点（T04）**：router/retrieve 每次 Gateway 调用后精确校验
（usage 已回）；generate 流开始前预检 + 流中按"字符数≈token 数"近似
估算校验（中文 1 字 ≈ 1 token，偏高估——宁严勿松，理由：流式中途拿不到
精确 usage，尾块才来）；流结束后以 Gateway 精确值终校。超限抛 KN-429
中断本 run。两种流出形态（docstring 取舍，chat.py 配合）：
- 流出前超限（router/retrieve 阶段）：AppError 从 generator 预取阶段冒泡
  到 API 层 → HTTP 429 + KN-429 JSON；
- 生成中途超限：SSE 已流出无法改状态码 → chat.py 捕获后发 event: error
  （code=KN-429）再正常收尾 done。

消息内容/查询词/凭据不入日志（细则 9）；模块导入零网络请求。
"""

import logging
import uuid
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END

from app.core.budget import BudgetManager
from app.core.context import ContextManager, build_evidence_block, load_history
from app.core.db import get_session
from app.core.errors import AppError
from app.core.gateway import ModelGateway
from app.core.policy import PolicyEngine
from app.core.tool_registry import build_default_registry

log = logging.getLogger("app.graphs.agent_graph")

_ROUTER_SYSTEM = (
    "你在为企业知识库问答系统做路由判断：用户的问题是否应该检索知识库。"
    "只要问题涉及任何知识点、概念、业务或事实内容（哪怕看起来是通用问题），"
    "为了给出有依据的回答就应检索知识库，回答 true。"
    "仅当问题是纯闲聊（问候、寒暄、询问你的身份）、或明确与任何资料内容无关时，回答 false。"
    "拿不准时回答 true——多检索一次的代价小于答非所问。只回答 true 或 false。"
)

# 以下三个无状态/只读组件保持模块级共享；gateway 必须每 run 新建（用量隔离，见 docstring）
_registry = build_default_registry()
_policy = PolicyEngine()
_context = ContextManager()


class AgentState(TypedDict):
    question: str
    workspace_id: uuid.UUID | None
    thread_id: str | None
    identity: str
    top_k: int
    need_retrieval: bool
    hits: list[dict[str, Any]]
    answer: str


# router 暂与生成共用 CHAT_MODEL（Gateway 内部回落）；后续如需小模型独立调优再引入常量


def _router(state: AgentState, config) -> dict:
    """LLM 判断是否检索；解析失败/异常一律保守 true。"""
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    try:
        resp = gw.chat(
            [{"role": "system", "content": _ROUTER_SYSTEM},
             {"role": "user", "content": state["question"]}],
            temperature=0.0,
        )
        budget.check_token(gw.total_tokens)  # T04：router 用量精确校验
        text = (resp.choices[0].message.content or "").strip().lower()
        need = text.startswith("true")
        if not need and not text.startswith("false"):
            need = True  # 解析失败保守 true
    except Exception as exc:  # 路由失败不崩问答（KN-429 之外的预算异常如实上抛）
        if isinstance(exc, AppError):
            raise
        log.warning("router 判断失败（%s），保守走检索路径", type(exc).__name__)
        need = True
    log.info("router need_retrieval=%s", need)
    return {"need_retrieval": need}


def _retrieve(state: AgentState, config) -> dict:
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    spec = _registry.get("hybrid_search")
    arguments = {"query": state["question"], "top_k": state["top_k"]}
    decision = _policy.check(spec, arguments=arguments)
    if not decision.allowed:
        # 正常只读工具不会被拦；拦截属策略异常，hits 置空并记 reason 供观测
        log.warning("policy 拦截检索工具 tool=%s reason=%s", spec.name, decision.reason)
        return {"hits": []}
    budget.record_tool_call()  # T04：调工具前计数（超限 KN-429 在执行前拦截）
    with get_session() as session:
        result = _registry.execute(
            session, name=spec.name, arguments=arguments,
            workspace_id=state["workspace_id"],
        )
    hits = result.get("results", [])
    log.info("retrieve hits=%d", len(hits))
    return {"hits": hits}


def _identity_for(state: AgentState) -> str:
    """identity 组装：闲聊路径（无检索）追加场景说明——RAG 约束 prompt 要求
    "仅依据资料回答"，闲聊时需豁免该约束让助手正常对话（context.py 不改，
    经 identity 参数注入场景说明）。"""
    base = state.get("identity", "")
    if not state["hits"]:
        chat_hint = "当前为无检索的闲聊场景：请正常回答用户问题，无需受仅依据资料的约束。"
        return f"{base}；{chat_hint}" if base else chat_hint
    return base


def _generate(state: AgentState, config) -> dict:
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    writer = get_stream_writer()
    writer({"sources": state["hits"]})  # 事件协议：sources 先行（闲聊为空数组）
    with get_session() as session:
        history = (
            load_history(session, thread_id=state["thread_id"])
            if state.get("thread_id") else []
        )
    messages = _context.build(
        identity=_identity_for(state),
        history=history,
        evidence=build_evidence_block(state["hits"]),
        question=state["question"],
    )
    budget.check_token(gw.total_tokens)  # 流开始前预检（精确值）
    parts: list[str] = []
    for tok in gw.chat(messages, stream=True):
        parts.append(tok)
        writer({"token": tok})
        # 流中校验：usage 尾块才来，按"字符数≈token 数"估算生成部分（中文 1:1，
        # 偏高估宁严勿松——超限即中断，避免预算被动穿透）
        budget.check_token(gw.total_tokens + len("".join(parts)))
    answer = "".join(parts)
    budget.check_token(gw.total_tokens)  # 流结束后以尾块精确 usage 终校
    writer({"budget": budget.snapshot()})  # T04：观测事件（T06 Trace 复用）
    return {"answer": answer}


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("router", _router)
    g.add_node("retrieve", _retrieve)
    g.add_node("generate", _generate)
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: "retrieve" if s["need_retrieval"] else "generate",
        {"retrieve": "retrieve", "generate": "generate"},
    )
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


graph = _build_graph()  # 模块级编译常量，不每次请求重建


def stream_answer(
    workspace_id: uuid.UUID,
    question: str,
    *,
    thread_id: str | None = None,
    identity: str = "",
    top_k: int = 5,
    budget: BudgetManager | None = None,
):
    """Agent 问答流：{'sources'} → {'token'}×N → {'budget'}。

    每 run 新建 ModelGateway（用量隔离，client 懒创建共享）与 BudgetManager
    （无参则用模块默认限额）；budget 参数供测试/部署层注入小限额。"""
    gateway = ModelGateway()
    budget = budget or BudgetManager()
    yield from graph.stream(
        {"question": question, "workspace_id": workspace_id, "thread_id": thread_id,
         "identity": identity, "top_k": top_k, "need_retrieval": False,
         "hits": [], "answer": ""},
        config={"configurable": {"gateway": gateway, "budget": budget}},
        stream_mode="custom",
    )
