# MiniKnora 应用镜像（M-S6-T01）。
# 核心设计：同镜像不同 command——CMD 默认 uvicorn（api），worker 在 compose.yaml
# 用同一镜像覆盖 command 为 celery worker，两个服务共享一个镜像。
#
# uv 安装修理取舍：选 COPY --from=ghcr.io/astral-sh/uv 官方多阶段直取二进制，
# 而非 pip install uv——后者多一次 pip 解析/下载（构建期网络环节越多越脆弱，
# S0 已实证 pypi.org 直连超时），且官方镜像层固定、可被 Docker 缓存复用。

FROM python:3.12-slim

# 构建期依赖安装走清华镜像（S0 实证 pypi.org 直连超时，构建期同样需要镜像源）；
# UV_LINK_MODE=copy 规避跨文件系统 hardlink 警告。
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# 非 root 用户（验收：容器内 whoami = appuser）
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# 先只 COPY 依赖清单（利用层缓存：pyproject/uv.lock 不变则依赖层直接复用）
COPY pyproject.toml uv.lock ./

# --frozen 锁定 uv.lock 不重解析；--no-dev 不装测试/工具依赖；
# --no-install-project 不构建项目自身包（代码以普通文件 COPY 进 /app，
# uvicorn 从工作目录直接 import app，无需安装元数据）
RUN uv sync --frozen --no-dev --no-install-project

# venv 二进制进 PATH：python/uvicorn/celery 均指向虚拟环境
ENV PATH="/app/.venv/bin:$PATH"

# 再 COPY 应用代码（.dockerignore 已排除凭据/测试/文档等无关内容）
COPY app ./app

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# CMD 默认 api 入口；worker 由 compose command 覆盖（celery），镜像保持唯一
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
