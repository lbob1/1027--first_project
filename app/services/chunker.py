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


def tokenize_text(text: str) -> str:
    """jieba 分词 → 空格连接（M-S3-T01 方案 B，用户确认）。

    **入库侧与查询侧必须用同一函数**（保证 chunk 侧 lexeme 与查询侧
    token 一致，否则召回错位）：
    - 入库：摄取时对 chunk content 分词，结果存 chunks.content_tokens，
      tsv 生成列 to_tsvector('simple', content_tokens)；
    - 查询：检索时对查询词分词，经绑定参数送 plainto_tsquery('simple', ...)。

    过滤规则：丢弃空白 token 与不含字母/数字的 token（标点）——'。'
    等符号入 tsv 只是噪声 lexeme；中文字符 isalnum()=True 不受影响。
    jieba 词典加载约 1s（首次调用），进程内缓存。
    """
    import jieba  # 局部导入：jieba 启动加载较重，非检索/摄取路径不付出代价

    return " ".join(
        t for t in jieba.cut_for_search(text) if t.strip() and any(ch.isalnum() for ch in t)
    )
