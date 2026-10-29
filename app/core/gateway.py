"""ModelGateway：统一模型调用入口（M-S4-T01）。

**现状说明**：rag_graph._generate 目前直调 embedding._get_client 的 openai
client 发起 chat.completions；S4-T03 Agent Graph 将统一切换到本 Gateway。
本任务不改 rag_graph（避免连锁改动，T03 统一切换）。

**取舍说明**：
- 重试：自写 1 层应用级重试——仅对连接类错误（openai.APIConnectionError）
  与限流（openai.RateLimitError）生效，最多 3 次、指数退避 0.5s 起；
  不依赖 SDK max_retries 的理由：自写可统一日志与用量统计口径，且可明确
  流式语义"仅重试建流、不重试已产出的 token"；
- 超时：显式 60s（CHAT_TIMEOUT_S 模块常量）；
- 用量：非流式取 response.usage；流式传 stream_options={"include_usage":
  True} 采集尾块 usage；累计到实例属性（本轮 run 的 token 计数，
  S4-T04 BudgetManager 将消费）；
- 日志只记模型名/消息条数/耗时/token 数——消息内容与凭据不入日志（细则 9），
  任何异常路径同样只记异常类型名；
- client 复用 embedding._get_client 同款懒创建（构造参数可注入替代实现，
  供测试 mock），不重复造连接。
"""

import logging
import time

import openai

from app.core.config import get_settings

log = logging.getLogger("app.core.gateway")

CHAT_TIMEOUT_S = 60.0
RETRYABLE_ERRORS = (openai.APIConnectionError, openai.RateLimitError)


class ModelGateway:
    """chat.completions 统一入口：重试 / 超时 / 用量统计 / 脱敏日志。"""

    def __init__(self, *, client=None, model: str | None = None, max_attempts: int = 3):
        self._client = client
        self._model = model
        self.max_attempts = max_attempts
        # 用量累计（本轮 run 的 token 计数，S4-T04 BudgetManager 消费）
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.last_usage: dict | None = None

    def _ensure_client(self):
        if self._client is None:
            from app.services.embedding import _get_client  # 复用懒创建，导入零网络
            self._client = _get_client()
        return self._client

    def _accumulate(self, usage) -> None:
        if usage is None:
            return
        self.prompt_tokens += usage.prompt_tokens or 0
        self.completion_tokens += usage.completion_tokens or 0
        self.total_tokens += usage.total_tokens or 0
        self.last_usage = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }

    def chat(self, messages: list[dict], *, stream: bool = False, **kwargs):
        """发起对话。非流式返回完整 response；流式返回 token 文本生成器
        （usage 在内部采集，经实例属性读取）。"""
        model = self._model or get_settings().CHAT_MODEL
        t0 = time.perf_counter()
        if stream:
            return self._chat_stream(model, messages, t0, **kwargs)
        return self._chat_once(model, messages, t0, **kwargs)

    def _retry_loop(self, model: str, n_msgs: int, create_fn):
        """应用级重试：仅连接类错误与限流，最多 max_attempts 次，指数退避。"""
        for attempt in range(1, self.max_attempts + 1):
            try:
                return create_fn()
            except RETRYABLE_ERRORS as exc:
                if attempt == self.max_attempts:
                    log.warning(
                        "gateway 最终失败 model=%s msgs=%d attempts=%d err=%s",
                        model, n_msgs, attempt, type(exc).__name__,
                    )
                    raise
                delay = 0.5 * (2 ** (attempt - 1))
                log.warning(
                    "gateway 第%d/%d次失败（%s），%.1fs 后重试 model=%s msgs=%d",
                    attempt, self.max_attempts, type(exc).__name__, delay, model, n_msgs,
                )
                time.sleep(delay)

    def _chat_once(self, model: str, messages: list[dict], t0: float, **kwargs):
        resp = self._retry_loop(
            model, len(messages),
            lambda: self._ensure_client().chat.completions.create(
                model=model, messages=messages, timeout=CHAT_TIMEOUT_S, **kwargs,
            ),
        )
        self._accumulate(resp.usage)
        log.info(
            "gateway chat ok model=%s msgs=%d tokens=%d elapsed=%.1fms",
            model, len(messages), self.total_tokens, (time.perf_counter() - t0) * 1000,
        )
        return resp

    def _chat_stream(self, model: str, messages: list[dict], t0: float, **kwargs):
        # 重试只覆盖"建流"（create 发出 HTTP 请求）；建流成功后逐块产出阶段
        # 不再重试——否则会把已 yield 的 token 重复发送给调用方。
        stream_resp = self._retry_loop(
            model, len(messages),
            lambda: self._ensure_client().chat.completions.create(
                model=model, messages=messages, timeout=CHAT_TIMEOUT_S,
                stream=True, stream_options={"include_usage": True}, **kwargs,
            ),
        )

        def _iter_tokens():
            for chunk in stream_resp:
                if getattr(chunk, "usage", None) is not None:
                    self._accumulate(chunk.usage)  # 尾块 usage
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            log.info(
                "gateway stream done model=%s msgs=%d tokens=%d elapsed=%.1fms",
                model, len(messages), self.total_tokens, (time.perf_counter() - t0) * 1000,
            )

        return _iter_tokens()
