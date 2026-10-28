"""统一日志配置与凭据脱敏（M-S0-T03）。

00 文件第六节细则 9：凭据不入日志——凡输出中含 API key、Authorization、
SECRET、PASSWORD、TOKEN 等字段值一律打码为 ***。
脱敏发生在 Formatter.format() 之后，对 %(message)s 与 %s 参数插值结果统一生效。
"""

import logging
import re
import sys

# 敏感字段名 + 分隔符 + 值（值整体替换为 ***；bearer 前缀一并吞掉）。
# 前缀用 lookbehind 排除字母数字而非 \b：复合名（OPENAI_API_KEY / MINIO_SECRET_KEY）
# 中下划线与字母同为 word 字符，\b 在 `_API_KEY` 处不成立，会导致漏打码。
_SECRET_FIELD_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(api[_-]?key|authorization|secret(?:_key)?|password|passwd|token)\b"
    r"(\s*[=:：]\s*)(?:bearer\s+)?\S+"
)
# 无字段名兜底：OpenAI 风格密钥 sk-xxxx
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")

_MASK = r"\1\2***"


def mask_secrets(text: str) -> str:
    """对文本中的敏感字段值打码为 ***。"""
    text = _SECRET_FIELD_RE.sub(_MASK, text)
    return _SK_RE.sub("***", text)


class MaskingFormatter(logging.Formatter):
    """在标准格式化之后执行脱敏的 Formatter。"""

    def format(self, record: logging.LogRecord) -> str:
        return mask_secrets(super().format(record))


def setup_logging(level: int = logging.INFO) -> None:
    """初始化根 logger（幂等：已有 handler 时不重复配置）。"""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            MaskingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
        root.setLevel(level)
    # uvicorn 自带 handler 会绕过脱敏 Formatter 直接打印 traceback
    # （Starlette ServerErrorMiddleware 处理异常后仍 re-raise，uvicorn 层再次输出），
    # 清空其 handler 并 propagate 到 root，让全部输出统一经脱敏（细则 9）。
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def get_logger(name: str) -> logging.Logger:
    """获取业务 logger（经 setup_logging 后输出自动脱敏）。"""
    return logging.getLogger(name)
