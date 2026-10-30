"""统一配置加载（M-S0-T03）。

pydantic-settings 从仓库根 .env 读取变量并做类型校验；凭据只进内存，
禁止硬编码、禁止打印完整 Settings（00 文件第六节细则 9：凭据不入日志）。

变量命名以 00/01 文件口径为准（.env.example 为权威清单）。
用户 .env 中如存在旧命名（OPENAI_BASE_URL / MODEL_NAME 等），
需在 S3 模型调用前迁移为标准名，详见任务计划表问题记录。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # .env 中存在本阶段尚未声明的变量（模型名、JWT 过期时间等），显式忽略
        extra="ignore",
    )

    # ---------- 模型（compatible-mode） ----------
    OPENAI_API_BASE: str = ""
    OPENAI_API_KEY: str
    CHAT_MODEL: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 1024

    # ---------- 数据库 / 缓存 / 对象存储 ----------
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "miniknora"

    # ---------- 上传限制 ----------
    MAX_UPLOAD_MB: int = 20  # 单文件大小上限（MB），S2-T06 早期快速失败用

    # ---------- Rerank（M-S3-T04：DashScope 原生端点，不在 compatible-mode） ----------
    RERANK_MODEL: str = "gte-rerank-v2"  # 老 gte-rerank 部分账号未开通（403 AccessDenied，T04 实测）
    RERANK_ENABLED: bool = True  # false 整体跳过精排（降级为 rrf_score 原序）

    # ---------- 认证（S5 起使用） ----------
    JWT_SECRET_KEY: str = ""
    JWT_EXPIRE: int = 1800  # token 有效期（秒），S5-T01 起使用


@lru_cache
def get_settings() -> Settings:
    """返回全局单例 Settings（lru_cache 保证只加载一次）。"""
    return Settings()
