# MiniKnora

企业级多租户知识库问答系统（RAG + Agent），对标腾讯 WeKnora 的学习复刻版。

## 功能

- **文档摄取**：md/txt/docx/pdf 上传，扫描件自动 OCR，异步管线入库（MinIO + Postgres/pgvector）
- **混合检索问答**：BM25 全文 + 向量语义 + RRF 融合 + rerank 精排，SSE 流式回答带溯源引用，支持多轮会话
- **版本管理**：文档版本不可变，激活切换即回滚
- **多租户隔离**：工作区隔离 + JWT 认证，跨区访问不泄露存在性
- **Agent 审批**：删除文档走审批流（挂起→确认→执行+审计）
- **预算护栏 / 监控指标**：单轮 token 限额 + Prometheus 格式 /metrics
- **质量评测**：黄金集 recall@5 / 引用正确率 / 隔离零泄露

## 快速开始

```bash
# 0. 前置：启动 Docker Desktop，复制 .env.example 为 .env 并填入真实值（含百炼 API key）
cp .env.example .env

# 1. 一键启动（5 容器：pg/redis/minio/api/worker）
docker compose up -d

# 2. 等容器 healthy 后，浏览器打开交互文档，登录→上传→问答
#    http://localhost:8000/docs
```

不使用容器（宿主开发模式）：

```bash
uv sync                                              # 安装依赖（清华镜像）
docker compose up -d pg redis minio                  # 只起基础服务
uv run python -m app.models.init_db                  # 建表
uv run uvicorn app.main:app --port 8000              # API
uv run celery -A app.workers.celery_app worker -l info --pool=solo   # worker（Windows 需 --pool=solo）
```

## 测试与评测

```bash
uv run pytest                              # 35 个自动化测试
uv run python eval/run_eval.py --phase a   # 黄金集质量（recall@5 + 引用正确率）
uv run python eval/run_eval.py --phase b   # B 区隔离零泄露
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [GUIDE.md](GUIDE.md) | **项目指南**：全部文件逐一概述 + 运行流程图 + 功能全景 |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | 前端 API 契约（冻结版 v1.0） |
| [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) | v1.0 终验报告 |
| [STATUS.md](STATUS.md) | 32 任务执行台账 |
