"""基础指标与请求日志中间件（M-S6-T02）。

技术选型：prometheus_client 而非自写 JSON——Counter/Histogram/Gauge 是
标准件（并发安全、自带 exposition 校验），/metrics 输出行业 exposition
格式，未来可零成本接入 Prometheus/Grafana；自写 JSON 仅省一个依赖但失去
整个监控生态。prometheus-client 纯 Python 实现无传递依赖。

**硬约束（细则 9 延伸）**：指标标签与请求日志一律不含文件名、query 词、
答案内容、user_id、token——path 一律取路由模板（scope["route"].path），
天然不含 UUID 与查询串；未匹配路由记 "unmatched"。

四个指标：
- http_requests_total{method, path, status}：请求计数（path=路由模板）；
- http_request_duration_seconds{method, path}：延迟直方图；
- llm_tokens_total{kind=prompt|completion}：LLM token 全局累计——run 级
  ModelGateway 实例的用量在 run 收尾经 record_llm_tokens 累入（用量读取
  是消费实例属性，gateway 本体零改动）；
- ingestion_queue_depth：摄取队列深度，**DB 口径**——document_versions 中
  status='staging' 计数，/metrics 抓取时经 set_function 实时查询。取舍：
  比 Redis LLEN 更贴业务语义（staging 行即"待摄取版本"，天然含派发失败
  重试场景），且不耦合 Celery 内部队列名/约定；查询失败返回 -1（未知）
  不抛异常，保证 /metrics 端点可用性。
"""

import logging
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("app.core.metrics")

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests by method, route template and status",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds",
    ["method", "path"],
)
llm_tokens_total = Counter(
    "llm_tokens_total", "Cumulative LLM token usage", ["kind"],
)


def _queue_depth() -> int:
    """staging 计数（set_function 在 /metrics 抓取时调用）；失败返回 -1。"""
    try:
        from sqlalchemy import text

        from app.core.db import get_engine
        with get_engine().connect() as conn:
            return int(
                conn.execute(
                    text("SELECT COUNT(*) FROM document_versions WHERE status = 'staging'")
                ).scalar_one()
            )
    except Exception:
        log.warning("ingestion_queue_depth 查询失败（返回 -1）", exc_info=True)
        return -1


ingestion_queue_depth = Gauge(
    "ingestion_queue_depth", "Document versions awaiting ingestion (status=staging)"
)
ingestion_queue_depth.set_function(_queue_depth)


def record_llm_tokens(prompt: int, completion: int) -> None:
    """run 收尾把 gateway 实例用量累入全局计数器（agent_graph 调用）。"""
    try:
        if prompt:
            llm_tokens_total.labels(kind="prompt").inc(prompt)
        if completion:
            llm_tokens_total.labels(kind="completion").inc(completion)
    except Exception:
        log.warning("llm_tokens_total 打点失败", exc_info=True)


def exposition() -> Response:
    """/metrics 响应（exposition 格式）。

    认证豁免理由：监控端点，输出仅聚合值（计数/延迟/token 累计/队列深度），
    无任何文档内容与用户数据，与 /healthz 同为无认证端点。
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def request_latency_middleware(request: Request, call_next):
    """全局请求中间件：计时 + 打点 + 每请求一行结构化日志。

    打点整体 try/except——采集失败只 warning，绝不影响业务请求；
    日志行只含 method/路由模板/status/耗时，不含 query/body/头部。
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    try:
        route = request.scope.get("route")  # call_next 后路由已解析；404 无 route
        path = route.path if route is not None else "unmatched"
        method, status = request.method, response.status_code
        http_requests_total.labels(method, path, str(status)).inc()
        http_request_duration_seconds.labels(method, path).observe(elapsed_ms / 1000)
        log.info(
            "http_request method=%s route=%s status=%s duration_ms=%.1f",
            method, path, status, elapsed_ms,
        )
    except Exception:
        log.warning("metrics middleware 打点失败", exc_info=True)
    return response
