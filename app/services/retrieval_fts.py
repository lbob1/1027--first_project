"""稀疏检索路（M-S3-T01）：tsvector 全文检索 top-k 单路纯函数。

**中文分词方案 B（探针实证 + 用户确认）**：'simple' 配置不做中文分词，
对原始 content 建索引时整句（到标点）成单 token，中文子串查询零召回
（探针：'机器学习' 命中 0 / 完整子句命中 1 / 英文命中 1）。故两侧共同改造：
- 入库侧：摄取时 jieba 分词（chunker.tokenize_text）存 chunks.content_tokens，
  tsv 生成列 to_tsvector('simple', content_tokens)（models.py，已重建）；
- 查询侧：本模块对查询词用**同一函数**分词后空格连接，经**绑定参数**
  送 plainto_tsquery('simple', :kw)（AND 语义，用户确认；禁止字符串拼接）；
- 排名 ts_rank（用户确认）：单路召回基线，精排由 T03 RRF+Rerank 兜底。

**引用越权防线第一层（细则 1 / P-S3 / S3-AC-3 前置）**：workspace_id 与
document_versions.status='active' 两过滤条件必须进 SQL WHERE（与稠密路
M-S3-T02 完全一致），禁止先查全表再内存过滤。

返回结构预置引用溯源字段（S3-AC-3）：chunk_id / seq_no / content(截断) /
rank / filename / version_no（经 version JOIN documents 取）。

日志只记条数与耗时，禁止 chunk 全文与查询词进日志（细则 9）。
本函数不碰向量、不融合（T02/T03 职责）。
"""

import logging
import time
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("app.services.retrieval_fts")

CONTENT_CLIP = 200  # 返回 content 截断长度（引用展示用，全文留在 chunk 行）

_SEARCH_SQL = text("""
    SELECT c.chunk_id,
           c.seq_no,
           left(c.content, :clip)              AS content,
           round(ts_rank(c.tsv, plainto_tsquery('simple', :kw))::numeric, 6) AS rank,
           d.filename,
           dv.version_no
    FROM chunks c
    JOIN document_versions dv ON dv.version_id = c.version_id
    JOIN documents d          ON d.document_id = dv.document_id
    WHERE c.workspace_id = :ws
      AND dv.status = 'active'
      AND c.tsv @@ plainto_tsquery('simple', :kw)
    ORDER BY rank DESC
    LIMIT :k
""")


def search_fts(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """工作区内 active 版本 chunks 的全文检索 top-k（稀疏单路）。"""
    from app.services.chunker import tokenize_text

    # 查询侧分词：与入库侧同一函数；结果只经绑定参数进 SQL（防注入）
    keywords = tokenize_text(query)
    t0 = time.perf_counter()
    rows = session.execute(
        _SEARCH_SQL,
        {"ws": workspace_id, "kw": keywords, "clip": CONTENT_CLIP, "k": top_k},
    ).all()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "search_fts ws=%s hits=%d top_k=%d elapsed=%.1fms",
        workspace_id, len(rows), top_k, elapsed_ms,
    )
    return [
        {
            "chunk_id": str(r.chunk_id),
            "seq_no": r.seq_no,
            "content": r.content,
            "rank": float(r.rank),
            "filename": r.filename,
            "version_no": r.version_no,
        }
        for r in rows
    ]
