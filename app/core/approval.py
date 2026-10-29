"""ApprovalManager：删除类操作审批语义封装（M-S4-T05）。

**职责边界**：挂起载荷构造 / 确认解析 / 审计落库三件事的纯封装——
不持状态（挂起状态由 LangGraph InMemorySaver checkpoint 持有，不自造
审批轮询轮子，P-S4 硬性约束）、不发网络请求；真正的挂起/恢复机制在
agent_graph 的 interrupt(Command(resume)) 中，本模块只提供语义件。

**审计落库的 [APPROVAL] 方案取舍（docstring 注明）**：00 契约 messages
表无审批专用字段（第四节七表字段不得增删改），最小兼容方案为——
role="system"（role 列 String(32) 无约束，审计行非用户/助手对话，
语义上属系统记录）+ content 以 "[APPROVAL]" 前缀 + JSON 序列化事件
（event=pending/approved/rejected + 工具名/目标文件名/风险文案）。
消费方（load_history）据此过滤，审计行不进对话上下文。审批全程
（挂起/批准/拒绝）各写一行，满足细则 7"审计记录"。

**payload 不落敏感信息（硬约束）**：挂起载荷只含工具名/目标文件名/
风险文案三项——不含 workspace_id/user_id/UUID 等内部标识，客户端
可见内容最小化。

模块导入零网络请求。
"""

import json
import logging
from typing import TYPE_CHECKING, Any

from app.models.models import Message

if TYPE_CHECKING:  # 静态注解用，运行时不 import tool_registry（互不依赖）
    from app.core.tool_registry import ToolSpec

log = logging.getLogger("app.core.approval")

APPROVAL_TAG = "[APPROVAL]"  # 审计行 content 前缀，消费方据此识别

# 审批事件三类（event 字段取值）
EVENT_PENDING = "pending"      # 挂起：等待人工确认
EVENT_APPROVED = "approved"    # 批准：confirm=True，工具已执行
EVENT_REJECTED = "rejected"    # 拒绝：confirm=False/解析失败，未执行

_RISK_TEXT = "该操作将从当前工作区删除指定文档，删除后无法通过本系统恢复；仍有版本的文档会被系统阻断。"


class ApprovalManager:
    """审批语义封装：纯函数 + 落库，不持状态。"""

    def build_interrupt_payload(
        self, spec: "ToolSpec", arguments: dict, workspace_id: Any
    ) -> dict:
        """构造挂起时发给调用方的审批请求。

        **payload 只含工具名/目标文件名/风险文案**（硬约束，不落
        workspace_id/user_id 等内部标识——workspace_id 形参为签名完整与
        后续扩展预留，当前不写入 payload；审计行的 workspace 维度由
        audit 落库时以 Message.workspace_id 列承载，不入 content JSON）。
        """
        payload = {
            "tool": spec.name,
            "filename": arguments.get("filename", ""),
            "risk": _RISK_TEXT,
        }
        log.info("approval payload built tool=%s", spec.name)
        return payload

    def parse_confirm(self, resume_value: Any) -> bool:
        """解析恢复值：仅布尔 True 放行——False、"true" 字符串、None 等
        一律视为拒绝（宁可错杀：确认必须是显式布尔意图）。"""
        return resume_value is True

    def audit(
        self,
        session,
        *,
        workspace_id,
        thread_id: str,
        event: str,
        payload: dict,
    ) -> None:
        """审批事件写 messages 审计行（role="system" + [APPROVAL] JSON）。

        任务书签名无 workspace_id，但 messages 表该列非空（00 第四节），
        故以参数显式传入——审计行归属工作区，同时满足细则 1 每行数据
        带 workspace 维度。落库失败向上抛（审批审计缺失属严重问题，
        不静默吞掉——调用方在事务内）。
        """
        record = {"event": event, **payload}
        session.add(
            Message(
                workspace_id=workspace_id,
                thread_id=thread_id,
                role="system",
                content=f"{APPROVAL_TAG} {json.dumps(record, ensure_ascii=False)}",
            )
        )
        log.info("approval audit event=%s tool=%s", event, payload.get("tool"))
