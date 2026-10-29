"""百炼 Rerank 精排（M-S3-T04）。

- DashScope **原生 HTTP 端点**（rerank 不在 compatible-mode 内）：
  POST https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank
  复用 OPENAI_API_KEY（同一 DashScope key）；
- httpx 直调（openai SDK 传递依赖，pyproject 显式声明），超时显式 5s；
- **降级策略（硬要求）**：RERANK_ENABLED=false 整体跳过；调用失败
  （网络/配额/超时/HTTP 错误）log.warning 后**按原 rrf_score 顺序原样返回**
  （截断 top_n），不抛异常不中断问答——Rerank 是增强不是依赖；
- 日志只记条数与耗时；query/文档内容/凭据不入日志（细则 9）；
- 输出在每条 doc 上附 relevance_score（DashScope 返回，值域 [0,1]）。
"""

import logging
import time

import httpx

from app.core.config import get_settings

log = logging.getLogger("app.services.rerank")

DASHSCOPE_RERANK_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)
RERANK_TIMEOUT_S = 5.0


def rerank_documents(query: str, docs: list[dict], top_n: int) -> list[dict]:
    """按 query 相关性重排 docs，返回前 top_n 条（失败降级原序）。"""
    if not docs:
        return []
    if not get_settings().RERANK_ENABLED:
        log.info("rerank 已禁用（RERANK_ENABLED=false），降级原序 n=%d", len(docs))
        return docs[:top_n]

    t0 = time.perf_counter()
    payload = {
        "model": get_settings().RERANK_MODEL,
        "input": {"query": query, "documents": [d["content"] for d in docs]},
        "parameters": {"top_n": top_n, "return_documents": False},
    }
    try:
        resp = httpx.post(
            DASHSCOPE_RERANK_URL,
            json=payload,
            headers={"Authorization": f"Bearer {get_settings().OPENAI_API_KEY}"},
            timeout=RERANK_TIMEOUT_S,
        )
        resp.raise_for_status()
        results = resp.json()["output"]["results"]  # [{index, relevance_score}]
        reranked = [
            {**docs[r["index"]], "relevance_score": r["relevance_score"]}
            for r in results
        ]
        log.info(
            "rerank 成功 n=%d -> %d elapsed=%.1fms",
            len(docs), len(reranked), (time.perf_counter() - t0) * 1000,
        )
        return reranked
    except Exception as exc:  # 降级是硬要求：任何失败都不中断问答
        log.warning(
            "rerank 调用失败（%s: %.60s），降级为 rrf_score 原序 n=%d",
            type(exc).__name__, str(exc), len(docs),
        )
        return docs[:top_n]
