"""ContextManager：Agent run 上下文装配（M-S4-T01）。纯装配不发请求。

**单一来源方向（任务书允许的唯一既有文件改动，已注明）**：
- RAG system prompt 的**权威定义在本模块**（RAG_SYSTEM_PROMPT），
  rag_graph._SYSTEM_PROMPT 改为 import 本模块常量（别名转发，保持其内部
  引用点与行为不变）；
- 证据块格式同理：build_evidence_block 权威在本模块，rag_graph._build_context
  改为 import 转发——两处各维护一份格式被禁止；
- 方向选择理由：context 是装配方、消费面更广（S4-T03 Agent Graph 多节点
  都要拼 system/evidence），权威放这里可让 rag_graph 退化为纯编排。

**职责边界**：本模块不管重试/超时/用量（那是 gateway.py），不发任何网络
请求；模块导入零网络。

**history 截断**：HISTORY_MAX_TURNS=10（模块常量，ContextManager 构造参数
可覆盖；本任务硬约束禁改 config.py 等既有文件，故不入配置，S4 后续轮次
如需集中配置再迁移）。

**identity**：S5 JWT 接入前的身份说明过渡参数（O-7）——当前由调用方传入
字符串说明（用户名/workspace 名），S5 换 JWT 后由认证层生成。
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Message

log = logging.getLogger("app.core.context")

RAG_SYSTEM_PROMPT = (
    "你是企业知识库问答助手。仅依据下面提供的资料回答用户问题；"
    "资料不足以回答时，明确说明资料中未涉及，不要编造。"
    "回答末尾另起一行，用【来源: 文件名】列出所引用的资料文件名。"
)

HISTORY_MAX_TURNS = 10  # 默认保留最近 10 轮历史（ContextManager 可覆盖）


def build_evidence_block(hits: list[dict]) -> str:
    """检索证据块：[资料i] 文件: filename (版本 vN)\\ncontent（原 rag_graph 格式）。"""
    blocks = [
        f"[资料{i}] 文件: {h['filename']} (版本 v{h['version_no']})\n{h['content']}"
        for i, h in enumerate(hits, start=1)
    ]
    return "\n\n".join(blocks) if blocks else "（无检索结果）"


def load_history(session: Session, *, thread_id: str) -> list[dict]:
    """按 thread_id 读取 messages 历史（role/content dict，created_at 升序）。"""
    rows = session.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at)
    ).scalars().all()
    return [{"role": m.role, "content": m.content} for m in rows]


class ContextManager:
    """为 Agent run 装配最终 messages 列表：system(身份+RAG 约束) → history → 证据+问题。"""

    def __init__(self, *, history_max_turns: int = HISTORY_MAX_TURNS):
        self.history_max_turns = history_max_turns

    def build(
        self,
        *,
        identity: str,
        history: list[dict],
        evidence: str,
        question: str,
    ) -> list[dict]:
        """装配 messages：纯内存计算，不改任何状态。

        - identity 非空时并入 system（身份说明）；
        - history 截断为最近 history_max_turns 条；
        - evidence 为检索证据块文本（build_evidence_block 产物）。
        """
        trimmed = list(history[-self.history_max_turns:])
        system = RAG_SYSTEM_PROMPT
        if identity:
            system = f"{system}\n\n当前用户与工作区说明：{identity}"
        messages = [{"role": "system", "content": system}, *trimmed]
        messages.append(
            {"role": "user", "content": f"资料如下：\n{evidence}\n\n问题：{question}"}
        )
        log.info(
            "context built system=1 history=%d(裁前%d) user=1 total=%d",
            len(trimmed), len(history), len(messages),
        )
        return messages
