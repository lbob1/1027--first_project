"""RRF 混合融合层（M-S3-T03）：稀疏 + 稠密两路结果的 Reciprocal Rank Fusion。

- 内部调用既有两路（不复制逻辑）：search_fts（M-S3-T01）+ search_vec
  （M-S3-T02）；两路各自的 workspace + active SQL 过滤即隔离防线（细则 1），
  本层为**纯内存计算，不再查库、不重复过滤**；
- RRF 打分（Cormack et al. 2009 经典值）：对每路结果按排名次序 r=1,2,...，
  score = Σ 1/(RRF_K + r)，**只消费排名序位、不消费 rank 分值**（两路 rank
  量纲不同：ts_rank 词频 vs 余弦相似度，直接相加无意义，RRF 用排名规避）；
  同一 chunk 被两路命中时贡献相加，天然高于单路命中；
- 按 chunk_id 去重合并（同一 chunk 两路都命中只算一次）。

**rank 字段语义**：保留其来源路的原始值；两路都命中时取 fts 的 rank
（fts 先合并；字段只有一个槽位，取先处理路的原值，原始分值语义见各路
模块 docstring——ts_rank 词频相关度 / 1-余弦距离）。

返回结构：T01/T02 六字段 + **rrf_score**（round 6 位）+ **sources**
（命中路列表，如 ["fts","vec"]），供调试与 M-S3-T04 消费。

硬约束：不碰 LLM、不碰 Rerank（T04 职责）；模块导入零网络请求
（search_vec 内 embed 才发请求，本层只编排）；日志只记两路各自命中
条数、融合后条数、耗时（细则 9）。
"""

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.services.retrieval_fts import search_fts
from app.services.retrieval_vec import search_vec

log = logging.getLogger("app.services.retrieval_hybrid")

RRF_K = 60  # 经典值（Cormack et al. 2009）：压制第一名权重过度集中，给尾部路公平贡献


def search_hybrid(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """两路各取 top_k → chunk_id 去重 → RRF 融合 → 降序截取 top_k。"""
    t0 = time.perf_counter()
    fts_hits = search_fts(session, workspace_id=workspace_id, query=query, top_k=top_k)
    vec_hits = search_vec(session, workspace_id=workspace_id, query=query, top_k=top_k)

    merged: dict[str, dict] = {}
    for source, hits in (("fts", fts_hits), ("vec", vec_hits)):  # fts 先处理 → rank 优先保留 fts 原值
        for r, hit in enumerate(hits, start=1):  # r=1 第一名
            entry = merged.setdefault(hit["chunk_id"], {**hit, "sources": [], "rrf_score": 0.0})
            entry["sources"].append(source)
            entry["rrf_score"] += 1.0 / (RRF_K + r)
    results = sorted(merged.values(), key=lambda e: e["rrf_score"], reverse=True)[:top_k]
    for e in results:
        e["rrf_score"] = round(e["rrf_score"], 6)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "search_hybrid ws=%s fts=%d vec=%d merged=%d returned=%d elapsed=%.1fms",
        workspace_id, len(fts_hits), len(vec_hits), len(merged), len(results), elapsed_ms,
    )
    return results
