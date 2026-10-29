"""BudgetManager：每 run 预算管控（M-S4-T04）。

消费 S4-T01 Gateway 预留的用量统计（total_tokens）与工具调用计数，
把"单次问答烧多少"关进笼子：token 超限或工具调用超限即抛 AppError("KN-429")
中断本 run。

**取码依据**：00 文件第五节错误码表 KN-429 的字面语义即"超出预算限制
（token / 调用次数）"——与本组件职责逐字吻合，http_status=429，无需发明新码。

**限额默认值**：MAX_TOKENS_PER_RUN=10000（实测单轮完整问答 ~2000 token，
默认值宽松到正常问答绝不误伤）；MAX_TOOL_CALLS_PER_RUN=5（当前仅
hybrid_search 一个工具，正常问答 router 判定最多触发 1 次检索）。
限额收紧是运行时决策不是代码决策：BudgetManager 构造参数显式传入；
模块常量经运行时读取（默认参数 None → 取常量），便于部署轮按环境收紧
与测试注入。

纯内存计数，不发请求不查库；预算数字与用量不入敏感日志范畴（细则 9：
不落消息内容/凭据，条数与限额可记）。
"""

import logging

from app.core.errors import AppError

log = logging.getLogger("app.core.budget")

MAX_TOKENS_PER_RUN = 10000
MAX_TOOL_CALLS_PER_RUN = 5


class BudgetManager:
    """每 run 一个实例：token 用量与工具调用次数的双重限额。"""

    def __init__(
        self,
        *,
        max_total_tokens: int | None = None,
        max_tool_calls: int | None = None,
    ):
        # 默认参数运行时读模块常量（非 def 绑定），支持部署/测试期收紧
        self.max_total_tokens = (
            max_total_tokens if max_total_tokens is not None else MAX_TOKENS_PER_RUN
        )
        self.max_tool_calls = (
            max_tool_calls if max_tool_calls is not None else MAX_TOOL_CALLS_PER_RUN
        )
        self.tokens_used = 0
        self.tool_calls = 0

    def check_token(self, usage_total: int) -> None:
        """校验 run 累计 token 是否超限；超限抛 KN-429 中断本 run。"""
        self.tokens_used = max(self.tokens_used, usage_total)
        if usage_total > self.max_total_tokens:
            log.warning(
                "budget 超限 tokens=%d max=%d", usage_total, self.max_total_tokens
            )
            raise AppError(
                "KN-429",
                f"本轮问答 token 用量 {usage_total} 超过预算上限 {self.max_total_tokens}",
            )

    def record_tool_call(self) -> None:
        """工具调用计数 +1；超限抛 KN-429（在调工具之前拦截）。"""
        if self.tool_calls >= self.max_tool_calls:
            log.warning(
                "budget 工具调用超限 calls=%d max=%d",
                self.tool_calls, self.max_tool_calls,
            )
            raise AppError(
                "KN-429",
                f"本轮问答工具调用次数超过上限 {self.max_tool_calls}",
            )
        self.tool_calls += 1

    def snapshot(self) -> dict:
        """用量快照（T06 Trace 将复用）。"""
        return {
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "max_total_tokens": self.max_total_tokens,
            "max_tool_calls": self.max_tool_calls,
        }
