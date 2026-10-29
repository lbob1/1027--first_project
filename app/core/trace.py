"""RunTracer：每 run 一份结构化 JSON Trace（M-S4-T06，观测收拢）。

把散落在各节点日志里的观测信息（调用链/耗时/token 用量/审批事件/预算）
收拢为一次 run 一份结构化 JSON：与 ModelGateway/BudgetManager 同生命周期
（stream_answer 每 run 新建，经 config["configurable"]["tracer"] 注入节点）。

**脱敏硬约束（细则 9）**：Trace 只含结构化元数据——不含 question/答案
内容/检索结果内容/文件内容/凭据；工具参数只记 key 集合（arg_keys）；
工具错误只记 KN 码或 "unknown"（safe_error_type 剥离消息正文——删除类
错误消息含文件名等参数值，绝不能进 Trace）。

**纯内存收集**：不发请求不查库；to_json 字段白名单装配，天然无敏感
内容注入面。

**取舍（与任务书注明一致）**：trace 事件由 stream_answer 直接 yield
（stream_answer 本身就是 custom 流出口，节点 writer 无法在图结束后发
事件）；budget 保持独立事件兼容既有消费方，Trace 为超集（budget
snapshot 全量包含在 tokens/budget 字段）。流出前超限（HTTP 429 形态）
不 yield trace 只落日志，保持 T04 实证的纯 JSON 429 行为。
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger("app.core.trace")

_KN_CODE_RE = re.compile(r"KN-\d{3}")


def safe_error_type(err: str) -> str:
    """从工具错误串提取可入 Trace 的类型标识：仅 KN 码，无码记 "unknown"。

    错误消息正文（含文件名等参数值）绝不入 Trace（脱敏硬约束）。"""
    m = _KN_CODE_RE.search(err)
    return m.group(0) if m else "unknown"


class RunTracer:
    """每 run 一个实例：节点打点 / 工具记录 / 事件记录 / 收尾装配，纯内存。

    节点耗时采用"链式结算"：mark(node) 记录进入时刻，同时把上一个未
    闭合节点的耗时结算入表；finish 闭合最后一个节点。本图节点不重入
    （恢复 run 只执行 approve_and_delete→generate，各 mark 一次），
    链式结算即逐节点真实耗时。"""

    def __init__(self) -> None:
        self.run_id = uuid.uuid4().hex
        self.thread_id: str | None = None
        self.workspace_id: str | None = None
        self._t0: float = 0.0
        self._started_at: str = ""
        self._nodes: list[dict] = []
        self._open_node: str | None = None
        self._open_t: float = 0.0
        self._tools: list[dict] = []
        self._events: list[dict] = []
        self._tokens: dict = {}
        self._budget: dict = {}
        self._total_ms: float = 0.0

    def start(self, thread_id: str | None, workspace_id=None) -> None:
        """记 run 起始时间戳与维度标识（workspace_id 仅记 UUID，非内容）。"""
        self.thread_id = thread_id
        self.workspace_id = str(workspace_id) if workspace_id else None
        self._t0 = time.perf_counter()
        self._started_at = datetime.now(timezone.utc).isoformat()

    def mark(self, node: str) -> None:
        """节点进入打点（router/retrieve/delete_prepare/approve_and_delete/
        generate）：上一个未闭合节点的耗时在此刻结算。"""
        now = time.perf_counter()
        if self._open_node is not None:
            self._nodes.append({
                "node": self._open_node,
                "duration_ms": round((now - self._open_t) * 1000, 1),
            })
        self._open_node = node
        self._open_t = now

    def record_tool(self, name: str, *, ok: bool, result_count: int,
                    error_type: str | None = None,
                    arg_keys: list[str] | None = None) -> None:
        """工具调用结果：参数只记 key 集合，错误只记 KN 码（脱敏硬约束）。"""
        self._tools.append({
            "name": name, "ok": ok, "result_count": result_count,
            "error_type": error_type, "arg_keys": sorted(arg_keys or []),
            "t_ms": round((time.perf_counter() - self._t0) * 1000, 1),
        })

    def record_event(self, kind: str, detail: dict | None = None) -> None:
        """特殊事件：approval_pending / approval_approved / approval_rejected、
        budget_exceeded、run_interrupted、policy_blocked、router_fallback；
        detail 只允许结构化元数据（调用方自律：不含参数值/消息内容）。"""
        self._events.append({
            "kind": kind, "detail": detail or {},
            "t_ms": round((time.perf_counter() - self._t0) * 1000, 1),
        })

    def finish(self, gateway, budget) -> None:
        """收尾装配：闭合末节点 + gateway 用量（prompt/completion/total）
        + budget snapshot + 总耗时。"""
        now = time.perf_counter()
        if self._open_node is not None:
            self._nodes.append({
                "node": self._open_node,
                "duration_ms": round((now - self._open_t) * 1000, 1),
            })
            self._open_node = None
        self._tokens = {
            "prompt_tokens": gateway.prompt_tokens,
            "completion_tokens": gateway.completion_tokens,
            "total_tokens": gateway.total_tokens,
        }
        self._budget = budget.snapshot()
        self._total_ms = round((now - self._t0) * 1000, 1)

    def to_json(self) -> dict:
        """完整 Trace 结构（字段白名单，无内容类数据）。"""
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workspace_id": self.workspace_id,
            "started_at": self._started_at,
            "nodes": self._nodes,
            "tools": self._tools,
            "events": self._events,
            "tokens": self._tokens,
            "budget": self._budget,
            "total_ms": self._total_ms,
        }


def finish_and_log(tracer: RunTracer, gateway, budget) -> dict | None:
    """收尾装配 + 结构化日志一行 JSON（log.info，中间件式观测口径统一）。

    硬约束：Trace 生成失败不影响问答主流程——任何异常 log.warning 后
    返回 None，调用方拿 None 则不发 event: trace，主流程照常收尾。"""
    try:
        tracer.finish(gateway, budget)
        data = tracer.to_json()
        log.info("run trace %s", json.dumps(data, ensure_ascii=False))
        return data
    except Exception:
        log.warning("trace 装配失败（不影响问答主流程）", exc_info=True)
        return None
