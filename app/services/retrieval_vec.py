"""稠密检索路（M-S3-T02）：pgvector 余弦近邻 top-k 单路纯函数。

- query 经 embed_texts([query])[0] 得查询向量（真实调 compatible-mode API，
  key 不入日志；embed 客户端复用 app/services/embedding.py，不新建）；
- pgvector 余弦距离算子 `<=>`（vector_cosine_ops HNSW 索引同款算子）：
  距离 = 1 - 余弦相似度，值域 [0,2]，越小越相关；
- **过滤条件与 M-S3-T01 稀疏路完全一致**（P-S3 硬约束，细则 1）：
  JOIN document_versions + WHERE chunks.workspace_id = :ws AND status='active'，
  条件进 SQL，禁止先查全表再内存过滤；
- 向量经**绑定参数**传 SQL（字符串形式 + 显式 ::vector cast，禁止拼接进
  SQL 文本）；查询向量/中间结果不入日志（细则 9），日志只记条数与耗时。

**rank 语义对齐（T03 RRF 融合前提）**：返回 rank = 1 - 余弦距离（四舍五入
6 位）——把"越小越相关"的距离换算为"越大越相关"的相似度，与 T01 的
ts_rank 语义方向一致（两路 rank 同为越大越相关）；RRF 融合只消费排名
序位不消费分值，但字段语义统一可避免下游误用。content 截断 200 字与
T01 的 CONTENT_CLIP 一致。

返回结构逐字段对齐 retrieval_fts.search_fts：chunk_id / seq_no / content /
rank / filename / version_no。本函数不碰 FTS、不融合、不 Rerank（T03 职责）。
模块导入零网络请求（embedding client 懒创建）。
"""

import logging
import time
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embedding import embed_texts

log = logging.getLogger("app.services.retrieval_vec")

CONTENT_CLIP = 200  # 与 T01 retrieval_fts.CONTENT_CLIP 一致（引用展示截断）

_SEARCH_SQL = text("""
    SELECT c.chunk_id,
           c.seq_no,
           left(c.content, :clip)              AS content,
           round((1 - (c.embedding <=> (:vec)::vector))::numeric, 6) AS rank,
           d.filename,
           dv.version_no
    FROM chunks c
    JOIN document_versions dv ON dv.version_id = c.version_id
    JOIN documents d          ON d.document_id = dv.document_id
    WHERE c.workspace_id = :ws
      AND dv.status = 'active'
    ORDER BY c.embedding <=> (:vec)::vector
    LIMIT :k
""")


def search_vec(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """工作区内 active 版本 chunks 的余弦近邻 top-k（稠密单路）。"""
    vec = embed_texts([query])[0]  # 真实调 embedding API（key 只进 SDK，不入日志）
    vec_str = "[" + ",".join(f"{x:.8g}" for x in vec) + "]"  # 绑定参数值，非 SQL 拼接
    t0 = time.perf_counter()
    rows = session.execute(
        _SEARCH_SQL,
        {"ws": workspace_id, "vec": vec_str, "clip": CONTENT_CLIP, "k": top_k},
    ).all()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "search_vec ws=%s hits=%d top_k=%d elapsed=%.1fms",
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
