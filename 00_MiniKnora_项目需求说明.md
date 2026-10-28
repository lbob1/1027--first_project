# MiniKnora 项目需求说明

> 版本：v2.0 ｜ 日期：2026-10-28
> 定位：PyKnora（腾讯 WeKnora 重构项目）的**教学轻量替代版**。轻量化体现在**单机单实例部署与模块精简**，**基础设施选型完整复用原项目**（PostgreSQL + pgvector / Redis / Celery / MinIO），功能与工程思想不变。
> 上游文档：`E:\1027--first_project\pyknora\docs\`（PRD / tdd / adr），本文件继承其安全与 ID 契约。

---

## 一、项目背景与定位

原 PyKnora 项目规划了 32 个 Phase 0 验证任务，因 token 消耗过高不再由学生执行。**MiniKnora 在保持原项目核心功能、基础设施选型与工程纪律不变的前提下，将执行规模压缩为单人可完成的 7 个阶段**，目标是：

1. 完整走一遍"需求 → 设计 → 实施 → 测试 → 验收"的项目流程；
2. 把 Week13–Week19 所学知识在一个项目里**全部串联实操**；
3. 择优吸收原项目中的**新技术点**（pgvector、Celery 异步、MinIO、LangGraph Checkpointer / interrupt 审批 / 版本不可变）。

### 与原项目的对照（功能与组件不变，规模减重）

| 原项目 | MiniKnora | 说明 |
|---|---|---|
| PostgreSQL + pgvector + Redis + Celery + MinIO | **完整保留四件套**（单机单实例部署） | 轻量化=不做集群/高可用/多实例，**不换组件** |
| DocReader gRPC 容器解析 | **pypdf/python-docx + PyMuPDF + RapidOCR** 本地解析 | 覆盖 PDF（含扫描件）/Word/Markdown |
| 4 张 LangGraph Graph + Harness 全家桶 | **1 张 RAG Graph + 完整轻量 Harness**（7 个组件全保留，W14 课件实现法） | Graph 聚焦 RAG 主链路；Harness 组件结构不删减 |
| 约 40 张表、40 个错误码 | **7 张核心表、约 12 个错误码** | 字段命名严格继承 tdd/01 的 ID 规范 |
| Outbox + 原子发布 + checkpoint 恢复 | **简化版本号 + 事务内写入 + LangGraph Checkpointer** | 保留"版本不可变"与"可恢复"思想 |
| 32 任务 / 12 波次 | **7 个阶段 / 约 26 个小任务** | 单人 1~2 周可完成 |

---

## 二、基础设施组件职责（⭐ 完整复用原项目选型）

| 组件 | 具体职责 | 在 MiniKnora 中的落法 |
|---|---|---|
| **PostgreSQL + pgvector** | ① 业务事实数据（7 张表）；② **向量存储**（chunks.embedding 列，ivfflat/hnsw 索引）；③ **稀疏检索路**（tsvector + GIN 索引，承担 BM25 对应的全文检索） | 单实例；向量与业务数据同库，事务内一致 |
| **Redis** | ① Celery 的 **broker 与结果后端**；② 轻量缓存（会话/检索中间结果） | 单实例 |
| **Celery** | **异步任务队列**：文档摄取流水线（解析→切块→向量化→入库）在 Worker 中执行，上传 API 快速返回、不阻塞 | 单 Worker 进程（本地开发） |
| **MinIO** | **对象存储**：原始上传文件的持久保存（document_versions.file_path 指向 MinIO object key） | 单节点 + Docker 卷持久化 |
| **LangGraph + Checkpointer** | 工作流状态持久化（run/thread 的每步状态），进程重启可恢复 | Checkpointer 落 PostgreSQL |

> 💡 部署形态：本地开发用一份 `docker-compose.yml` 一键起 PG + Redis + MinIO 三个基础服务（复用 W19 Day03 所学），应用与 Celery Worker 在 PyCharm 中直接运行排错——**基础组件容器化、业务代码本地跑**，兼顾复用与调试便利。

---

## 三、核心功能需求（继承原 PRD，编号 MF-xx）

| 编号 | 功能 | 优先级 | 说明 |
|---|---|---|---|
| MF-01 | 多工作区知识库 | P0 | 创建/列出/删除工作区，**所有数据按 workspace_id 严格隔离** |
| MF-02 | 文档上传与解析 | P0 | 支持 PDF（含扫描页 OCR）/ Word / Markdown；上传即存 MinIO，解析由 Celery 异步执行 |
| MF-03 | 版本化摄取 | P0 | 同一文档多次上传 → 版本号递增；**旧版本不可变**；active_version 指针切换 |
| MF-04 | 切块与向量化入库 | P0 | 切块 → 内容指纹去重 → embedding 写入 chunks 表（**pgvector 列**），状态流转 staging→active |
| MF-05 | 增量索引 | P0 | 通过 content_hash 检测变更：未变不重复索引；变更生成新版本并增量更新 |
| MF-06 | 混合检索 | P0 | **pgvector 向量路 + tsvector 全文检索路** 双路召回 → chunk_id 去重 → RRF 融合 → Reranker 精排 |
| MF-07 | RAG 问答（SSE） | P0 | LangGraph RAG Graph 流式生成，**回答必须带引用溯源**（文件名+版本+片段定位） |
| MF-08 | 检索工具 Agent | P0 | 以 Tool 形式注册混合检索，由 Agent 决定是否/如何检索 |
| MF-09 | Harness 工程控制 | P0 | 七组件完整实现：身份合同、工具合同、预算、审批、Trace（详见第六节） |
| MF-10 | 敏感操作审批 | P1 | 删除工作区/文档需 confirm=true 二次确认，走 LangGraph interrupt |
| MF-11 | 用户认证与权限 | P0 | JWT 登录；用户只能访问被授权的 workspace |
| MF-12 | RAG 评测基线 | P1 | 黄金测试集 + 召回率/引用正确性自动评测 |
| MF-13 | 容器化部署 | P2（可选） | Docker Compose 一键起全服务 + 基础可观测性 |

---

## 四、数据模型（7 张核心表，字段命名继承 tdd/01 规范）

| 表 | 关键字段 | 说明 |
|---|---|---|
| users | user_id (UUID PK), username, password_hash, created_at | 认证主体 |
| workspaces | workspace_id (UUID PK), name, owner_user_id, created_at | 隔离边界 |
| workspace_members | workspace_id, user_id, role | 用户-工作区授权（多对多） |
| documents | document_id (UUID PK), workspace_id, filename, active_version, created_at | 文档元信息，**每查询必带 workspace_id 过滤** |
| document_versions | version_id (UUID PK), document_id, version_no, content_hash, file_path（**MinIO object key**）, status, created_at | **不可变**：只增不改；status ∈ {staging, active, retired} |
| chunks | chunk_id (UUID PK), version_id, seq_no, content, content_hash, **embedding vector(N)**（pgvector）, **tsv tsvector**（生成列）, created_at | 切块记录；向量与全文索引同表 |
| messages | message_id (UUID PK), workspace_id, thread_id, role, content, citations (JSON), created_at | 问答记录；thread_id 继承 W14 会话隔离 |

> ⭐ 核心不变量：**document_versions 一经写入不允许 UPDATE/DELETE**（新上传 = 新版本行）；documents.active_version 是唯一可变的"激活指针"。

---

## 五、统一错误码（继承 tdd/07 思想，约 12 个）

| 错误码 | HTTP | 含义 |
|---|---|---|
| KN-400 | 400 | 请求参数校验失败 |
| KN-401 | 401 | 未认证 / token 失效 |
| KN-403 | 403 | 无该 workspace 权限 |
| KN-404 | 404 | 资源不存在（**不泄露是否存在于其他 workspace**） |
| KN-409 | 409 | 状态冲突（如版本非 active） |
| KN-410 | 410 | 需要二次确认（审批未通过即执行敏感操作） |
| KN-422 | 422 | 文档格式不支持 / 解析失败 |
| KN-429 | 429 | 超出预算限制（token / 调用次数） |
| KN-500 | 500 | 服务内部错误 |
| KN-502 | 502 | 上游模型服务（百炼）调用失败 |
| KN-503 | 503 | 数据库 / Redis / MinIO 不可用 |
| KN-ORG-001 | 400 | 上游返回内容无法解析为合法结构 |

---

## 六、安全与工程细则（⭐ 必须逐条落实，验收将逐项检查）

| # | 细则 | 原项目出处 | MiniKnora 落法 |
|---|---|---|---|
| 1 | workspace_id 隔离 | ADR0005 / tdd/07 | 所有业务表带 workspace_id；**所有查询强制过滤**；Chroma 无关，向量检索在 SQL 内过滤（embedding 查询同带 workspace 条件）；跨区访问返回 KN-404 而非 KN-403 |
| 2 | 三级身份隔离 | W14 Day01 / tdd/01 | user_id（用户）→ workspace_id（租户）→ thread_id（会话）；Agent 运行时三者全部绑定校验 |
| 3 | 身份留给程序，证据交给模型 | W14 Day01 | 用户角色由 JWT/数据库判定，**绝不从对话文本或文档 metadata 推断权限**；metadata 只是数据不是规则 |
| 4 | 统一 ID 体系 | tdd/01 | 全部 UUID；命名严格照抄：workspace_id / document_id / version_id / chunk_id / message_id / thread_id / run_id |
| 5 | 版本不可变 + 激活指针 | ADR0002 | 见第四节核心不变量；摄取任务（Celery）完成前后状态流转：staging → active（新）→ retired（旧） |
| 6 | 统一错误码 | tdd/07 | 第五节，全局异常处理器统一输出；Celery 任务失败经状态查询接口暴露，不静默吞掉 |
| 7 | 敏感操作审批 | ADR0003 | 删除类操作：首次调用返回 KN-410 + 待审批状态；confirm=true 或经 LangGraph interrupt 恢复后才执行；**审批记录进 messages/审计日志** |
| 8 | 预算控制 | W14 Day02 / 老师 Harness 设计 | 每次 run 限制最大 token 与工具调用次数，超限中断并返回 KN-429 |
| 9 | 凭据不入日志 | ADR0005 | API key 只存 `.env`（用户自管，仓库只提交 `.env.example`）；日志打印前统一脱敏过滤 |
| 10 | 引用溯源 | PRD | 回答的每个结论可回溯到 chunk（文件名 + version_no + seq_no） |
| 11 | 工具合同 | W14 Day02 | 每个 Tool 声明输入/输出 schema、权限要求、失败策略；写入类工具单独标记 |
| 12 | 观测 Trace | W14 Day03 | 每次问答输出 JSON Trace（模型调用/工具调用/耗时/token 消耗），供回归排查 |

---

## 七、技术选型与简介

| 技术 | 一句话简介 | 用在 |
|---|---|---|
| Python 3.12 + uv | uv 是 Rust 写的 Python 包管理器，用 `pyproject.toml` + `uv.lock` 实现"声明-锁定-同步"可复现环境（W19 Day01） | S0 |
| FastAPI | 基于 Pydantic 类型注解自动生成路由校验与 Swagger 文档的 Web 框架（W17 Day01） | 全部 API |
| **PostgreSQL + pgvector** | 企业级关系数据库 + 向量扩展：embedding 以 vector 列存储，用 ivfflat/hnsw 索引做余弦近邻检索（**向量存储 + 全文检索同库**） | S1–S3 |
| **tsvector / GIN 全文检索** | PG 原生中文分词全文索引，承担混合检索的稀疏路（对应原项目 FTS 设计） | S3 |
| SQLAlchemy ORM | 用 Python 类映射数据表，Session 管理事务与连接池（W18 Day04，课件用 MySQL，本项目连接串切 PG，写法不变） | S1 |
| **Redis** | 内存键值库：作 Celery 的 broker/result backend，兼做轻量缓存 | S2 |
| **Celery** | Python 分布式任务队列：把耗时摄取流水线放入 Worker 异步执行，API 立即返回 | S2 |
| **MinIO** | S3 兼容对象存储：持久保存上传原件，file_path 存 object key | S2 |
| pypdf / python-docx | PDF 文本层提取 / Word 文档解析 | S2 |
| PyMuPDF | 将 PDF 页面渲染为图片，供 OCR 使用（W13 Day01） | S2 |
| RapidOCR | 轻量中文 OCR，识别扫描页文字，返回文本行+置信度（W13 Day01） | S2 |
| RRF 融合 | Reciprocal Rank Fusion：按两路排名的倒数合并分数，无需调权（W13 Day03） | S3 |
| Reranker（百炼 gte-rerank） | 对初筛候选做交叉注意精排，显著提升 top-k 相关性；**降级策略：不可用时直接用 RRF 分数** | S3 |
| LangChain | Model/Message/Prompt 抽象 + LCEL 链式调用 | S3/S4 |
| LangGraph | 状态机式工作流编排：State Graph + 节点 + 边；**Checkpointer** 持久化每步状态、**interrupt** 人工中断审批 | S3/S4 |
| SSE | Server-Sent Events，HTTP 单向流式推送，Agent 聊天用 POST SSE + fetch 消费（W17 Day02） | S3 |
| JWT | 无状态登录令牌：签发-校验-携带权限声明（W18 Day06） | S5 |
| pytest | 参数化/fixture 驱动的自动化测试（W18 Day07） | S5 |
| Docker Compose | 多容器编排，本地一键起 PG/Redis/MinIO，收尾阶段容器化应用（W19 Day02/03） | S0/S6 |
| 阿里云百炼 compatible-mode | OpenAI 兼容网关调用 chat / embedding 模型；**API key 由用户自管 `.env`，项目只提供 `.env.example`** | S2–S5 |

> ⚠️ 模型配置约定（继承主项目习惯）：`OPENAI_API_BASE` + `OPENAI_API_KEY` 走 compatible-mode；对话/向量模型型号在 `.env` 中填写；rerank 走 DashScope 原生接口，失败自动降级 RRF。

---

## 八、Harness 组件结构（⭐ 七组件完整保留，轻量=单模块实现）

原项目 Harness 含全套企业组件，MiniKnora **一个不删**，按 W14 课件实现法各落为一个轻量模块（Protocol 接口 + 默认实现）：

| 组件 | 职责 | 对应所学 |
|---|---|---|
| ModelGateway | 统一模型调用入口：重试/超时/用量统计/降级 | W14 Day02 |
| ContextManager | 上下文装配：身份、历史、检索证据的组装与裁剪 | W14 Day01 |
| ToolRegistry | 工具注册与合同校验（schema/权限/失败策略） | W14 Day02 |
| PolicyEngine | 策略判定：只读工具可并行，写入类工具需审批 | W14 Day02 + ADR0003 |
| ApprovalManager | 审批管理：interrupt 挂起 → confirm 恢复 → 审计记录 | ADR0003（新） |
| BudgetManager | 预算账本：token/调用次数限制，超限中断 | W14 Day02 |
| Observability | JSON Trace 输出：调用链/耗时/用量 | W14 Day03 |

---

## 九、课件知识映射（实操即复习）

| 项目阶段 | 对应课件 | 实操的知识点 |
|---|---|---|
| S0 工程初始化 | W19 Day01 + Day03 | pyproject、uv、锁文件、compose 起基础服务 |
| S1 数据模型与隔离 | W18 Day04 + W14 Day01 | SQLAlchemy ORM、pgvector 列、三级隔离、身份合同 |
| S2 解析与摄取 | W13 Day01 + Day04 | 文本层检查、OCR、切块、指纹去重、增量索引、**Celery 异步** |
| S3 检索与 RAG | W13 Day02/03 + W17 Day02 | pgvector+FTS 混合检索、RRF、Rerank、评测基线、SSE |
| S4 Harness 与 Agent | W14 Day01–05 + W15 | 七组件 Harness、观测 Trace、interrupt 审批（新）、Router（可选） |
| S5 认证与测试 | W18 Day05–07 | 持久化升级、JWT、权限过滤、pytest |
| S6 部署（可选） | W19 Day02–05 | Docker、Compose、反向代理、可观测性 |

### 🆕 新技术选入清单（未学但保留，均有明确学习价值）

| 新技术 | 来源 | 引入理由 |
|---|---|---|
| **PostgreSQL + pgvector** | 原项目技术选型 | 向量与业务数据同库，事务一致；企业 RAG 主流方案 |
| **PG tsvector 全文检索** | 原项目 tdd/07 | 混合检索稀疏路的数据库原生实现，免维护外部索引 |
| **Redis + Celery 异步任务** | 原项目技术选型 | 摄取流水线异步化，是原项目核心架构模式 |
| **MinIO 对象存储** | 原项目技术选型 | 原件持久化的标准做法，S3 兼容技能可迁移 |
| LangGraph Checkpointer | 老师 ADR0001/0003 | Graph 状态可持久化、重启可恢复 |
| LangGraph interrupt 审批 | 老师 ADR0003 | 原项目"审批绑定+人工介入"的最小实现 |
| 版本不可变 + 激活指针 | 老师 ADR0002 | 数据治理正确性的关键设计 |
| 统一错误码表 | 老师 tdd/07 | 企业 API 工程规范训练 |

---

## 十、范围边界（明确不做）

- ❌ DocReader gRPC 容器、BrowserSkill / Playwright 浏览器采集
- ❌ Outbox 模式、分布式事务、多实例 Worker/高可用集群
- ❌ Research Graph / Wiki Graph（Graph 侧聚焦 RAG 主链路 + 工具 Agent）
- ❌ 数据库 RLS 行级安全（用应用层过滤替代）
- ❌ 前端页面（**只做后端 API**，用 Swagger UI / curl 验证；前端契约见第十一节，留待后续）

---

## 十一、前端接口契约预留（后端完成后的扩展口）

后端 API 前缀统一 `/api/v1`，响应统一 `{code, message, data}` 结构（code 见第五节错误码表）：

| 端点 | 方法 | 用途 |
|---|---|---|
| /api/v1/auth/login | POST | 登录换 JWT |
| /api/v1/workspaces | GET/POST | 列出/创建工作区 |
| /api/v1/workspaces/{workspace_id} | DELETE | 删除工作区（需审批 KN-410 → confirm） |
| /api/v1/workspaces/{workspace_id}/documents | GET/POST | 列出/上传文档（上传异步，返回 version_id） |
| /api/v1/workspaces/{workspace_id}/documents/{document_id}/status | GET | 查询摄取进度（staging/active/failed） |
| /api/v1/workspaces/{workspace_id}/documents/{document_id} | DELETE | 删除文档（需审批） |
| /api/v1/workspaces/{workspace_id}/chat | POST (SSE) | 问答，流式返回 + 引用 |
| /api/v1/workspaces/{workspace_id}/threads/{thread_id}/messages | GET | 会话历史 |
| /api/v1/workspaces/{workspace_id}/eval | POST | 跑黄金测试集评测 |

> 💡 未来前端只需消费以上契约：原生 HTML+JS 用 fetch + ReadableStream 消费 POST SSE（W17 课件 6.3 节模式）。
