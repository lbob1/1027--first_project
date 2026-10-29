"""ToolRegistry：Agent 工具注册与执行（M-S4-T02）。

**fn 签名约定（安全边界，不是便利性设计）**：
fn(session, *, workspace_id, **arguments)——session 与 workspace_id 由
execute 的框架层传入注入，工具函数签名**不接受调用方传 workspace**，
杜绝 LLM 编造参数越权访问他区（细则 1：LLM 可控的只有 arguments，
workspace 上下文永远由服务端决定）。

**get() 未注册选择 KN-422 的理由**：工具不存在对 Agent 循环而言是
"不可处理请求"（模型给出了无效工具名），属请求语义错误而非代码 bug，
统一 KN 错误码语义便于 API 层透传；ValueError 留给代码内编程错误
（如重名注册）。

**execute 错误包裹策略**：AppError 原样透传（保留 KN 码语义，策略/路由层
可识别）；其他异常包裹为 {"error": "<类型>: <消息>"} 结构化返回——
LLM 可读的失败说明，让 Agent 能自我修正而非崩掉整个循环。

**日志只记工具名与参数 key 集合**，不记 query 值/返回内容/凭据（细则 9）。
模块导入零网络请求（registry 构造不建 client）。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.errors import AppError

log = logging.getLogger("app.core.tool_registry")


@dataclass(frozen=True)
class ToolSpec:
    """工具描述：schema 供 LLM 选择工具，fn 为服务端实现。"""

    name: str
    description: str
    parameters_schema: dict  # OpenAI function parameters（JSON Schema）
    read_only: bool
    fn: Callable  # 约定签名 fn(session, *, workspace_id, **arguments)


class ToolRegistry:
    """工具注册表：注册 / 查询 / 列 schema / 框架层执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具重名注册被拒绝: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise AppError("KN-422")
        return spec

    def list_schemas(self) -> list[dict]:
        """输出 OpenAI tools=[{type:"function", function:{...}}] 格式。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters_schema,
                },
            }
            for s in self._tools.values()
        ]

    def execute(
        self,
        session,
        *,
        name: str,
        arguments: dict,
        workspace_id,
    ) -> dict:
        """框架层执行：注入 session/workspace_id，调用 fn，统一错误策略。"""
        spec = self.get(name)  # 未注册 → KN-422 透传
        log.info(
            "tool execute name=%s arg_keys=%s", name,
            sorted(arguments.keys()),
        )
        try:
            result = spec.fn(session, workspace_id=workspace_id, **arguments)
        except AppError:
            raise  # KN 码语义原样透传
        except Exception as exc:  # 包裹为 LLM 可读的结构化错误，不崩 Agent 循环
            log.warning("tool failed name=%s err=%s", name, type(exc).__name__)
            return {"error": f"{type(exc).__name__}: {exc}"}
        if not isinstance(result, dict):
            result = {"result": result}
        return result


def _hybrid_search_fn(session, *, workspace_id, query: str, top_k: int = 5) -> dict:
    """hybrid_search 的服务端实现（workspace 注入，不接受调用方传区）。"""
    from app.services.retrieval_hybrid import search_hybrid  # 局部 import 避免循环依赖
    return {"results": search_hybrid(session, workspace_id=workspace_id, query=query, top_k=top_k)}


_HYBRID_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "检索查询词"},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5,
                  "description": "返回条数上限"},
    },
    "required": ["query"],
}


def build_default_registry() -> ToolRegistry:
    """默认注册表：混合检索作为第一个工具。"""
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="hybrid_search",
        description=(
            "在当前工作区知识库中做混合检索（全文+向量+RRF 融合），"
            "返回与查询相关的文档片段（含来源文件名与版本）。"
            "当需要查询知识库内容、回答资料相关问题时使用。"
        ),
        parameters_schema=_HYBRID_SEARCH_SCHEMA,
        read_only=True,
        fn=_hybrid_search_fn,
    ))
    return registry
