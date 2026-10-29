"""Agent Graph：Router 模式单 Agent + 工具（M-S4-T03/T04，T05 接审批）。

S4 控制层组件接线：ModelGateway（模型调用）、ContextManager（上下文装配）、
ToolRegistry（工具执行）、PolicyEngine（策略判定）、BudgetManager（预算）、
ApprovalManager（审批语义件）——只消费不复制逻辑。

图结构（Router 三分类，四分支）：
    START → router ──(search)──→ retrieve → generate → END
                ├────(chat)──────────────→ generate → END
                └────(delete)──→ delete_prepare → approve_and_delete → generate → END

- router：Gateway 调 CHAT_MODEL 结构化三分类 chat|search|delete；**解析
  失败保守 search**（多检索一次的代价小于答非所问，删除误判则宁可少删）；
- retrieve：PolicyEngine.check 放行 → ToolRegistry.execute 调 hybrid_search
  （框架层注入 workspace_id，细则 1）；policy 拦截时 hits=[] 并 log.warning；
- **delete_prepare（T05）**：Gateway 从问题提取目标文件名（LLM 不可控
  document_id，按文件名定位）→ PolicyEngine.check（delete_document
  read_only=False → needs_approval）→ ApprovalManager.build_interrupt_payload
  → writer 发 {"approval_required": payload} → audit(pending) 落库 → return。
  **与本节点分离的职责**：提取失败/policy 拦截直接置 tool_notice 取消审批
  （fail-safe，不删除任何东西），经条件边直达 generate；
- **approve_and_delete（T05）**：**interrupt(payload) 是节点第一行**——
  LangGraph 恢复语义为"重跑本节点"，interrupt 前不能有副作用（否则恢复时
  重复审计/重复执行），这就是 delete 拆两节点的原因：挂起审计与提取留在
  prepare（checkpoint 已完成不重跑），本节点恢复时 interrupt() 返回
  resume 值 → parse_confirm：True → audit(approved) → record_tool_call →
  registry.execute 删除（注入 workspace+user_id，service 层成员判定与
  KN-409 阻断语义全保留）；False/解析失败 → audit(rejected) 不执行；
  结果经 tool_notice 交 generate 转述；
- generate：load_history(thread_id) 过滤审计行 → ContextManager.build 装配
  → Gateway.chat(stream=True) 逐 token 经 custom writer 发出；事件协议：
  {"sources": hits} → {"token": ...}×N → {"budget": snapshot}。

**run 级实例（M-S4-T04）**：stream_answer 每 run 创建 ModelGateway +
BudgetManager 经 graph.stream 的 config["configurable"] 注入节点；图保持
模块级编译常量。**Checkpointer（T05）**：InMemorySaver 模块级——进程内
状态、重启即失（挂起中的审批重启后不可恢复，docstring 如实注明；S6 部署
轮可换 PostgresSaver 持久化）。恢复请求必须携带 thread_id 定位 checkpoint；
**边界行为（探针实证）**：对无 checkpoint / 无挂起的 thread 发
Command(resume)，LangGraph 不报错而是从头重跑图（会重复挂起）——故
stream_answer 恢复路径先 get_state 预检 pending interrupt，缺失即 KN-400。

**预算检查点（T04）**：router/提取/检索每次 Gateway 调用后精确校验；
generate 流前预检 + 流中字符估算 + 流后终校；删除执行前 record_tool_call。
超限抛 KN-429 两种流出形态见 chat.py（流出前→HTTP 429；中途→event: error）。

**RunTracer（T06）**：stream_answer 每 run 创建 RunTracer（经 config
["configurable"]["tracer"] 注入节点）：节点入口 mark（链式结算逐节点
耗时）、工具结果 record_tool（参数只记 key 集合）、特殊事件 record_event
（approval_pending/approval_approved/approval_rejected、budget_exceeded、
run_interrupted、policy_blocked、router_fallback）。run 结束（正常/挂起/
中断均算结束）统一 finish_and_log：log.info 一行结构化 JSON + yield
{"trace"} → SSE event: trace（done 前；budget 保持独立事件，Trace 为
超集）。**流出前超限（HTTP 429 形态）不 yield trace 只落日志**——保持
T04 实证的"headers 未发→纯 JSON 429"行为。**观测缺失项**：rerank 不在
本图链路（retrieve 走 hybrid_search 工具，T03 起未接 rerank），降级无
观测点，本 run 能拿到什么记什么。

消息内容/查询词/凭据不入日志（细则 9）；Trace 字段白名单见 trace.py；
模块导入零网络请求。
"""

import logging
import uuid
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

from app.core.approval import (
    ApprovalManager,
    EVENT_PENDING,
    EVENT_APPROVED,
    EVENT_REJECTED,
)
from app.core.budget import BudgetManager
from app.core.context import ContextManager, build_evidence_block, load_history
from app.core.db import get_session
from app.core.errors import AppError
from app.core.gateway import ModelGateway
from app.core.policy import PolicyEngine
from app.core.tool_registry import build_default_registry
from app.core.trace import RunTracer, finish_and_log, safe_error_type

log = logging.getLogger("app.graphs.agent_graph")

_ROUTER_SYSTEM = (
    "你在为企业知识库问答系统做意图分类，判断用户消息属于哪一类：\n"
    "chat：纯闲聊（问候、寒暄、询问你的身份）、或明确与任何资料内容无关的消息；\n"
    "search：资料问答——只要问题涉及任何知识点、概念、业务或事实内容"
    "（哪怕看起来是通用问题），为了给出有依据的回答就需要检索知识库；\n"
    "delete：删除文档类操作——用户明确要求删除/移除某个文档或文件。\n"
    "拿不准时回答 search——多检索一次的代价小于答非所问，删除误判宁可少删。"
    "只回答 chat、search 或 delete 三个词之一。"
)

_EXTRACT_SYSTEM = (
    "从用户消息中提取要删除的文档文件名。只输出文件名本身（例如 doc.txt），"
    "不要包含引号、路径或任何其他内容；若无法确定具体文件名，只输出 NONE。"
)

# 以下组件无状态/只读/进程内：registry/policy/context/approval 模块级共享；
# gateway 每 run 新建（用量隔离）；checkpointer 进程内（重启即失，见 docstring）
_registry = build_default_registry()
_policy = PolicyEngine()
_context = ContextManager()
_approval = ApprovalManager()
_checkpointer = InMemorySaver()


class AgentState(TypedDict):
    question: str
    workspace_id: uuid.UUID | None
    thread_id: str | None
    user_id: uuid.UUID | None  # T05：框架注入的请求用户（删除工具成员判定用）
    identity: str
    top_k: int
    intent: str  # T05：router 三分类 chat|search|delete
    hits: list[dict[str, Any]]
    answer: str
    tool_notice: str  # T05：delete 分支结果说明（generate 转述，优先于闲聊豁免）
    delete_filename: str  # T05：prepare 提取的目标文件名
    approval_payload: dict[str, Any]  # T05：挂起载荷（空 dict = 未进入审批）


def _router(state: AgentState, config) -> dict:
    """LLM 三分类；解析失败/异常一律保守 search。"""
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    tracer = config["configurable"].get("tracer")  # T06
    if tracer:
        tracer.mark("router")
    try:
        resp = gw.chat(
            [{"role": "system", "content": _ROUTER_SYSTEM},
             {"role": "user", "content": state["question"]}],
            temperature=0.0,
        )
        budget.check_token(gw.total_tokens)  # T04：router 用量精确校验
        text = (resp.choices[0].message.content or "").strip().lower()
        if text.startswith("delete"):
            intent = "delete"
        elif text.startswith("chat"):
            intent = "chat"
        else:
            intent = "search"  # 解析失败/异常值保守 search
    except Exception as exc:  # 路由失败不崩问答（KN-429 之外的预算异常如实上抛）
        if isinstance(exc, AppError):
            raise
        log.warning("router 判断失败（%s），保守走检索路径", type(exc).__name__)
        if tracer:  # T06：router 兜底事件（只记异常类型名，细则 9）
            tracer.record_event("router_fallback", {"error_type": type(exc).__name__})
        intent = "search"
    log.info("router intent=%s", intent)
    return {"intent": intent}


def _retrieve(state: AgentState, config) -> dict:
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    tracer = config["configurable"].get("tracer")  # T06
    if tracer:
        tracer.mark("retrieve")
    spec = _registry.get("hybrid_search")
    arguments = {"query": state["question"], "top_k": state["top_k"]}
    decision = _policy.check(spec, arguments=arguments)
    if not decision.allowed:
        # 正常只读工具不会被拦；拦截属策略异常，hits 置空并记 reason 供观测
        log.warning("policy 拦截检索工具 tool=%s reason=%s", spec.name, decision.reason)
        if tracer:  # T06：策略拦截事件（reason 为固定策略文案，无内容）
            tracer.record_event("policy_blocked", {"tool": spec.name, "reason": decision.reason})
        return {"hits": []}
    budget.record_tool_call()  # T04：调工具前计数（超限 KN-429 在执行前拦截）
    with get_session() as session:
        result = _registry.execute(
            session, name=spec.name, arguments=arguments,
            workspace_id=state["workspace_id"],
        )
    hits = result.get("results", [])
    if tracer:  # T06：工具结果（参数只记 key 集合，错误只记 KN 码）
        err = result.get("error")
        tracer.record_tool(
            spec.name, ok=err is None, result_count=0 if err else len(hits),
            error_type=safe_error_type(err) if err else None,
            arg_keys=list(arguments),
        )
    log.info("retrieve hits=%d", len(hits))
    return {"hits": hits}


def _delete_prepare(state: AgentState, config) -> dict:
    """删除分支准备：提取文件名 → policy 判定 → 发审批请求 + 挂起审计。

    本节点在 checkpoint 中"已完成"后不再重跑（interrupt 在下一节点），
    提取 LLM 调用与 pending 审计行不会因恢复而重复。取消类分支返回空
    approval_payload，经条件边直达 generate（fail-safe：不删除任何东西）。
    """
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    tracer = config["configurable"].get("tracer")  # T06
    if tracer:
        tracer.mark("delete_prepare")
    writer = get_stream_writer()
    try:
        resp = gw.chat(
            [{"role": "system", "content": _EXTRACT_SYSTEM},
             {"role": "user", "content": state["question"]}],
            temperature=0.0,
        )
        budget.check_token(gw.total_tokens)  # 提取调用计入本 run 预算
        filename = (resp.choices[0].message.content or "").strip().strip("\"'。 ")
    except Exception as exc:
        if isinstance(exc, AppError):
            raise
        log.warning("delete 文件名提取失败（%s）", type(exc).__name__)
        filename = ""
    if not filename or filename.upper() == "NONE":
        log.info("delete 未提取到文件名，取消审批")
        return {"tool_notice": (
            "系统执行结果：未能从用户消息中确定要删除的文件名，未执行任何删除操作。"
            "请直接据此回复用户，请其明确指出要删除的文件名；不要提及资料或检索。"
        ), "delete_filename": "", "approval_payload": {}}
    spec = _registry.get("delete_document")
    arguments = {"filename": filename}
    decision = _policy.check(spec, arguments=arguments)
    if decision.allowed or "审批" not in decision.reason:
        # allowed 理论不可达（read_only=False 恒 needs_approval）；参数校验
        # 类拦截也不应发生（filename 由本节点构造）——均按取消处理
        log.warning("delete 分支未进入审批 tool=%s reason=%s", spec.name, decision.reason)
        return {"tool_notice": (
            f"系统执行结果：删除操作未获审批路径，已取消（原因：{decision.reason}）。"
            "请直接据此回复用户；不要提及资料或检索。"
        ), "delete_filename": "", "approval_payload": {}}
    payload = _approval.build_interrupt_payload(spec, arguments, state["workspace_id"])
    writer({"approval_required": payload})  # 事件协议：客户端据此发起 confirm
    with get_session() as session:
        _approval.audit(
            session, workspace_id=state["workspace_id"],
            thread_id=state["thread_id"] or "", event=EVENT_PENDING, payload=payload,
        )
    if tracer:  # T06：挂起事件（payload 含 filename 参数值不入 Trace，只记工具名）
        tracer.record_event("approval_pending", {"tool": spec.name, "arg_keys": sorted(arguments)})
    log.info("delete 审批挂起 filename_key=%s", sorted(payload.keys()))
    return {"delete_filename": filename, "approval_payload": payload}


def _approve_and_delete(state: AgentState, config) -> dict:
    """审批恢复与删除执行：interrupt 是第一行（恢复重跑零重复副作用）。

    恢复后 parse_confirm：True → audit(approved) → record_tool_call →
    registry.execute（注入 workspace+user_id）；False/解析失败 →
    audit(rejected) 不执行。结果一律经 tool_notice 交 generate 转述。
    """
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    tracer = config["configurable"].get("tracer")  # T06
    if tracer:
        tracer.mark("approve_and_delete")
    payload = state.get("approval_payload") or {}
    resume = interrupt(payload)  # 挂起；恢复时本行返回 confirm 值
    approved = _approval.parse_confirm(resume)
    event = EVENT_APPROVED if approved else EVENT_REJECTED
    with get_session() as session:
        _approval.audit(
            session, workspace_id=state["workspace_id"],
            thread_id=state["thread_id"] or "", event=event, payload=payload,
        )
    if tracer:  # T06：审批结论事件（只记工具名，不含 filename 参数值）
        tracer.record_event(
            "approval_approved" if approved else "approval_rejected",
            {"tool": payload.get("tool", ""), "arg_keys": ["filename"]},
        )
    filename = payload.get("filename", "")
    if not approved:
        log.info("delete 审批拒绝")
        return {"tool_notice": (
            f"系统执行结果：用户已拒绝删除「{filename}」的操作，文档未被删除。"
            "请直接据此回复用户，告知文档未被删除；如确认要删除可重新发起并在"
            "收到确认请求后同意。不要提及资料或检索。"
        )}
    budget.record_tool_call()  # 执行前计数（超限 KN-429，语义与 T04 一致）
    arguments = {"filename": filename}
    with get_session() as session:
        result = _registry.execute(
            session, name="delete_document", arguments=arguments,
            workspace_id=state["workspace_id"], user_id=state.get("user_id"),
        )
    if "error" in result:
        # 定位不到（隔离）/KN-409 有版本阻断等：转述不崩（删除语义见 fn docstring）
        log.info("delete 执行未成功 err_keys=%s", sorted(result.keys()))
        if tracer:  # T06：失败工具记录（错误只记 KN 码，消息正文含文件名不入）
            tracer.record_tool("delete_document", ok=False, result_count=0,
                               error_type=safe_error_type(result["error"]),
                               arg_keys=sorted(arguments))
        return {"tool_notice": (
            f"系统执行结果：删除「{filename}」未成功，原因：{result['error']}。"
            "请直接据此回复用户，告知删除失败及上述原因；不要提及资料或检索。"
        )}
    if tracer:
        tracer.record_tool("delete_document", ok=True, result_count=1,
                           arg_keys=sorted(arguments))
    log.info("delete 执行成功")
    return {"tool_notice": (
        f"系统执行结果：文档「{filename}」已成功删除。"
        "请直接据此回复用户，简短告知删除已完成；不要提及资料或检索。"
    )}


def _identity_for(state: AgentState) -> str:
    """identity 组装：tool_notice（删除分支结果）最优先——文案为明确指令式
    （"请直接据此回复，不要提及资料"），对抗 RAG 约束压制（诊断实证：
    陈述式 notice 会被模型当作资料复述而非转述）；其次闲聊路径（无检索）
    追加场景说明——RAG 约束 prompt 要求"仅依据资料回答"，闲聊/删除告知
    场景需豁免该约束（context.py 不改，经 identity 注入）。"""
    base = state.get("identity", "")
    notice = state.get("tool_notice") or ""
    if notice:
        return f"{base}；{notice}" if base else notice
    if not state["hits"]:
        chat_hint = "当前为无检索的闲聊场景：请正常回答用户问题，无需受仅依据资料的约束。"
        return f"{base}；{chat_hint}" if base else chat_hint
    return base


def _generate(state: AgentState, config) -> dict:
    gw, budget = config["configurable"]["gateway"], config["configurable"]["budget"]
    tracer = config["configurable"].get("tracer")  # T06
    if tracer:
        tracer.mark("generate")
    writer = get_stream_writer()
    writer({"sources": state["hits"]})  # 事件协议：sources 先行（闲聊/删除为空数组）
    with get_session() as session:
        history = (
            load_history(session, thread_id=state["thread_id"])
            if state.get("thread_id") else []
        )
    # 审计行（role="system" 的 [APPROVAL] 记录）不进对话上下文——context.py
    # 本体不可改（T05 硬约束），在消费侧过滤
    history = [m for m in history if m.get("role") != "system"]
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
    g.add_node("delete_prepare", _delete_prepare)
    g.add_node("approve_and_delete", _approve_and_delete)
    g.add_node("generate", _generate)
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: s["intent"],
        {"search": "retrieve", "chat": "generate", "delete": "delete_prepare"},
    )
    g.add_edge("retrieve", "generate")
    # 取消类分支（提取失败/policy 拦截）approval_payload 为空 → 直达 generate
    g.add_conditional_edges(
        "delete_prepare",
        lambda s: "approve_and_delete" if s.get("approval_payload") else "generate",
        {"approve_and_delete": "approve_and_delete", "generate": "generate"},
    )
    g.add_edge("approve_and_delete", "generate")
    g.add_edge("generate", END)
    return g.compile(checkpointer=_checkpointer)  # T05：interrupt 恢复依赖 checkpoint


graph = _build_graph()  # 模块级编译常量，不每次请求重建


def stream_answer(
    workspace_id: uuid.UUID,
    question: str,
    *,
    thread_id: str | None = None,
    identity: str = "",
    top_k: int = 5,
    budget: BudgetManager | None = None,
    user_id: uuid.UUID | None = None,
    confirm: bool | None = None,
):
    """Agent 问答流：{'sources'} → {'token'}×N → {'budget'} → {'trace'}；
    delete 分支挂起 run：{'approval_required'} → {'trace'}（无 token/budget）。

    每 run 新建 ModelGateway（用量隔离，client 懒创建共享）与 BudgetManager
    （无参则用模块默认限额）；budget 参数供测试/部署层注入小限额。

    confirm（T05）：None=新请求；bool=恢复审批请求——thread_id 必传
    （缺失 KN-400），且该 thread 须有挂起的 interrupt（get_state 预检，
    缺失 KN-400；LangGraph 对无挂起 thread 的 resume 不报错而是重跑图，
    预检避免重复挂起/重复审计）。恢复经 Command(resume=confirm) 从
    checkpoint 继续，gateway/budget 为本 run 新实例（run 级用量隔离）。

    trace（T06）：每 run 配对创建 RunTracer 注入节点；run 结束（正常/
    挂起/中断均算结束）统一 finish_and_log——log.info 一行 JSON + yield
    {"trace"}（done 前）。中断（AppError）路径：已 yield 过事件才补发
    trace（SSE 已流出无法改状态码）；**流出前超限不 yield**——保持 T04
    实证的"headers 未发→HTTP 429 纯 JSON"行为，trace 只落日志。
    """
    gateway = ModelGateway()
    budget = budget or BudgetManager()
    if confirm is not None and not thread_id:
        raise AppError("KN-400", "恢复审批请求必须携带 thread_id")
    tid = thread_id or uuid.uuid4().hex
    tracer = RunTracer()  # T06：与 gateway/budget 同生命周期
    tracer.start(tid, workspace_id)
    config = {"configurable": {"gateway": gateway, "budget": budget,
                               "thread_id": tid, "tracer": tracer}}
    if confirm is None:
        streams = graph.stream(
            {"question": question, "workspace_id": workspace_id, "thread_id": tid,
             "user_id": user_id, "identity": identity, "top_k": top_k,
             "intent": "search", "hits": [], "answer": "",
             "tool_notice": "", "delete_filename": "", "approval_payload": {}},
            config=config,
            stream_mode="custom",
        )
    else:
        # 恢复路径：预检 pending interrupt（见 docstring 边界行为说明）
        snap = graph.get_state(config)
        if not any(t.interrupts for t in snap.tasks):
            log.warning("审批恢复预检失败 thread_id=%s（无挂起）", thread_id)
            raise AppError("KN-400", "该会话没有待确认的删除审批")
        streams = graph.stream(Command(resume=confirm), config=config, stream_mode="custom")

    emitted = False
    try:
        for ev in streams:  # graph.stream 为惰性生成器，异常在迭代时抛出
            emitted = True
            yield ev
    except AppError as exc:
        # 中断也属 run 结束（T06）：记录中断事件并照常落 Trace。
        # 已有事件流出才补发 trace 事件（其后 chat.py 追加 error+done）；
        # 流出前超限保持纯 JSON 429 形态，trace 只进日志
        tracer.record_event("run_interrupted", {"code": exc.code})
        if exc.code == "KN-429":
            tracer.record_event("budget_exceeded", {})
        data = finish_and_log(tracer, gateway, budget)
        if emitted and data is not None:
            yield {"trace": data}
        raise
    data = finish_and_log(tracer, gateway, budget)  # 硬约束：失败返回 None 不影响主流程
    if data is not None:
        yield {"trace": data}
