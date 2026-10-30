"""认证端点与当前用户依赖（M-S5-T01）。

- POST /api/v1/auth/login：用户名+密码换 token。**用户不存在与密码
  错误返回同一错误响应**（同 code 同 message，不泄露用户名存在性——
  细则 1"不泄露存在性"思想延伸到用户维度）；
- get_current_user_id：FastAPI 依赖，解析 Authorization: Bearer →
  decode_token → uuid.UUID（T02 批量接入业务端点用，本任务不改业务
  端点，避免半切换状态）；
- **无注册端点**（00 契约未定义 POST /auth/register 等）：dev 用户经
  脚本直接造（security.hash_password 写 users 表）——dev 路径，生产
  需补用户管理流程（S6 观察项）；
- users.username 无索引：登录按 username 等值查询在 dev 规模（行数
  百级）全表 scan 可接受；上量后补 index（模型改动留 T02+ 评审）；
- **细则 9**：密码/token 全程不入日志（失败日志记 username 供排障，
  username 非凭据）；响应体不回显请求输入。

时序侧信道：用户不存在跳过 bcrypt 比对、响应略快——dev 阶段接受，
S6 可加哑哈希比对均衡（正文一致性已保证，时序不属本任务验收）。
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import decode_token, issue_token, verify_password
from app.models.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

log = logging.getLogger("app.api.auth")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest) -> dict:
    """登录换 token：KN-000 + {token, token_type="bearer", expires_in}。"""
    with get_session() as session:
        user = session.execute(
            select(User).where(User.username == body.username)
        ).scalar_one_or_none()
        ok = user is not None and verify_password(body.password, user.password_hash)
    if not ok:
        # 不存在与密码错误同一响应（同 code 同 message，逐字节一致）
        log.info("login failed username=%s", body.username)
        raise AppError("KN-401", "用户名或密码错误")
    token = issue_token(user.user_id)
    log.info("login ok user_id=%s", user.user_id)  # 不记 token（细则 9）
    return {
        "code": "KN-000",
        "message": "ok",
        "data": {
            "token": token,
            "token_type": "bearer",
            "expires_in": get_settings().JWT_EXPIRE,
        },
    }


def get_current_user_id(
    authorization: str | None = Header(default=None),
) -> uuid.UUID:
    """FastAPI 依赖：Authorization: Bearer <token> → user_id（uuid.UUID）。

    缺头/非 Bearer/空 token/无效/过期统一 KN-401（HTTP 401）。"""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip() or None
    if token is None:
        raise AppError("KN-401", "缺少 Bearer 凭据")
    return decode_token(token)
