"""MiniKnora FastAPI 入口（M-S0-T04）。

- 启动即初始化脱敏日志（细则 9）并加载配置（配置错误尽早暴露）；
- 全局异常处理器统一输出 {code, message, data}（00 文件第十一节）；
- 客户端只见 code/message，不返回堆栈与敏感配置值；服务端日志经
  MaskingFormatter 脱敏（含 traceback 全文）。
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.core.config import get_settings
from app.core.errors import AppError, ERROR_TABLE
from app.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app.main")
get_settings()  # 启动即校验必填变量（OPENAI_API_KEY / DATABASE_URL）

from app.core.security import warn_if_secret_missing  # noqa: E402
from app.core.metrics import exposition, request_latency_middleware  # noqa: E402

warn_if_secret_missing()  # M-S5-T01：JWT 密钥缺失启动 warning（认证调用 fail-fast）


def unified(code: str, message: str, status: int, data=None) -> JSONResponse:
    """统一响应结构（00 文件第十一节）。"""
    return JSONResponse(
        status_code=status, content={"code": code, "message": message, "data": data}
    )


app = FastAPI(title="MiniKnora")

from app.api.status import router as status_router  # noqa: E402
from app.api.documents import router as documents_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402

app.include_router(status_router)  # M-S2-T03：摄取状态查询
app.include_router(documents_router)  # M-S2-T06：上传 API
app.include_router(chat_router)  # M-S3-T04：SSE 流式问答
app.include_router(auth_router)  # M-S5-T01：JWT 登录（本任务唯一 main.py 路由改动）
app.middleware("http")(request_latency_middleware)  # M-S6-T02：请求指标+日志（打点 try/except 不影响业务）


@app.get("/healthz")
def healthz() -> dict:
    """健康检查（S0-AC-1）。"""
    return {
        "code": "KN-000",
        "message": "ok",
        "data": {"service": "MiniKnora", "version": "0.1.0"},
    }


@app.get("/metrics")
def metrics() -> Response:
    """监控端点（M-S6-T02）：exposition 格式聚合值，认证豁免（理由见 metrics.exposition）。"""
    return exposition()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.error("AppError code=%s message=%s path=%s", exc.code, exc.message, request.url.path)
    return unified(exc.code, exc.message, exc.http_status, exc.data)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 参数校验失败映射到表内 KN-400；不回显原始输入，只留摘要（细则 9）
    logger.warning("validation error path=%s errors=%d", request.url.path, len(exc.errors()))
    return unified("KN-400", ERROR_TABLE["KN-400"][1], 400)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return unified("KN-404", ERROR_TABLE["KN-404"][1], 404)
    # 其余 HTTP 异常（如 405）不发明新错误码，body 用 KN-500 语义，原始状态码保留在 HTTP 层与日志
    logger.warning("HTTPException status=%s path=%s", exc.status_code, request.url.path)
    return unified("KN-500", ERROR_TABLE["KN-500"][1], exc.status_code)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 堆栈只进服务端日志（经脱敏 Formatter，含 traceback 全文），客户端只见 KN-500
    logger.exception("unhandled exception path=%s", request.url.path)
    return unified("KN-500", ERROR_TABLE["KN-500"][1], 500)
