"""PolicyEngine：工具执行前的策略判定（M-S4-T02）。纯内存判定，不发请求不查库。

**与 ToolRegistry 的关系**：本模块运行时不 import tool_registry（互不依赖，
仅经 ToolSpec 字段交互）；类型注解经 TYPE_CHECKING 静态引用，运行时对
spec 做 duck typing（读 read_only / parameters_schema 两字段）。

**三规则**：
- 规则一 read_only=True：参数通过即 allowed（reason 标注"只读工具可并行/
  可自动执行"）；
- 规则二 read_only=False：needs_approval——本版以 Decision 返回
  (allowed=False, reason="写入类工具需审批")；**演进路径**：S4-T05
  ApprovalManager 接管后升级为 LangGraph interrupt 审批流（此处 reason
  文案保持不变，调用方据 allowed=False 走审批分支）；
- 规则三（最优先）：参数校验——缺必填 key 或类型不符 → 不允许，reason
  指明缺什么/什么类型错（在调 fn 之前拦截，省一次无效执行）；
  只校验 schema 声明的 key（required + properties 类型），未声明的额外
  key 宽松放行（schema 未约束，由工具 fn 自行忽略）。

无硬编码密钥/路径。
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 静态注解用，运行时不 import tool_registry（互不依赖）
    from app.core.tool_registry import ToolSpec

log = logging.getLogger("app.core.policy")

_JSON_TYPES: dict[str, tuple] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def _type_mismatch(value: Any, json_type: str) -> bool:
    expected = _JSON_TYPES.get(json_type)
    if expected is None:
        return False  # 未支持的类型声明不拦截（宽松，schema 维护责任）
    ok = isinstance(value, expected)
    if json_type in ("integer", "number") and isinstance(value, bool):
        ok = False  # bool 是 int 子类，显式排除
    return not ok


class PolicyEngine:
    """check(spec, arguments) -> Decision：放行判定在调 fn 之前。"""

    def check(self, spec: "ToolSpec", *, arguments: dict) -> Decision:
        schema = spec.parameters_schema or {}

        # 规则三（最优先）：参数校验
        for key in schema.get("required", []):
            if key not in arguments:
                decision = Decision(False, f"参数校验失败：缺少必填参数 {key}")
                log.info("policy deny tool=%s rule=params reason=%s", spec.name, decision.reason)
                return decision
        properties = schema.get("properties", {})
        for key, value in arguments.items():
            declared = properties.get(key)
            if declared and _type_mismatch(value, declared.get("type", "")):
                decision = Decision(
                    False,
                    f"参数校验失败：参数 {key} 类型应为 {declared.get('type')}",
                )
                log.info("policy deny tool=%s rule=params reason=%s", spec.name, decision.reason)
                return decision

        # 规则一 / 规则二：按 read_only 分流
        if spec.read_only:
            decision = Decision(True, "只读工具可并行/可自动执行")
        else:
            decision = Decision(False, "写入类工具需审批")  # S4-T05 ApprovalManager 升级为 interrupt
        log.info("policy decide tool=%s allowed=%s read_only=%s", spec.name, decision.allowed, spec.read_only)
        return decision
