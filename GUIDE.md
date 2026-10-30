# MiniKnora 项目指南（GUIDE）

> 全部文件逐一概述 + 主运行文件 + 功能全景 + 运行流程图。
> 契约细节见 [docs/API_CONTRACT.md](docs/API_CONTRACT.md)，终验报告见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

---

## 一、这个项目能干什么（功能全景）

MiniKnora 是**企业级多租户知识库问答系统**（RAG + Agent），一键容器化交付：

| 功能 | 说明 |
|---|---|
| 文档摄取 | 上传 md/txt/docx/pdf；扫描件 PDF 自动 OCR 兜底；异步管线（MinIO→解析→切块→向量化→pgvector 落库） |
| 混合检索 | BM25 全文（tsv 生成列）+ 向量语义（HNSW）+ RRF 融合 + rerank 精排（超时自动降级） |
| 流式问答 | SSE 输出：sources→token×N→budget→trace→done；回答带溯源引用；支持多轮会话（thread_id） |
| 版本管理 | 文档版本不可变（staging→active→retired），激活切换即回滚 |
| 多租户隔离 | 工作区隔离 + JWT 认证 + 成员角色；跨区访问一律 KN-404 不泄露存在性 |
| Agent 审批 | 意图路由（检索/删除）；删除走审批流：挂起→确认→执行+审计落库 |
| 预算护栏 | 单轮 token / 工具调用限额，超限中断并记录 trace |
| 监控指标 | GET /metrics（Prometheus 格式）：请求数/延迟/token 消耗/摄取队列深度 + 请求日志中间件 |
| 质量评测 | 黄金集评测：recall@5 + 引用正确率 + B 区零泄露验证 |
| 容器交付 | docker compose 五容器（pg/redis/minio/api/worker）一键复现，非 root 镜像 |

## 二、主运行文件

| 入口 | 文件 | 怎么跑 |
|---|---|---|
| **主程序（API 服务）** | **`app/main.py`** | `uv run uvicorn app.main:app --port 8000` → 浏览器开 `http://localhost:8000/docs` 交互测试全套功能 |
| 后台 worker | `app/workers/celery_app.py` | `uv run celery -A app.workers.celery_app worker -l info --pool=solo`（Windows 宿主必须 --pool=solo；容器内不用） |
| 黄金集评测 | `eval/run_eval.py` | `uv run python eval/run_eval.py --phase a`（质量）→ `--phase b`（隔离） |
| 全量测试 | `tests/`（conftest.py 为入口夹具） | `uv run pytest` |

**最简体验路径**：`docker compose up -d` → 等 5 容器 healthy → 浏览器 `http://localhost:8000/docs`。

## 三、运行流程图

```
 浏览器 http://localhost:8000/docs
        │
        │ ① 登录 POST /api/v1/auth/login → 拿 JWT token
        ▼
 ② 上传文档 POST /workspaces/{ws}/documents
        │      写 MinIO + 建 staging 版本 + 投递 Celery 任务
        ▼
 worker 异步摄取: 解析(OCR 兜底) → 切块 → 百炼向量化 → 落库
        │      （文档 staging → active）
        ▼
 ③ 提问 POST /workspaces/{ws}/chat（SSE 流式）
        │      LangGraph: 意图路由 → 混合检索(BM25+向量+RRF+rerank)
        │      → LLM 流式回答（带溯源引用；删除意图走审批挂起）
        ▼
 ④ 监控 GET /metrics（请求数/延迟/token/队列深度）
```

## 四、全部文件逐一概述

### 根目录

| 文件 | 作用 |
|---|---|
| `app/main.py` | **主运行文件**：FastAPI 入口，挂路由/中间件/异常处理/日志 |
| `pyproject.toml` | 依赖与工具配置（uv 管理） |
| `uv.lock` | 依赖锁（--frozen 可复现安装） |
| `compose.yaml` | 五容器编排：pg/redis/minio + api/worker |
| `Dockerfile` | 应用镜像：python:3.12-slim + uv + 非 root appuser |
| `.env` | 真实凭据（**永不入库/入镜像**，本地自建） |
| `.env.example` | 凭据占位模板（入库，照抄填值） |
| `GUIDE.md` | 本文件 |
| `README.md` | 项目简介与快速开始 |
| `STATUS.md` | 32 任务执行台账（四态+实证证据） |
| `00_MiniKnora_项目需求说明.md` | 原始需求（错误码表/前端契约/细则） |
| `01_MiniKnora_分阶段执行计划.md` | S0~S6 分阶段计划 |
| `MiniKnora_任务计划表.md` | 32 任务一览表 |
| `AGENTS.md` | AI 协作代理说明 |
| `src/pyknora/__init__.py` | 打包容器壳（未使用，保留结构） |
| `.gitignore` / `.dockerignore` / `.gitmodules` / `.python-version` | 忽略与工具配置 |

### app/api（HTTP 端点层）

| 文件 | 作用 |
|---|---|
| `auth.py` | 登录端点：验密码 → 发 JWT |
| `documents.py` | 上传端点（JWT 认证 + 成员判定） |
| `status.py` | 摄取状态查询端点（staging 附处理提示） |
| `chat.py` | SSE 问答端点（含审批恢复：thread_id + confirm） |

### app/core（基础设施层）

| 文件 | 作用 |
|---|---|
| `config.py` | 配置加载（pydantic-settings 读 .env，单例） |
| `db.py` | 数据库 engine/session（事务提交/回滚/close） |
| `errors.py` | 12 个 KN 错误码统一异常 |
| `logger.py` | 日志 + 凭据自动脱敏 Formatter |
| `security.py` | 密码哈希/校验 + JWT 签发/解码 |
| `gateway.py` | 百炼 LLM 封装（对话调用 + 用量统计） |
| `budget.py` | 预算护栏（token/工具调用限额） |
| `policy.py` | 工具策略（意图→可用工具白名单） |
| `tool_registry.py` | 工具注册表（检索/删除文档工具） |
| `approval.py` | 审批门（LangGraph interrupt 挂起/恢复） |
| `trace.py` | RunTracer（单轮问答全轨迹记录） |
| `metrics.py` | 四类指标 + 请求日志中间件 |
| `context.py` | 请求上下文传递（user/thread_id） |

### app/graphs（Agent 编排）

| 文件 | 作用 |
|---|---|
| `agent_graph.py` | LangGraph 主图：意图路由→工具执行→检索/删除分支→流式答案→审批挂起恢复 |

### app/models（数据层）

| 文件 | 作用 |
|---|---|
| `models.py` | 7 表 ORM（users/workspaces/members/documents/versions/chunks/messages，含 pgvector/HNSW/GIN/生成列） |
| `init_db.py` | 建表脚本（幂等）：`uv run python -m app.models.init_db` |

### app/services（业务层）

| 文件 | 作用 |
|---|---|
| `workspace.py` | 工作区 CRUD（KN-404 隔离语义） |
| `document.py` | 文档 CRUD（强制 workspace_id 进 WHERE） |
| `version.py` | 版本三入口（建版/激活/标记失败，FOR UPDATE 并发安全） |
| `upload.py` | 上传编排（MinIO + staging + 投递 Celery） |
| `storage.py` | MinIO 客户端（三维对象键：区/文档/版本） |
| `parser.py` | 文件解析（pdf 文本层+扫描 OCR / docx / md / txt） |
| `chunker.py` | 文本切块 |
| `embedding.py` | 百炼向量化（1024 维） |
| `retrieval_fts.py` | BM25 全文检索（tsv 生成列） |
| `retrieval_vec.py` | 向量检索（HNSW） |
| `retrieval_hybrid.py` | RRF 融合两路结果 |
| `rerank.py` | 重排（超时/异常降级原序） |

### app/workers（异步任务）

| 文件 | 作用 |
|---|---|
| `celery_app.py` | Celery 实例（broker/backend = Redis） |
| `ingestion.py` | 摄取任务：解析→切块→向量化→chunks 落库→active |

### tests（自动化测试，`uv run pytest`）

| 文件 | 作用 |
|---|---|
| `conftest.py` | 夹具：savepoint 事务回滚零残留 + 数据工厂 + JWT |
| `test_isolation.py` | 多租户隔离 12+ 用例（跨区 KN-404/KN-403/版本不可变） |
| `test_auth.py` | 认证组（哈希/JWT 往返/过期/伪造/login 逐字节一致） |
| `test_retrieval.py` | 检索组（混合检索字段/隔离/retired 不可见/rerank 降级） |
| `test_approval.py` | 审批组（挂起/恢复删除/拒绝保留/审计行） |
| `test_ingestion_smoke.py` | 摄取冒烟（上传→摄取→active 全链，真实 API） |

### eval（质量评测）

| 文件 | 作用 |
|---|---|
| `run_eval.py` | **黄金集评测主脚本**：phase a 质量分 / phase b 隔离零泄露 |
| `golden_set.json` | 黄金集数据（12 条问答 + 12 条隔离用例） |
| `retrieval_eval.py` | 检索专项评测脚本（早期版本） |
| `cases.json` | 检索评测用例数据 |
| `golden_report.md` / `report.md` | 评测报告（历史结果） |

### docs（文档库）

| 文件 | 作用 |
|---|---|
| `API_CONTRACT.md` | **前端契约冻结版 v1.0**（逐端点 + 差异表） |
| `ACCEPTANCE.md` | v1.0 终验报告（S6 四条验收标准逐条对照） |
| `PRD_PyKnora.md` / `IMPLEMENTATION_STATUS.md` | 产品需求 / 原项目状态 |
| `adr/` | 5 份架构决策记录 |
| `tdd/` | 8 份技术设计文档 |
| `poc/` / `research/` | PoC 资料 / 源架构研究 |

## 五、测试命令速查

```bash
# 前置（一次性）：启动 Docker Desktop → docker compose up -d → .env 按 .env.example 配好 → uv sync

uv run pytest                              # 35 个自动化测试（需三基础服务 + 真实百炼 key）
uv run python eval/run_eval.py --phase a   # 黄金集质量：recall@5 + 引用正确率
uv run python eval/run_eval.py --phase b   # B 区隔离零泄露验证
uv run uvicorn app.main:app --port 8000    # 手动起 API（容器方式则 docker compose up -d 即含）
uv run celery -A app.workers.celery_app worker -l info --pool=solo   # Windows 宿主手动起 worker
```
