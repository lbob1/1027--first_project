# MiniKnora 任务计划表

> 版本：v1.0 ｜ 创建日期：2026-10-28
> 依据：《00_MiniKnora_项目需求说明.md》v2.0、《01_MiniKnora_分阶段执行计划.md》v2.0（任务编号、验收标准原文均沿用 01 文件，不得自行发明任务或降低验收标准）
> 范围：仅开发计划，不含业务代码。
> 上游背景：`docs/`（PRD / tdd / adr）与 `AGENTS.md` 提供契约思想；与本计划冲突时以 00/01 两份文件为准。

## 状态定义（四态）

| 状态 | 含义 |
|---|---|
| NOT_STARTED | 未开始（本表初始状态，全部任务均为此态） |
| PASS | 完成，且对应验收标准的真实运行证据已贴入 STATUS.md |
| FAIL | 已执行但验收未通过（备注记录真实失败原因） |
| BLOCKED | 因依赖/环境/前置问题无法开工（备注记录阻塞原因） |

> 执行纪律（继承 01 文件〇节）：每轮只做一个任务；不虚报；开工先 `git status`；每完成一个任务更新本表状态列与 `STATUS.md`。

## 已确认的决策记录（2026-10-28，用户拍板）

| # | 问题 | 决策 |
|---|---|---|
| D-1 | `document_versions.status` 枚举在 00 文件第四节（{staging, active, retired}）与第十一节/01 文件 P-S2 卡片（含 failed）不一致 | **合并为四态 {staging, active, retired, failed}**；failed 用于解析/摄取失败（对应 KN-422），status 查询接口可返回全部四态 |
| D-2 | DELETE /workspaces/{id}、DELETE /documents/{id}（KN-410 → confirm 双阶段）在 01 任务表无明确承载任务 | **归入 M-S4-T05**（ApprovalManager 落地时一并实现删除类 REST 端点的审批包装）；S1-T02 只做 service 层删除逻辑 |
| D-3 | STATUS.md 创建时机（〇节规范 vs T04 产出物） | **M-S0-T01 即创建** `STATUS.md`（仓库根，与原项目 `docs/IMPLEMENTATION_STATUS.md` 区分）；T04 视为核对在位 |

## 其他消解与观察项（非阻塞，执行时留意）

| # | 事项 | 处理口径 |
|---|---|---|
| O-1 | 00 文件称"约 26 个小任务"，01 文件实际列 32 个 | 以 01 文件任务编号体系为准（32 任务），本表照抄 |
| O-2 | S2-T05"旧版本 chunks 置 retired"：00 文件第四节 chunks 表无 status 列 | retired 是 `document_versions.status` 的值；"旧版本 chunks 退役"通过检索层 JOIN version.status='active' 过滤实现，**chunks 表不加 status 列**（00 第四节表结构为准） |
| O-3 | 00 第四节 status 接口含 pending 提示（S2 验收"停在 staging 且有明确 pending 提示"） | pending 是接口的提示性字段/文案，不是 status 枚举值；枚举仍按 D-1 四态 |
| O-4 | S0-T01 骨架目录未列 `eval/`，而 S3-T06 产出物为 `eval/golden_set.json + eval/run_eval.py` | S0-T01 目录骨架补 `app/eval/`（或根级 `eval/`，与 S3-T06 产出物路径一致，本表按根级 `eval/`） |
| O-5 | 现有工程为 src-layout（`src/pyknora` Hello World，uv_build 后端），S0-T01 要求 `app/` 布局 + `uv run uvicorn app.main:app` | `src/` 原样保留不动；S0-T01 需处理两布局并存的 import 路径问题（见 S0-T01 风险提示与实施要点） |
| O-6 | S3-T04 使用 run_id，但 00 文件 7 表无 runs 表 | 属 MiniKnora 简化设计：run_id 仅存在于 LangGraph Checkpointer（thread 级）与 JSON Trace（细则 12），不建业务 runs 表 |
| O-7 | S1~S4 阶段 API 尚无 JWT（S5 才引入认证），但 S1 验收已要求"以 workspace B 身份查询" | S1~S4 期间身份以 service 层参数显式传递（测试直接传 workspace_id 模拟身份）；JWT/权限在 S5-T01/T02 接入全部端点。这是 01 文件既定顺序，不视为矛盾 |

---

## 一、任务依赖总览

```
S0: T01 → T02 → T03 → T04
S1: T01 → T02 → T03 → T04        （S1 整体依赖 S0-T04）
S2: T01 → T02 → T03 → T04 → T05 → T06   （S2 整体依赖 S1-T04）
S3: T01 → T02 → T03 → T04 → T05 → T06   （S3 整体依赖 S2-T06）
S4: T01 → T02 → T03 → T04 → T05 → T06   （S4 整体依赖 S3-T06）
S5: T01 → T02 → T03               （S5 整体依赖 S4-T06）
S6: T01 → T02 → T03               （S6 整体依赖 S5-T03，可选）
```

单人单轮执行按编号顺序推进；表内"依赖"列给出最小前置集合（并行仅作理论参考，单人按序执行）。

---

## 二、S0：可复现工程 + 基础服务

**阶段目标（01 原文）**：建立 uv 可复现工程骨架，并用 docker-compose 起齐三个基础服务——这是后续一切的地基。

### S0 验收标准（01 原文，编号 S0-AC-1~4）

- **S0-AC-1** ✅ `uv sync && uv run uvicorn app.main:app` 启动成功，/healthz 返回 200；
- **S0-AC-2** ✅ `docker compose up -d` 后 `docker compose ps` 三服务均 healthy；`psql` 可执行 `CREATE EXTENSION vector`；
- **S0-AC-3** ✅ MinIO 控制台可登录，能手工创建 bucket；
- **S0-AC-4** ✅ 制造异常请求返回 `{code: "KN-500", ...}` 统一结构；日志中 API key 脱敏为 `***`。

### M-S0-T01 工程骨架与依赖管理

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | `pyproject.toml` + `uv lock` + 目录骨架（app/api、app/core、app/models、app/services、app/workers、app/graphs、tests/、compose.yaml） |
| 01 原文产出物 | 可 `uv sync` 的空工程 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | 无（基于现有仓库现状，见 O-5） |
| 实施要点 | ① 在现有 `pyproject.toml` 声明 S0 所需依赖（fastapi、uvicorn、pydantic-settings 等，禁止散装 pip install），运行 `uv lock` 生成锁文件；② 创建目录骨架 `app/api/`、`app/core/`、`app/models/`、`app/services/`、`app/workers/`、`app/graphs/`、`tests/`、`eval/`（补 O-4）、`compose.yaml` 占位；③ 处理 src-layout 与 app/ 布局并存（保留 `src/pyknora` 不动，为 `app/` 配置可被 `uv run` 导入，如 pyproject 配置 pythonpath 或调整构建配置）；④ 按 D-3 决策创建根级 `STATUS.md`（01 〇节表格格式），登记本任务状态 |
| 涉及文件路径 | `pyproject.toml`（修改）、`uv.lock`（新增）、`app/**/__init__.py`、`tests/__init__.py`、`compose.yaml`（占位）、`STATUS.md`（新增） |
| 验收映射 | 支撑 S0-AC-1（uv sync 可用性在此奠定）；本任务自检：`uv sync` 成功、`uv run python -c "import app"` 可导入 |
| 落实安全细则 | 无直接条目（细则 9 的 `.env.example` 在 T03，本任务不涉及） |
| 风险提示 | src-layout 与 app/ 并存的 import 路径是本任务最大坑点；`uv run uvicorn app.main:app` 必须真实跑通（O-5） |

### M-S0-T02 基础服务编排

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | `compose.yaml`：PostgreSQL（**装 pgvector 扩展**）+ Redis + MinIO，含健康检查与持久化卷 |
| 01 原文产出物 | 三服务可一键启动 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T01 |
| 实施要点 | ① 编写 `compose.yaml` 三服务：PostgreSQL 采用 **pgvector/pgvector:pg16** 镜像（自带 vector 扩展）、Redis、MinIO；② 每服务配置 healthcheck 与持久化卷（PG 数据卷、MinIO 数据卷）；③ 暴露端口与 `.env` 约定一致（DATABASE_URL/REDIS_URL/MINIO_* 将在 T03 定义）；④ 禁止用 SQLite/Chroma 等替代组件（00 文件第二节职责表） |
| 涉及文件路径 | `compose.yaml` |
| 验收映射 | **S0-AC-2**（三服务 healthy + `CREATE EXTENSION vector`）、**S0-AC-3**（MinIO 控制台登录、建 bucket） |
| 落实安全细则 | 无直接条目（为细则 1/5 提供数据库载体） |

### M-S0-T03 配置加载与日志脱敏

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | `.env.example`（OPENAI_API_BASE/KEY/模型型号/DATABASE_URL/REDIS_URL/MINIO_*）+ 配置加载 + 日志脱敏工具 |
| 01 原文产出物 | config.py + logger.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T01（目录）、M-S0-T02（服务地址约定） |
| 实施要点 | ① `.env.example` 含 OPENAI_API_BASE/OPENAI_API_KEY/对话与向量模型型号/EMBEDDING_DIM（P-S1 卡片要求）/DATABASE_URL/REDIS_URL/MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY/MINIO_BUCKET/JWT 密钥占位（S5 用）；② `app/core/config.py` 用 pydantic-settings 加载 `.env`；③ `app/core/logger.py` 统一日志 + **脱敏过滤器**（API key/AUTHORIZATION/SECRET 等打印为 `***`）；④ 仓库只提交 `.env.example`，真实 `.env` 进 `.gitignore` |
| 涉及文件路径 | `.env.example`、`.gitignore`（核对追加 `.env`）、`app/core/config.py`、`app/core/logger.py` |
| 验收映射 | 支撑 **S0-AC-4**（日志脱敏部分） |
| 落实安全细则 | **细则 9**（凭据不入日志：API key 只存 `.env`、日志统一脱敏）、**细则 4**（EMBEDDING_DIM 等配置命名与 00 文件第七节选型约定一致） |

### M-S0-T04 FastAPI 空应用与统一错误结构

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | FastAPI 空应用 + 全局异常处理器（统一 KN-xxx 错误码结构）+ /healthz + STATUS 文件 |
| 01 原文产出物 | main.py + STATUS.md |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T01、M-S0-T03（异常处理器用 config/logger） |
| 实施要点 | ① `app/main.py` 创建 FastAPI 实例 + `/healthz` 返回 200；② 全局异常处理器统一输出 `{code, message, data}`（00 文件第十一节结构），内置 00 文件第五节 **12 个 KN 错误码**常量表（app/core/errors.py），业务异常类型携带 code；③ 制造异常请求验证 KN-500 结构；④ 核对 `STATUS.md` 在位（D-3：T01 已创建）并登记本任务状态 |
| 涉及文件路径 | `app/main.py`、`app/core/errors.py`、`STATUS.md`（更新） |
| 验收映射 | **S0-AC-1**（启动 + /healthz 200）、**S0-AC-4**（KN-500 统一结构 + 脱敏） |
| 落实安全细则 | **细则 6**（统一错误码：全局异常处理器统一输出，本任务建立机制，后续任务复用） |

---

## 三、S1：数据模型与多级隔离

**阶段目标（01 原文）**：落地 7 张表的 SQLAlchemy 模型（含 pgvector 向量列与 tsvector 生成列）与三级隔离——全项目安全的地基。前置：S0 完成。

### S1 验收标准（01 原文，编号 S1-AC-1~5）

- **S1-AC-1** ✅ 向 workspace A 写入文档后，以 workspace B 身份查询返回**空列表**（不泄露存在性）；
- **S1-AC-2** ✅ 任何"修改版本"的调用被拒绝（代码无此路径 + 测试证明）；
- **S1-AC-3** ✅ 同一文档二次上传后 version_no 递增、旧行原样保留、active_version 指向新行；
- **S1-AC-4** ✅ `SELECT * FROM chunks LIMIT 1` 可见 embedding 与 tsv 列有值（插入测试数据后）；
- **S1-AC-5** ✅ pytest 通过且含至少 6 个隔离/版本负例断言。

### M-S1-T01 七张表 ORM 模型

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 7 张表 ORM 模型：chunks 含 `embedding vector(N)` 与 `tsv tsvector` 生成列（GIN 索引 + 向量索引）；建表与迁移脚本 |
| 01 原文产出物 | models.py + init_db.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T04（可连 PG、pgvector 扩展在位、config 可用） |
| 实施要点 | ① 按 00 文件第四节逐字段定义 7 张表（users/workspaces/workspace_members/documents/document_versions/chunks/messages），**字段名逐字照抄**，主键全部 UUID；② chunks.embedding 用 pgvector 的 `Vector(N)`，N 读 `EMBEDDING_DIM` 配置；tsv 为 tsvector 生成列 + GIN 索引，embedding 建 ivfflat/hnsw 向量索引；③ `document_versions.status` 按 D-1 决策为四态枚举 {staging, active, retired, failed}；④ chunks 表**不加** status 列（O-2）；⑤ init_db 脚本建表并确保 `CREATE EXTENSION IF NOT EXISTS vector`；⑥ 版本不可变在模型层落实：document_versions 不提供 update/delete 接口（P-S1 硬性约束） |
| 涉及文件路径 | `app/models/models.py`、`app/models/init_db.py`（或 `scripts/init_db.py`） |
| 验收映射 | **S1-AC-4**（chunks 列有值）、支撑 S1-AC-1/2/3 |
| 落实安全细则 | **细则 1**（业务表带 workspace_id：documents/document_versions/chunks/messages）、**细则 4**（统一 ID 体系：全部 UUID、命名严格照抄 workspace_id/document_id/version_id/chunk_id/message_id/thread_id）、**细则 5**（版本不可变：模型层无 UPDATE/DELETE 路径） |

### M-S1-T02 workspace / document 基础 CRUD service

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | workspace / document 基础 CRUD service（**每个查询方法强制 workspace_id 过滤**） |
| 01 原文产出物 | services/workspace.py 等 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01 |
| 实施要点 | ① workspace 与 document 的增删查改 service（删除逻辑仅 service 层，REST 路由按 D-2 决策在 S4-T05 实现审批包装）；② **每个查询方法强制 workspace_id 参数并在 SQL WHERE 中生效，禁止先查全表再内存过滤**（P-S1 硬性约束）；③ 查无资源时返回 KN-404 语义（不泄露跨区存在性，细则 1）；④ 用户角色只从数据库判定（P-S1 约束，细则 3），本阶段身份以 service 参数传入（O-7） |
| 涉及文件路径 | `app/services/workspace.py`、`app/services/document.py` |
| 验收映射 | **S1-AC-1**（跨区查询空列表）、支撑 S1-AC-5 |
| 落实安全细则 | **细则 1**（查询强制过滤、KN-404 而非 KN-403）、**细则 3**（身份留给程序：角色只从数据库判定） |

### M-S1-T03 版本不可变约束与激活指针

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 版本不可变约束：document_versions 无 UPDATE/DELETE 路径；上传新文件 → 新版本行 + active_version 指针切换 |
| 01 原文产出物 | services/version.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01（versions 表）、M-S1-T02（document service） |
| 实施要点 | ① `create_new_version`：同文档上传新文件 → version_no 递增新行，**旧行原样保留**；② `active_version` 指针切换逻辑（documents 表唯一可变字段，00 文件第四节核心不变量）；③ status 流转入口：staging（新建）→ active（激活）→ retired（被新版本替代），failed（D-1，S2 摄取失败置入）；④ 不定义任何修改版本内容/删除版本行的方法（代码级无路径） |
| 涉及文件路径 | `app/services/version.py` |
| 验收映射 | **S1-AC-2**（修改版本被拒）、**S1-AC-3**（version_no 递增 + 指针切换）、支撑 S1-AC-5 |
| 落实安全细则 | **细则 5**（版本不可变 + 激活指针，ADR0002 思想：新上传=新版本行，active_version 是唯一可变指针） |

### M-S1-T04 隔离与版本负例测试

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 隔离测试：跨 workspace 读/写返回 KN-404；版本不可变测试 |
| 01 原文产出物 | tests/test_isolation.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01、M-S1-T02、M-S1-T03 |
| 实施要点 | ① 跨 workspace 读：A 区文档以 B 身份查询 → 空列表；跨区直接按 ID 访问 → KN-404；② 跨 workspace 写被拒；③ 版本不可变负例：调用任何修改/删除版本路径 → 不存在或被拒；④ 二次上传版本递增 + 指针切换正例；⑤ 负例断言总数 ≥ 6（S1-AC-5）；⑥ 测试用 fixture 隔离数据（为 S5-T03 的全量规范预热） |
| 涉及文件路径 | `tests/test_isolation.py`、`tests/conftest.py` |
| 验收映射 | **S1-AC-1、S1-AC-2、S1-AC-3、S1-AC-5**（全部在本任务出证据）；里程碑 **M1** 判据 |
| 落实安全细则 | **细则 1**（隔离的测试证明）、**细则 5**（版本不可变的测试证明） |

---

## 四、S2：Celery 异步摄取管线

**阶段目标（01 原文）**：文档进得来：上传 → MinIO 存原件 → Celery 异步执行 解析（含 OCR）→ 指纹 → 版本 → 切块 → pgvector 入库 → 增量索引。前置：S1 完成。

### S2 验收标准（01 原文，编号 S2-AC-1~6）

- **S2-AC-1** ✅ 上传接口在 1 秒内返回（异步生效），随后 status 接口可见 staging→active 流转；
- **S2-AC-2** ✅ 扫描版 PDF 经 OCR 入库，检索层可查到 OCR 文本；
- **S2-AC-3** ✅ 同一文件重复上传 → 提示"内容未变"，**chunks 表无新增行**；
- **S2-AC-4** ✅ 修改后重传 → version_no +1，检索只命中新版本（旧行 status=retired）；
- **S2-AC-5** ✅ Worker 停止时上传 → status 停在 staging 且有明确 pending 提示（不静默失败）；
- **S2-AC-6** ✅ 三种格式各一个 pytest 冒烟用例（Celery 任务用 `.apply` 同步模式测）。

### M-S2-T01 MinIO 客户端封装

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | MinIO 客户端封装：bucket 初始化、对象上传下载（file_path 存 object key） |
| 01 原文产出物 | services/storage.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T02（MinIO 服务）、M-S0-T03（MINIO_* 配置）、M-S1-T01（file_path 字段语义） |
| 实施要点 | ① bucket 启动初始化（不存在则创建）；② put/get 封装，**file_path 只存 object key 不存本地路径**（P-S2 硬性约束）；③ object key 命名规则含 workspace_id/document_id/version 维度，避免跨区对象混放；④ 给出最小验证命令与预期输出（P-S2"新组件验证要求"，MinIO 为未学技术必须实证） |
| 涉及文件路径 | `app/services/storage.py` |
| 验收映射 | 支撑 S2-AC-1（上传链路第一步） |
| 落实安全细则 | **细则 1**（object key 按 workspace 隔离组织，访问经 service 层校验） |

### M-S2-T02 多格式解析器（含 OCR）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 解析器：PDF 文本层检查（pypdf）→ 无文本层页面 PyMuPDF 渲染 + RapidOCR；Word（python-docx）；Markdown 直读 |
| 01 原文产出物 | services/parser.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T01（骨架与依赖声明） |
| 实施要点 | ① pypdf 提取 PDF 文本层；② 无文本层页面触发 OCR：PyMuPDF 渲染页面为图片 → RapidOCR 识别（只对无文本层页面触发，P-S2 约束）；③ python-docx 解析 Word；Markdown 直读；④ 解析失败置 failed 并返回 KN-422 语义，不影响其他任务（P-S2 约束）；⑤ 依赖统一进 pyproject.toml 由 uv 管理 |
| 涉及文件路径 | `app/services/parser.py`、`pyproject.toml`（追加依赖） |
| 验收映射 | **S2-AC-2**（OCR 文本可入库）、支撑 S2-AC-6 |
| 落实安全细则 | **细则 6**（解析失败 KN-422 显式暴露，不静默） |

### M-S2-T03 Celery 基座与任务状态查询

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | Celery 基座：celery_app（Redis broker）+ 任务状态查询接口 |
| 01 原文产出物 | workers/celery_app.py + api/status.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S0-T02（Redis）、M-S0-T03（REDIS_URL）、M-S1-T01（版本状态字段） |
| 实施要点 | ① `celery_app` 以 Redis 为 broker 与 result backend（00 文件第二节职责）；② 摄取任务状态查询接口：按 document_id 返回 version 的 status（staging/active/retired/failed，D-1 四态）与失败原因（**Celery 任务失败经状态查询接口暴露，不静默吞掉**，细则 6）；③ Worker 未运行时任务停留 staging 的 pending 提示逻辑；④ 给出 Celery 最小验证命令与预期输出（P-S2 新组件验证要求） |
| 涉及文件路径 | `app/workers/celery_app.py`、`app/api/status.py` |
| 验收映射 | **S2-AC-1**（status 接口可见流转）、**S2-AC-5**（Worker 停止时 pending 提示不静默） |
| 落实安全细则 | **细则 6**（任务失败经状态接口暴露，不静默吞掉） |

### M-S2-T04 摄取任务（切块→指纹→向量化→入库）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 摄取任务：切块（300~500 字/重叠 50）→ content_hash 指纹 → embedding 写入 chunks（向量+tsv 同事务）→ 状态流转 staging→active→retired |
| 01 原文产出物 | workers/ingestion.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S2-T01（读原件）、M-S2-T02（解析）、M-S2-T03（Celery）、M-S1-T01（chunks 表）、M-S1-T03（状态流转） |
| 实施要点 | ① 解析文本 → 切块（300~500 字、重叠 50）；② **chunk 级 content_hash 与文档级全文 content_hash 分开存**（P-S2 约束：两者分开）；③ embedding 走 `.env` compatible-mode 配置（OPENAI_API_BASE/KEY），**key 不入日志**；④ chunks 写入（embedding + tsv 生成列）与 version 状态流转在**同一事务**，失败回滚并置 failed（不静默）；⑤ 完成后新版本 → active，旧版本 → retired（细则 5 流转）；⑥ 给出 pgvector 写入的最小验证命令与预期输出 |
| 涉及文件路径 | `app/workers/ingestion.py` |
| 验收映射 | **S2-AC-1**（staging→active 流转）、**S2-AC-2**（OCR 文本入库）、支撑 S2-AC-4 |
| 落实安全细则 | **细则 5**（状态流转 staging→active→retired，事务内写入）、**细则 9**（embedding 调用 key 不入日志）、**细则 6**（失败置 failed 不静默） |

### M-S2-T05 增量索引

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 增量索引：上传时对比 content_hash——未变跳过并提示；变更 → 新版本 + 旧版本 chunks 置 retired |
| 01 原文产出物 | services/version.py 扩展 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S2-T04（摄取管线）、M-S1-T03（版本机制） |
| 实施要点 | ① 上传时计算全文 content_hash 与现有版本对比；② 未变 → 跳过索引并返回"内容未变"提示，**chunks 表无新增行**；③ 变更 → 走 T04 摄取生成新版本；旧版本整体 retired（O-2：通过 version.status=retired 实现，检索层过滤，chunks 行不改）；④ 去重粒度：chunk 指纹用于行级去重，文档指纹用于增量判定 |
| 涉及文件路径 | `app/services/version.py`（扩展） |
| 验收映射 | **S2-AC-3**（重复上传无新增 chunks 行）、**S2-AC-4**（修改重传 version_no +1、检索只命中新版本） |
| 落实安全细则 | **细则 5**（旧版本不可变、retired 流转）、**细则 1**（增量比对在 workspace 范围内进行） |

### M-S2-T06 上传 API

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 上传 API：POST /documents（multipart）→ 存 MinIO → 建 staging 版本 → 派发 Celery 任务 → 立即返回 version_id |
| 01 原文产出物 | api/documents.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S2-T01、M-S2-T03、M-S2-T05、M-S1-T02/T03 |
| 实施要点 | ① multipart 上传端点（路径按 00 文件第十一节：/api/v1/workspaces/{workspace_id}/documents）；② 流程顺序：**原件先写 MinIO 再建 version 行**（staging）→ 派发 Celery → 立即返回 version_id（快速返回不阻塞，00 文件第二节 Celery 职责）；③ 响应结构 {code, message, data}；④ 本阶段暂无 JWT（O-7），workspace_id 由路径参数传入 |
| 涉及文件路径 | `app/api/documents.py`、`app/main.py`（注册路由） |
| 验收映射 | **S2-AC-1**（1 秒内返回 + 异步生效）、支撑 S2-AC-3/4/5 端到端 |
| 落实安全细则 | **细则 1**（workspace_id 路径隔离）、**细则 6**（KN-422/KN-429 等错误码统一输出） |

---

## 五、S3：混合检索 + RAG Graph + SSE + 评测基线

**阶段目标（01 原文）**：答案出得去：pgvector 向量路 + tsvector 全文路 双路召回 → RRF 融合 → Rerank 精排 → LangGraph RAG Graph（Checkpointer）→ SSE 流式回答 + 引用。前置：S2 完成（库内有 active 状态的 chunks）。

### S3 验收标准（01 原文，编号 S3-AC-1~5）

- **S3-AC-1** ✅ 混合检索 recall@5 **≥ 任一单路**（评测脚本输出三列对照表证明）；
- **S3-AC-2** ✅ rerank 不可用时（假 key）系统仍返回 RRF 结果，日志有降级记录；
- **S3-AC-3** ✅ 每条引用可回溯 filename + version_no + seq_no，且全部属于当前 workspace（**引用越权 = 验收失败**）；
- **S3-AC-4** ✅ `curl -N -X POST .../chat` 可观察流式输出；
- **S3-AC-5** ✅ 进程重启后同 thread_id 继续会话（Checkpointer 生效——新技术验证点）。

### M-S3-T01 稀疏检索路（tsvector 全文）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 稀疏路：tsvector 全文检索 top-k（同事务带 workspace + active 过滤） |
| 01 原文产出物 | services/retrieval_fts.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01（tsv 列与 GIN 索引）、M-S2-T06（库内有数据） |
| 实施要点 | ① PG 全文检索（tsquery 匹配 tsv 生成列）top-k；② **SQL 必须带 workspace_id 过滤与 JOIN document_versions.status='active' 条件**（P-S3 约束：两路条件完全一致）；③ 返回 chunk_id 与全文相关性排名 |
| 涉及文件路径 | `app/services/retrieval_fts.py` |
| 验收映射 | 支撑 **S3-AC-1**（单路基线之一）、**S3-AC-3**（过滤是引用越权防线的第一层） |
| 落实安全细则 | **细则 1**（向量/全文检索在 SQL 内过滤 workspace，跨区不可见） |

### M-S3-T02 稠密检索路（pgvector 向量）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 稠密路：query embedding → pgvector 余弦近邻 top-k（同样过滤） |
| 01 原文产出物 | services/retrieval_vec.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01（向量列与索引）、M-S0-T03（embedding 模型配置）、M-S2-T06 |
| 实施要点 | ① query → embedding（compatible-mode 配置，key 不入日志）；② pgvector 余弦近邻 top-k，**过滤条件与 T01 完全一致**（workspace_id + status='active'）；③ 给出 pgvector 检索算子（`<=>`）最小验证命令与预期输出（P-S3 新组件验证要求） |
| 涉及文件路径 | `app/services/retrieval_vec.py` |
| 验收映射 | 支撑 **S3-AC-1**（单路基线之二） |
| 落实安全细则 | **细则 1**（embedding 查询同带 workspace 条件）、**细则 9**（key 不入日志） |

### M-S3-T03 融合层（去重 → RRF → Rerank 降级）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 融合层：chunk_id 去重 → RRF（k=60）→ 百炼 rerank 精排（**失败自动降级 RRF 分数**，日志可见降级原因） |
| 01 原文产出物 | services/fusion.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S3-T01、M-S3-T02 |
| 实施要点 | ① 两路结果按 chunk_id 去重后 RRF 融合：score = Σ 1/(60 + rank)（P-S3 标准公式）；② 百炼 gte-rerank 精排（DashScope 原生接口）；③ **rerank 失败降级为 RRF 分数排序，不抛错不中断，降级事件写入日志**（P-S3 约束；00 文件第七节降级策略） |
| 涉及文件路径 | `app/services/fusion.py` |
| 验收映射 | **S3-AC-1**（混合 ≥ 单路）、**S3-AC-2**（假 key 降级 + 日志记录） |
| 落实安全细则 | **细则 9**（rerank key 不入日志）、**细则 6**（降级事件日志可见，不静默） |

### M-S3-T04 LangGraph RAG Graph（Checkpointer）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | LangGraph RAG Graph：State{query, workspace_id, thread_id, retrieved, answer, citations} → 节点：检索→重排→生成→引用组装；接 PostgreSQL Checkpointer（run_id/thread_id） |
| 01 原文产出物 | graphs/rag_graph.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S3-T03（融合层）、M-S0-T03（DATABASE_URL 复用） |
| 实施要点 | ① StateGraph 按任务表定义 State（含三级身份字段 workspace_id/thread_id，细则 2）；② 节点链：检索→重排→生成→引用组装；③ **Checkpointer 持久化到 PostgreSQL（连接串复用 DATABASE_URL）**——新技术验证点；④ **citations 只能从 retrieved chunks 组装（filename + version_no + seq_no），禁止把模型生成文本当引用**（P-S3 约束）；⑤ run_id 存于 Trace 与 Checkpointer 层面，不建业务 runs 表（O-6） |
| 涉及文件路径 | `app/graphs/rag_graph.py` |
| 验收映射 | **S3-AC-3**（引用溯源）、**S3-AC-5**（重启续会话）、支撑 S3-AC-4 |
| 落实安全细则 | **细则 2**（三级身份：user_id→workspace_id→thread_id 绑定进 Graph State）、**细则 10**（引用溯源：从检索结果组装 citations） |

### M-S3-T05 问答 API（SSE 流式）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 问答 API：POST /chat（SSE 流式），事件含 token 增量与最终 citations |
| 01 原文产出物 | api/chat.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S3-T04（Graph） |
| 实施要点 | ① POST + SSE 事件流（W17 课件模式，fetch 可消费）；② 事件类型：token / citation / done / error（P-S3 约定）；③ citations 事件在流末尾携带完整溯源（filename+version_no+seq_no）；④ 会话历史写入 messages 表（thread_id 隔离） |
| 涉及文件路径 | `app/api/chat.py`、`app/main.py`（注册路由） |
| 验收映射 | **S3-AC-3**（引用随流输出）、**S3-AC-4**（curl -N 流式可观察） |
| 落实安全细则 | **细则 10**（每个结论可回溯 chunk）、**细则 1**（thread/messages 按 workspace 隔离） |

### M-S3-T06 黄金测试集与评测脚本

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 黄金测试集（10~20 条 QA）+ 评测脚本：recall@5、引用正确率 |
| 01 原文产出物 | eval/golden_set.json + eval/run_eval.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S3-T05（端到端问答可跑）、M-S3-T01/T02（单路基线） |
| 实施要点 | ① 构造 10~20 条 QA 黄金集（基于测试语料，标注期望 chunk）；② 评测脚本输出**三列对照表：稀疏路 / 稠密路 / 混合的 recall@5**（S3-AC-1 量化证据，必须贴真实数字进 STATUS）；③ 引用正确率评测：回答引用是否指向黄金集期望 chunk 且属当前 workspace |
| 涉及文件路径 | `eval/golden_set.json`、`eval/run_eval.py` |
| 验收映射 | **S3-AC-1**（三列对照表）、**S3-AC-3**（引用正确率）；里程碑 **M2** 判据 |
| 落实安全细则 | **细则 10**（引用正确率是溯源的质量证明）、**细则 1**（引用越权检查进入评测） |

---

## 六、S4：Harness 七组件与 Agent

**阶段目标（01 原文）**：把"能用的 RAG"升级为"受控的 Agent"：七组件 Harness 全套落地（轻量=单模块实现，结构不删）+ interrupt 审批 + JSON Trace。前置：S3 完成。

### S4 验收标准（01 原文，编号 S4-AC-1~5）

- **S4-AC-1** ✅ 负例 1：用户 A 访问 workspace B 文档 → 全链路不出现 B 的内容（**以 Trace 为证据**）；
- **S4-AC-2** ✅ 负例 2：构造超预算 run → 中断并返回 KN-429，Trace 记录中断点；
- **S4-AC-3** ✅ 负例 3：不带 confirm 的删除 → 挂起（KN-410）；confirm=true → 执行且审计有记录；
- **S4-AC-4** ✅ 七组件均有独立模块与最小单测（结构完整性检查）；
- **S4-AC-5** ✅ 每条 Trace 为合法 JSON，含 run_id、工具调用次数、token 消耗，不含 API key 与文档正文。

### M-S4-T01 ModelGateway + ContextManager

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | ModelGateway + ContextManager：统一模型调用入口（重试/超时/用量统计）与上下文装配（身份/历史/证据） |
| 01 原文产出物 | core/gateway.py + core/context.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S3-T06（S3 链路完成，模型调用点收敛入口） |
| 实施要点 | ① `core/gateway.py`：统一 chat/embedding 调用入口，重试/超时/用量统计/降级（00 文件第八节职责）；② `core/context.py`：身份、历史、检索证据的组装与裁剪，**身份只来自程序侧**（JWT/数据库），不从对话文本或 metadata 推断；③ 各自独立成模块，接口签名写类型注解（P-S4 约束） |
| 涉及文件路径 | `app/core/gateway.py`、`app/core/context.py` |
| 验收映射 | 支撑 S4-AC-1（身份装配是越权负例的基础）、S4-AC-4 |
| 落实安全细则 | **细则 3**（身份留给程序：绝不从对话文本/metadata 推断权限）、**细则 2**（三级身份在上下文装配中绑定）、**细则 8**（用量统计为预算提供数据） |

### M-S4-T02 ToolRegistry + PolicyEngine

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | ToolRegistry + PolicyEngine：混合检索注册为 Tool（schema/只读标记/失败策略）；策略判定（只读可并行、写入需审批） |
| 01 原文产出物 | core/tool_registry.py + core/policy.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S4-T01（组件接口约定）、M-S3-T03（检索服务可注册） |
| 实施要点 | ① 混合检索注册为 Tool：声明输入/输出 schema、权限要求、失败策略（**细则 11 工具合同**）；② 写入类工具单独标记（only-read / write 标志）；③ PolicyEngine：只读工具可并行，写入类需审批（ADR0003 思想） |
| 涉及文件路径 | `app/core/tool_registry.py`、`app/core/policy.py` |
| 验收映射 | 支撑 S4-AC-4（结构完整性）、S4-AC-3（写入需审批的判定入口） |
| 落实安全细则 | **细则 11**（工具合同：schema/权限/失败策略/写入标记）、**细则 7**（策略判定联动审批） |

### M-S4-T03 Agent Graph（Router 模式）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | Agent Graph：Router 判断是否检索 → 调用工具 → 生成（W15 Router 模式，单 Agent + 工具） |
| 01 原文产出物 | graphs/agent_graph.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S4-T01（gateway/context）、M-S4-T02（工具与策略） |
| 实施要点 | ① Router 节点判断是否需要检索（W15 模式）→ Tool 调用节点（经 ToolRegistry/PolicyEngine）→ 生成节点；② 接 Checkpointer（复用 S3-T04 的 PG Checkpointer 配置）；③ Graph 节点内部逻辑保持可被 Trace 中间件外层包装（为 T06 预留） |
| 涉及文件路径 | `app/graphs/agent_graph.py` |
| 验收映射 | 支撑 S4-AC-1/2/3（三类负例都跑在 Agent Graph 上）、S4-AC-4 |
| 落实安全细则 | **细则 2**（Agent 运行时三级身份绑定校验）、**细则 1**（工具检索继承 workspace 过滤） |

### M-S4-T04 BudgetManager

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | BudgetManager：每 run 限 token 与工具调用次数，超限中断返回 KN-429 |
| 01 原文产出物 | core/budget.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S4-T03（Agent run 中接入检查点）、M-S4-T01（用量统计） |
| 实施要点 | ① 每 run 的 token 与工具调用次数账本；② **每次模型/工具调用前检查，超限抛出携带 KN-429 的业务异常并终止 run**（P-S4 约束）；③ 限值走配置（.env/默认值） |
| 涉及文件路径 | `app/core/budget.py`、`app/core/config.py`（限值配置） |
| 验收映射 | **S4-AC-2**（超预算中断 + KN-429 + Trace 中断点） |
| 落实安全细则 | **细则 8**（预算控制：超限中断返回 KN-429） |

### M-S4-T05 ApprovalManager 与删除端点审批

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | ApprovalManager（🆕）：删除类操作 → LangGraph interrupt 挂起 → confirm=true 恢复执行；审批事件入 messages 审计 |
| 01 原文产出物 | core/approval.py（+ 删除类 REST 端点审批包装，D-2 决策） |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S4-T03（Agent Graph interrupt 挂点）、M-S1-T02（service 层删除逻辑） |
| 实施要点 | ① **审批用 LangGraph 原生 interrupt + Checkpointer 恢复，不自造审批轮询轮子**（P-S4 硬性约束）；② Agent 内删除类工具：interrupt 挂起 → confirm=true 恢复执行；③ **REST 删除端点**（D-2 决策）：DELETE /api/v1/workspaces/{workspace_id} 与 DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}——首次调用返回 **KN-410 + 待审批状态**，confirm=true 重调后才执行；④ **审批记录进 messages/审计日志**（role 用审批类标记，content 记录操作与结果）；⑤ 审批人身份由程序侧判定（细则 3） |
| 涉及文件路径 | `app/core/approval.py`、`app/api/workspaces.py`（DELETE 路由）、`app/api/documents.py`（DELETE 路由） |
| 验收映射 | **S4-AC-3**（负例 3：未 confirm 挂起 KN-410；confirm=true 执行且审计有记录） |
| 落实安全细则 | **细则 7**（敏感操作审批：KN-410 + confirm/interrupt + 审计记录，ADR0003 思想）、**细则 3**（审批人身份程序判定） |

### M-S4-T06 Observability（JSON Trace）

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | Observability：每次 run 输出 JSON Trace（工具调用链/耗时/token），中间件式接入 |
| 01 原文产出物 | core/trace.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S4-T03（Agent run 可被包装）、M-S4-T01（用量统计） |
| 实施要点 | ① **中间件式接入：不改 S3 的 Graph 节点内部逻辑，只在外层包装**（P-S4 约束）；② 每次问答输出 JSON Trace：模型调用/工具调用/耗时/token 消耗、run_id；③ **Trace 不含 API key 与文档正文（只含摘要与统计值）**（P-S4 约束）；④ 每条 Trace 为合法 JSON（S4-AC-5） |
| 涉及文件路径 | `app/core/trace.py` |
| 验收映射 | **S4-AC-1**（Trace 作为越权负例证据）、**S4-AC-2**（中断点记录）、**S4-AC-5**（Trace 合法性与脱敏）；里程碑 **M3** 判据 |
| 落实安全细则 | **细则 12**（观测 Trace）、**细则 9**（Trace 不含凭据）、**细则 10**（Trace 辅助引用排查） |

---

## 七、S5：认证与自动化测试

**阶段目标（01 原文）**：补齐 JWT 登录权限，用 pytest 建立全量回归防线。前置：S4 完成（权限测试需要 Harness 在位）。

### S5 验收标准（01 原文，编号 S5-AC-1~4）

- **S5-AC-1** ✅ 无 token → KN-401；无效 token → KN-401；有 token 无权限 → KN-404（不泄露存在性）；
- **S5-AC-2** ✅ `uv run pytest` 全绿，真实输出贴 STATUS；
- **S5-AC-3** ✅ 覆盖率 ≥ 70%（核心 services 模块）；
- **S5-AC-4** ✅ Celery 相关测试用同步模式（`.apply`）跑通，不依赖 Worker 常驻。

### M-S5-T01 JWT 登录

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | JWT 登录：/auth/login 签发；依赖注入当前用户；密码 bcrypt |
| 01 原文产出物 | api/auth.py + core/security.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S1-T01（users 表）、M-S0-T03（JWT 密钥配置占位已在 .env.example） |
| 实施要点 | ① POST /api/v1/auth/login 签发 JWT（P-S5 约束：**JWT 密钥走 .env；密码只存 bcrypt hash**）；② FastAPI 依赖注入当前用户（user_id），失败 KN-401；③ 无 token/无效 token → KN-401 |
| 涉及文件路径 | `app/api/auth.py`、`app/core/security.py` |
| 验收映射 | **S5-AC-1**（KN-401 部分） |
| 落实安全细则 | **细则 3**（用户角色由 JWT/数据库判定）、**细则 9**（JWT 密钥入 .env 不入代码） |

### M-S5-T02 权限过滤回归

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 权限过滤回归：workspace_members 授权检查接入全部业务端点 |
| 01 原文产出物 | 中间件/依赖 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S5-T01（当前用户注入）、M-S4-T06（全部端点在位） |
| 实施要点 | ① 统一依赖/中间件：校验当前用户在 workspace_members 中的授权（user_id+workspace_id+role），未授权 → **KN-404（不泄露存在性）**；② 接入全部业务端点（workspaces/documents/status/chat/threads/eval/delete）；③ 有 token 无权限 ≠ KN-403（细则 1：跨区返回 KN-404） |
| 涉及文件路径 | `app/core/permissions.py`（或 `app/api/deps.py`）、各端点接入 |
| 验收映射 | **S5-AC-1**（有 token 无权限 → KN-404）、支撑 S4-AC-1 端到端复验 |
| 落实安全细则 | **细则 1**（所有查询强制过滤、KN-404）、**细则 2**（user_id→workspace_id 绑定校验） |

### M-S5-T03 pytest 全量回归

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | pytest 全量：模型/隔离/摄取/检索/审批/认证 六组用例 + 覆盖率报告 |
| 01 原文产出物 | tests/ 完整套件 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S5-T01、M-S5-T02 及全部前序任务（S1-T04 隔离、S2 冒烟、S4 负例等汇总） |
| 实施要点 | ① 六组用例：模型/隔离/摄取/检索/审批/认证；② **测试用 fixture 隔离：每个测试用独立数据库 schema 或事务回滚，禁止共用脏数据**（P-S5 约束）；③ **Celery 测试用 .apply() 同步执行**（P-S5 约束）；④ **不得为了让测试通过而修改任何隔离/审批/预算规则本身**；失败用例如实保留（P-S5 灵魂条款）；⑤ 覆盖率报告（核心 services ≥ 70%） |
| 涉及文件路径 | `tests/`（conftest.py + 六组用例文件）、`pyproject.toml`（pytest/覆盖率配置） |
| 验收映射 | **S5-AC-2、S5-AC-3、S5-AC-4**；里程碑 **M4** 判据 |
| 落实安全细则 | 全部细则的回归证明（1/2/3/5/7/8 的用例在此汇总固化） |

---

## 八、S6：部署与收尾（可选）

**阶段目标（01 原文）**：应用容器化、全栈 Compose 一键起、冻结前端契约、项目收官。前置：S5 完成。

### S6 验收标准（01 原文，编号 S6-AC-1~4）

- **S6-AC-1** ✅ `docker compose up` 后从上传到问答的端到端链路可用（api + worker + 三基础服务共 5 容器 healthy）；
- **S6-AC-2** ✅ 容器内评测 recall@5 与本地一致（偏差 < 5%）；
- **S6-AC-3** ✅ 前端契约文档与实际 API 一致（逐端点核对）；
- **S6-AC-4** ✅ 镜像内无 .env / 密钥（运行时挂载），容器非 root 运行。

### M-S6-T01 应用容器化

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 应用 Dockerfile + 扩展 compose：加入 api 与 worker 两个服务（复用 S0 的三基础服务） |
| 01 原文产出物 | 部署文件 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S5-T03（测试基线稳定后容器化） |
| 实施要点 | ① 单一 Dockerfile，api 与 worker 共用镜像不同 command（P-S6 约束）；② **镜像内不打包 .env 与任何密钥，运行时以环境变量/挂载注入**；③ **容器以非 root 用户运行**；④ compose 扩展为 5 服务（api/worker + PG/Redis/MinIO） |
| 涉及文件路径 | `Dockerfile`、`compose.yaml`（扩展）、`.dockerignore` |
| 验收映射 | **S6-AC-1**（5 容器 healthy）、**S6-AC-4**（无密钥、非 root） |
| 落实安全细则 | **细则 9**（凭据不入镜像/日志，运行时注入） |

### M-S6-T02 基础可观测性

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 可观测性：/metrics 基础指标（请求数/延迟/token 消耗/摄取队列深度）+ 请求日志中间件 |
| 01 原文产出物 | core/metrics.py |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S6-T01（api 容器在位）、M-S4-T06（Trace 数据源） |
| 实施要点 | ① /metrics 暴露聚合值：请求数/延迟/token 消耗/摄取队列深度；② **指标只暴露聚合值，不暴露文档内容与用户输入**（P-S6 约束）；③ 请求日志中间件接入既有脱敏 logger（S0-T03） |
| 涉及文件路径 | `app/core/metrics.py`、`app/main.py`（接入） |
| 验收映射 | 支撑 S6-AC-1（端到端可观测） |
| 落实安全细则 | **细则 12**（观测扩展到指标层）、**细则 9**（日志/指标脱敏） |

### M-S6-T03 终验与契约冻结

| 项 | 内容 |
|---|---|
| 01 原文任务内容 | 终验：容器内跑黄金测试集 + 全量 pytest + 前端契约文档冻结（对照需求文档第十一节逐端点核对） |
| 01 原文产出物 | 验收报告 |
| 状态 | **NOT_STARTED** |
| 依赖任务 | M-S6-T01、M-S6-T02、M-S3-T06（评测脚本）、M-S4-T05（删除端点，契约含 DELETE） |
| 实施要点 | ① **终验数字（recall@5、pytest 结果）必须在容器内真实执行后贴原始输出，不得引用本地历史结果**（P-S6 约束）；② 对照 00 文件第十一节 9 个端点逐一核对实际 API（含 D-2 决策的 DELETE 双阶段）；③ 契约差异记录进验收报告，冻结为前端开发契约；④ 报告含阶段总结（做了什么/简化了什么/遗留什么，01 文件里程碑要求） |
| 涉及文件路径 | `MiniKnora_验收报告.md`（新建，仓库根）、`STATUS.md`（最终更新） |
| 验收映射 | **S6-AC-1、S6-AC-2、S6-AC-3**；里程碑 **M5** 判据 |
| 落实安全细则 | **细则 6**（错误码契约核对）、**细则 10**（引用溯源端到端复验） |

---

## 九、安全细则（00 文件第六节 12 条）→ 任务映射总表

| 细则 | 内容摘要 | 落实任务 |
|---|---|---|
| 1 | workspace_id 隔离：全表带 workspace_id、查询强制过滤、检索 SQL 内过滤、跨区返回 KN-404 | S1-T01、S1-T02、S1-T04、S2-T01、S2-T05、S3-T01、S3-T02、S5-T02 |
| 2 | 三级身份隔离：user_id→workspace_id→thread_id，Agent 运行时全部绑定校验 | S3-T04、S4-T01、S4-T03、S5-T02 |
| 3 | 身份留给程序：角色由 JWT/数据库判定，不从文本/metadata 推断 | S1-T02、S4-T01、S4-T05、S5-T01 |
| 4 | 统一 ID 体系：全部 UUID，命名严格照抄 | S1-T01（全表字段命名） |
| 5 | 版本不可变 + 激活指针：staging→active→retired 流转 | S1-T01、S1-T03、S1-T04、S2-T04、S2-T05 |
| 6 | 统一错误码：全局异常处理器；Celery 失败经状态接口暴露不静默 | S0-T04、S2-T02（KN-422）、S2-T03、S2-T04、S3-T03（降级日志）、S6-T03 |
| 7 | 敏感操作审批：KN-410 + confirm / interrupt 恢复 + 审计记录 | S4-T02（策略判定）、S4-T05（核心实现） |
| 8 | 预算控制：每 run 限 token/调用次数，超限 KN-429 | S4-T01（用量统计）、S4-T04 |
| 9 | 凭据不入日志：API key 只存 .env；日志统一脱敏 | S0-T03、S2-T04、S3-T02、S3-T03、S4-T06、S5-T01、S6-T01、S6-T02 |
| 10 | 引用溯源：每个结论可回溯 chunk（filename+version_no+seq_no） | S3-T04、S3-T05、S3-T06、S6-T03 |
| 11 | 工具合同：schema/权限/失败策略/写入类单独标记 | S4-T02 |
| 12 | 观测 Trace：每次问答输出 JSON Trace | S4-T06、S6-T02 |

> 每条细则至少有一个实施任务与一个测试/验收证明点（细则 1/5/7/8 的负例证据在 S1-T04、S4-AC-1/2/3；细则 9/12 的证据在 S4-AC-5 与 S6-AC-4）。

## 十、里程碑（01 文件第九节原文）

| 检查点 | 判据 | 完成时点 |
|---|---|---|
| 🎯 M1（S1 后） | 隔离与版本不变量测试全绿 | S1-T04 PASS |
| 🎯 M2（S3 后） | 混合检索 ≥ 单路 + 引用可溯源 + 断线重启可续 | S3-T06 PASS |
| 🎯 M3（S4 后） | 三类负例（越权/超预算/未审批）全拦截 + 七组件结构完整 | S4-T06 PASS |
| 🎯 M4（S5 后） | 全量 pytest 绿 + 认证链路完整 | S5-T03 PASS |
| 🎯 M5（S6 后） | 5 容器端到端 + 契约冻结 | S6-T03 PASS |

## 十一、关键路径与执行顺序

- **总任务数**：7 个阶段、32 个任务（S0:4 / S1:4 / S2:6 / S3:6 / S4:6 / S5:3 / S6:3）。
- **关键路径**（单人按序执行即全链）：S0-T01 → S0-T04 → S1-T01 → S1-T03 → S2-T03 → S2-T04 → S2-T06 → S3-T02 → S3-T03 → S3-T04 → S3-T05 → S4-T03 → S4-T05 → S5-T01 → S5-T02 → S5-T03 → S6-T01 → S6-T03。
- **新技术密集点**（需按提示词卡片"新组件验证要求"实证，防止"看起来写了但没跑通"）：S0（pgvector 镜像/健康检查）、S2（MinIO/Celery/OCR）、S3（pgvector 算子/Checkpointer/SSE）、S4（interrupt 审批）。
- **里程碑停点**：M1/M2/M3/M4 各写 3~5 行阶段总结进 STATUS（做了什么/简化了什么/遗留什么）。

## 十二、状态汇总表（每完成一任务更新此表与对应任务块）

| 任务 | 状态 | 日期 | 备注（真实测试结果/阻塞原因） |
|---|---|---|---|
| M-S0-T01 | NOT_STARTED | | |
| M-S0-T02 | NOT_STARTED | | |
| M-S0-T03 | NOT_STARTED | | |
| M-S0-T04 | NOT_STARTED | | |
| M-S1-T01 | NOT_STARTED | | |
| M-S1-T02 | NOT_STARTED | | |
| M-S1-T03 | NOT_STARTED | | |
| M-S1-T04 | NOT_STARTED | | |
| M-S2-T01 | NOT_STARTED | | |
| M-S2-T02 | NOT_STARTED | | |
| M-S2-T03 | NOT_STARTED | | |
| M-S2-T04 | NOT_STARTED | | |
| M-S2-T05 | NOT_STARTED | | |
| M-S2-T06 | NOT_STARTED | | |
| M-S3-T01 | NOT_STARTED | | |
| M-S3-T02 | NOT_STARTED | | |
| M-S3-T03 | NOT_STARTED | | |
| M-S3-T04 | NOT_STARTED | | |
| M-S3-T05 | NOT_STARTED | | |
| M-S3-T06 | NOT_STARTED | | |
| M-S4-T01 | NOT_STARTED | | |
| M-S4-T02 | NOT_STARTED | | |
| M-S4-T03 | NOT_STARTED | | |
| M-S4-T04 | NOT_STARTED | | |
| M-S4-T05 | NOT_STARTED | | |
| M-S4-T06 | NOT_STARTED | | |
| M-S5-T01 | NOT_STARTED | | |
| M-S5-T02 | NOT_STARTED | | |
| M-S5-T03 | NOT_STARTED | | |
| M-S6-T01 | NOT_STARTED | | |
| M-S6-T02 | NOT_STARTED | | |
| M-S6-T03 | NOT_STARTED | | |
