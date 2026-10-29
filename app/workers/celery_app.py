"""Celery 基座（M-S2-T03）。

- broker 与 result backend 均为 REDIS_URL（get_settings() 读取）；
- 序列化一律 json（任务要求）；
- add 为基座链路验证任务（P-S2 实证用，T04 起可删）；
- Windows 本地启动 worker：uv run celery -A app.workers.celery_app worker
  --pool=solo -l info（--pool=solo 为 Windows 必要参数，见 STATUS 备注）。
"""

import logging

from celery import Celery

from app.core.config import get_settings

log = logging.getLogger("app.workers.celery_app")

_settings = get_settings()

celery_app = Celery(
    "miniknora",
    broker=_settings.REDIS_URL,
    backend=_settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
)


@celery_app.task(name="miniknora.debug.add")
def add(x: int, y: int) -> int:
    """基座链路验证任务（仅证明 broker/backend 打通，可删）。"""
    return x + y
