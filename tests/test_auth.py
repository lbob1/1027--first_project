"""认证组测试（M-S5-T01 行为固化，M-S5-T03）：security 纯函数层 + login 端点。

- 纯函数层：hash/verify 往返、损坏哈希串、issue/decode 往返、过期（负
  delta）/伪造签名/垃圾串/非 UUID sub、空密钥 fail-fast 双路径
  （env 覆盖 + get_settings.cache_clear，finally 恢复原值——不触 .env 本体）；
- login 端点（TestClient）：app 经 get_session 独立连接读库，看不见
  savepoint 未提交数据——故造数走真实提交 + fixture finally 清理
  （与 test_ingestion_smoke 同款取舍）；
- 错密码 与 不存在用户名 的响应逐字节一致（T01 防用户名探测语义固化）。
"""

import os
import uuid
from sqlalchemy import delete

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import decode_token, hash_password, issue_token, verify_password
from app.main import app as api_app
from app.models.models import User


# ---------- 密码哈希（bcrypt） ----------

def test_password_hash_verify_roundtrip():
    h = hash_password("correct-horse-battery")
    assert h != "correct-horse-battery"  # 确为哈希非明文
    assert verify_password("correct-horse-battery", h) is True
    assert verify_password("wrong-password", h) is False


def test_password_verify_corrupted_hash_false():
    """损坏/截断哈希串按不匹配返回 False，不向调用方抛异常（T01 语义）。"""
    assert verify_password("x", "not-a-real-hash") is False
    assert verify_password("x", "$2b$12$truncated") is False


# ---------- JWT 签发/校验 ----------

def test_token_roundtrip_sub():
    uid = uuid.uuid4()
    assert decode_token(issue_token(uid)) == uid


def test_token_expired_kn401_message_distinct():
    """过期（负 expires_delta 造）→ KN-401 且 message 区分"token 已过期"。"""
    tok = issue_token(uuid.uuid4(), expires_delta=-10)
    with pytest.raises(AppError) as ei:
        decode_token(tok)
    assert ei.value.code == "KN-401"
    assert ei.value.message == "token 已过期"


def test_token_forged_signature_kn401_default_message():
    """伪造签名 → KN-401 表默认 message（与过期区分）。"""
    tok = pyjwt.encode({"sub": str(uuid.uuid4())}, "forged-secret", algorithm="HS256")
    with pytest.raises(AppError) as ei:
        decode_token(tok)
    assert ei.value.code == "KN-401"
    assert ei.value.message == "未认证 / token 失效"


def test_token_garbage_kn401():
    with pytest.raises(AppError) as ei:
        decode_token("garbage.token.value")
    assert ei.value.code == "KN-401"


def test_token_sub_not_uuid_kn401():
    """签名合法但 sub 非 UUID → 无效 token（KN-401，T01 语义）。"""
    tok = pyjwt.encode({"sub": "not-a-uuid"},
                       get_settings().JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(AppError) as ei:
        decode_token(tok)
    assert ei.value.code == "KN-401"


def test_empty_secret_fail_fast_issue_and_decode():
    """空密钥 fail-fast 双路径：签发与校验均 KN-500（env 覆盖+cache_clear，用完恢复）。"""
    original = os.environ.get("JWT_SECRET_KEY")
    try:
        os.environ["JWT_SECRET_KEY"] = ""
        get_settings.cache_clear()
        uid = uuid.uuid4()
        with pytest.raises(AppError) as ei:
            issue_token(uid)
        assert ei.value.code == "KN-500"
        with pytest.raises(AppError) as ei2:
            decode_token("anything")
        assert ei2.value.code == "KN-500"
    finally:
        if original is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = original
        get_settings.cache_clear()


# ---------- login 端点（TestClient，真实提交造数） ----------

@pytest.fixture()
def login_user():
    """真实提交造登录用户（TestClient 独立连接可见）；结束清理该用户。"""
    username = f"t03-auth-{uuid.uuid4().hex[:8]}"
    with get_session() as s:
        u = User(username=username, password_hash=hash_password("t03-login-pass"))
        s.add(u)
        s.flush()
        uid = u.user_id
    yield username, uid
    with get_session() as s:
        s.execute(delete(User).where(User.user_id == uid))


def test_login_success_kn000_and_token_immediately_valid(login_user):
    username, uid = login_user
    r = TestClient(api_app).post(
        "/api/v1/auth/login",
        json={"username": username, "password": "t03-login-pass"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "KN-000" and body["message"] == "ok"
    d = body["data"]
    assert d["token_type"] == "bearer"
    assert d["expires_in"] == get_settings().JWT_EXPIRE
    assert decode_token(d["token"]) == uid  # 端到端：登录签发的 token 立即可校验


def test_login_wrong_password_and_missing_user_identical_bytes(login_user):
    """错密码 与 不存在用户名：同状态码 + 响应体逐字节一致（不泄露存在性）。"""
    username, _ = login_user
    client = TestClient(api_app)
    r1 = client.post("/api/v1/auth/login",
                     json={"username": username, "password": "definitely-wrong"})
    r2 = client.post("/api/v1/auth/login",
                     json={"username": f"ghost-{uuid.uuid4().hex[:8]}", "password": "whatever"})
    assert r1.status_code == r2.status_code == 401
    assert r1.content == r2.content  # 逐字节一致断言
    b = r1.json()
    assert b["code"] == "KN-401" and b["message"] == "用户名或密码错误"
