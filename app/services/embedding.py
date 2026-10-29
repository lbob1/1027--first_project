"""Embedding 客户端（M-S2-T04）。

- 走 OPENAI_API_BASE compatible-mode 的 /embeddings 接口；
- SDK 选型 openai（非 httpx）：compatible-mode 即 OpenAI 协议，SDK 自带
  429/401/超时等结构化错误类型与显式 max_retries 控制，手搓解析不可靠；
- 批量限制：百炼 text-embedding 系列单次请求最多 10 条输入，超限分批；
- 维度校验：返回向量维度必须等于 EMBEDDING_DIM，不等显式报错；
- 失败显式抛出（限流/超时/鉴权），重试由 SDK max_retries=2 承担，
  不做额外静默重试；
- key 只从 get_settings() 读；日志仅记条数，禁止记文本内容与 key（细则 9）；
- 模块导入不发起任何网络请求（client 懒创建）。
"""

import logging

from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings

log = logging.getLogger("app.services.embedding")

MAX_BATCH = 10  # 百炼 compatible-mode embeddings 单请求上限（服务端限制）


class EmbeddingError(RuntimeError):
    """embedding 调用失败（维度不符/网络/鉴权等），显式暴露。"""


@lru_cache
def _get_client() -> OpenAI:
    s = get_settings()
    return OpenAI(
        base_url=s.OPENAI_API_BASE,
        api_key=s.OPENAI_API_KEY,
        max_retries=2,  # 任务约束：不静默重试超过 2 次
        timeout=60.0,
    )


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """单批调用（≤MAX_BATCH 条），返回向量列表并校验维度。"""
    s = get_settings()
    try:
        resp = _get_client().embeddings.create(
            model=s.EMBEDDING_MODEL, input=texts
        )
    except Exception as exc:
        raise EmbeddingError(f"embedding 调用失败: {type(exc).__name__}") from exc
    vectors = [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]
    dim = s.EMBEDDING_DIM
    bad = [i for i, v in enumerate(vectors) if len(v) != dim]
    if bad:
        raise EmbeddingError(
            f"embedding 维度不符: 期望 {dim}, 第 {bad} 条实际 "
            f"{[len(vectors[i]) for i in bad]}"
        )
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    """文本列表 → 向量列表（自动按 MAX_BATCH 分批，保序）。"""
    if not texts:
        return []
    result: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH):
        batch = texts[i : i + MAX_BATCH]
        result.extend(_embed_batch(batch))
    log.info("调用 embedding 成功 n=%d 条", len(result))
    return result
