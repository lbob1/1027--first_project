"""统一 KN 错误码与业务异常（M-S0-T04）。

错误码表逐字照抄 00 文件第五节（12 个：KN-400/401/403/404/409/410/422/
429/500/502/503/ORG-001），不得增删改（细则 6）。
"""

# 00 文件第五节：稳定错误码表（code -> (http_status, 默认 message)），逐字照抄
ERROR_TABLE: dict[str, tuple[int, str]] = {
    "KN-400": (400, "请求参数校验失败"),
    "KN-401": (401, "未认证 / token 失效"),
    "KN-403": (403, "无该 workspace 权限"),
    "KN-404": (404, "资源不存在（不泄露是否存在于其他 workspace）"),
    "KN-409": (409, "状态冲突（如版本非 active）"),
    "KN-410": (410, "需要二次确认（审批未通过即执行敏感操作）"),
    "KN-422": (422, "文档格式不支持 / 解析失败"),
    "KN-429": (429, "超出预算限制（token / 调用次数）"),
    "KN-500": (500, "服务内部错误"),
    "KN-502": (502, "上游模型服务（百炼）调用失败"),
    "KN-503": (503, "数据库 / Redis / MinIO 不可用"),
    "KN-ORG-001": (400, "上游返回内容无法解析为合法结构"),
}


class AppError(Exception):
    """业务异常：携带表内 code、对应 http_status 与可选 data；message 默认取表内值。"""

    def __init__(self, code: str, message: str | None = None, *, data=None) -> None:
        if code not in ERROR_TABLE:
            raise ValueError(f"未知错误码: {code}（只允许使用 00 文件第五节错误码表）")
        status, default_message = ERROR_TABLE[code]
        self.code = code
        self.http_status = status
        self.message = message or default_message
        self.data = data
        super().__init__(self.message)
