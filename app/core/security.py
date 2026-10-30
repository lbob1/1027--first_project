"""认证基座：bcrypt 密码哈希 + HS256 JWT（M-S5-T01）。

**选型**：直接用官方 bcrypt 库，不引 passlib——后者自 2024 年起维护
停滞，与 bcrypt>=4 的版本探测（__about__ 移除）存在长期未修的兼容
告警，新项目不引入（任务书拍板）。

**密码比对**：bcrypt.checkpw 恒定时间校验（硬约束）；库内哈希串损坏
按"不匹配"返回 False，不向调用方泄露异常细节。

**JWT**：HS256，claims 最小集 {sub=str(user_id), iat, exp}（硬约束：
不放用户名/密码哈希等冗余 claims）。expires_delta 单位秒，None 取
配置 JWT_EXPIRE。

**取码依据（00 第五节 12 码表）**：认证失败类码只有 KN-401（401,
"未认证 / token 失效"）——签名无效/格式错/过期统一 KN-401，不发明
新码。**过期与无效共用一码的取舍**：表内无更细分码；message 区分
"token 已过期"（客户端据此预刷新）与表默认值，HTTP 层同为 401。

**fail-fast 防御**：JWT_SECRET_KEY 为空串时签发与校验均显式抛
KN-500（绝不空密钥静默签发）；warn_if_secret_missing 供启动日志
warning（服务可起，认证调用拒绝服务）。

**细则 9**：凭据/token 全程不入日志——本模块 log 只记动作不记值。
"""

import logging
import time
import uuid
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("app.core.security")

_ALGORITHM = "HS256"


def warn_if_secret_missing() -> None:
    """启动自检：密钥缺失仅 warning（不阻断启动，认证调用将 fail-fast）。"""
    if not get_settings().JWT_SECRET_KEY:
        log.warning(
            "JWT_SECRET_KEY 未配置——auth/login 与 token 校验将拒绝服务"
            "（fail-fast，绝不空密钥静默签发）"
        )


def _secret() -> str:
    """取签名密钥；空串 fail-fast（防御配置缺失被静默放过）。"""
    secret = get_settings().JWT_SECRET_KEY
    if not secret:
        # 只报状态不报值（值本身为空，亦不含其他配置，细则 9）
        raise AppError("KN-500", "JWT_SECRET_KEY 未配置，拒绝签发/校验 token")
    return secret


def hash_password(plain: str) -> str:
    """bcrypt 哈希（gensalt 默认 12 轮），返回 ascii 密文入库 users.password_hash。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """恒定时间密码比对（bcrypt.checkpw，硬约束）；哈希串损坏按不匹配。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def issue_token(user_id: uuid.UUID, *, expires_delta: int | None = None) -> str:
    """签发 HS256 token；expires_delta 秒（None 取配置 JWT_EXPIRE），负值可造过期 token。"""
    secret = _secret()
    now = int(time.time())
    ttl = expires_delta if expires_delta is not None else get_settings().JWT_EXPIRE
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> uuid.UUID:
    """校验并解析 token，返回 user_id。

    签名无效/格式错/过期统一 KN-401（ExpiredSignatureError 是
    InvalidTokenError 子类，须先捕过期以区分 message；取码依据见模块
    docstring）。sub 非 UUID 视为无效 token（同样 KN-401）。"""
    secret = _secret()
    try:
        payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AppError("KN-401", "token 已过期") from exc
    except jwt.InvalidTokenError as exc:  # 签名无效/格式错等全部落此基类
        raise AppError("KN-401") from exc
    try:
        return uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise AppError("KN-401") from exc
