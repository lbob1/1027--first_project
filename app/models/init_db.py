"""建表脚本（M-S1-T01）。幂等：可重复运行不报错。

顺序：CREATE EXTENSION IF NOT EXISTS vector → Base.metadata.create_all。
连接串从 get_settings() 读取，禁止打印完整连接串（细则 9）。
用法：uv run python -m app.models.init_db
"""

import logging

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.logger import setup_logging
from app.models.models import Base


def main() -> None:
    setup_logging()
    log = logging.getLogger("app.models.init_db")
    engine = create_engine(get_settings().DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    log.info("init_db 完成：pgvector 扩展已确保，7 张表已确保存在（幂等可重复执行）")


if __name__ == "__main__":
    main()
