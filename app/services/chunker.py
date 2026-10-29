"""切块纯函数（M-S2-T04）：无状态，不碰 DB。

- 目标块 300~500 字（size=400），相邻块重叠恒 50 字（中文按字符计）；
- **边界决策（任务书歧义点，落地说明）**：末块可能短于 300 字——重叠
  恒 50、块长上限 500 与末块下限 300 三者不可同时满足（1234 字实例：
  400/400/400/184）。取舍：**重叠精确 50 + 内容零丢失优先，末块保留
  短块**（LangChain RecursiveCharacterTextSplitter 同款行为）；向量检索
  对短块无惩罚，短块优于把两块硬并成 >500 的超限块。
- 空文本输出空列表；无状态不碰 DB。
"""

CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """纯文本 → 块文本列表（保序，相邻块重叠 overlap 字）。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = size - overlap
    return [p for p in (text[i : i + size] for i in range(0, len(text), step)) if p.strip()]
