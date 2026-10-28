# MiniKnora 分阶段执行计划

> 版本：v2.0 ｜ 日期：2026-10-28
> 配套文档：`00_MiniKnora_项目需求说明.md` v2.0（基础设施四件套、7 表模型、Harness 七组件、错误码、安全细则）
> 适用：单人 + PyCharm + vibe coding，**后端优先**，每轮一个任务。
> ⭐ 本版重点：基础组件完整复用原项目（PostgreSQL+pgvector / Redis / Celery / MinIO）；每阶段提示词以"提示词卡片"形式给出**使用位置、服务环节、作用与影响输出**。

---

## 〇、执行纪律（每个阶段都遵守，继承原项目方法论）

1. **每轮只做一个任务**（编号 M-Sx-Txx），做完更新 STATUS 文件，停在任务边界；
2. **不虚报**：测试没跑就说没跑，失败就记失败（简化四态：PASS / FAIL / BLOCKED / NOT_STARTED）；
3. **保护现场**：开工先 `git status`，不动无关文件；
4. **提示词用法**：找到当前任务所属阶段的提示词卡片 → 填占位符 → 发给 AI → 逐条核对验收标准 → **本地真实运行验证**（AI 说"应该能跑"不算数）。

### STATUS 文件规范（S0 创建，每任务更新）

```markdown
# MiniKnora 实施状态
| 任务 | 状态 | 日期 | 备注（真实测试结果/阻塞原因） |
|---|---|---|---|
| M-S0-T01 | PASS | 2026-xx-xx | uv sync 通过；compose 三服务健康检查通过 |
```

---

## 一、阶段依赖总览

```
S0 工程与基础服务
   ↓
S1 数据模型与隔离   ──→ 
S2 异步摄取管线    ──→ 
S3 混合检索与RAG   ──→ 
S4 Harness与Agent ──→ 
S5 认证与测试       ──→ 
S6 部署(可选)
                        (依赖S1表)        (依赖S2数据)          (依赖S3问答链路)
```

| 阶段 | 主题 | 依赖 | 预计 |
|---|---|---|---|
| S0 | 可复现工程 + 基础服务（PG/Redis/MinIO） | 无 | 0.5 天 |
| S1 | ORM 模型与多级隔离（pgvector 列就绪） | S0 | 1 天 |
| S2 | Celery 异步摄取管线（解析/切块/入库/增量） | S1 | 2 天 |
| S3 | 混合检索 + RAG Graph + SSE + 评测基线 | S2 | 2 天 |
| S4 | Harness 七组件 + interrupt 审批 + Trace | S3 | 2 天 |
| S5 | JWT 认证 + pytest 全量回归 | S4 | 1.5 天 |
| S6 | 应用容器化 + 收尾验收（可选） | S5 | 1 天 |

---

## 二、S0：可复现工程 + 基础服务（W19 Day01 + Day03）

**目标**：建立 uv 可复现工程骨架，并用 docker-compose 起齐三个基础服务——这是后续一切的地基。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S0-T01 | `pyproject.toml` + `uv lock` + 目录骨架（app/api、app/core、app/models、app/services、app/workers、app/graphs、tests/、compose.yaml） | 可 `uv sync` 的空工程 |
| M-S0-T02 | `compose.yaml`：PostgreSQL（**装 pgvector 扩展**）+ Redis + MinIO，含健康检查与持久化卷 | 三服务可一键启动 |
| M-S0-T03 | `.env.example`（OPENAI_API_BASE/KEY/模型型号/DATABASE_URL/REDIS_URL/MINIO_*）+ 配置加载 + 日志脱敏工具 | config.py + logger.py |
| M-S0-T04 | FastAPI 空应用 + 全局异常处理器（统一 KN-xxx 错误码结构）+ /healthz + STATUS 文件 | main.py + STATUS.md |

**验收标准**：
- ✅ `uv sync && uv run uvicorn app.main:app` 启动成功，/healthz 返回 200；
- ✅ `docker compose up -d` 后 `docker compose ps` 三服务均 healthy；`psql` 可执行 `CREATE EXTENSION vector`；
- ✅ MinIO 控制台可登录，能手工创建 bucket；
- ✅ 制造异常请求返回 `{code: "KN-500", ...}` 统一结构；日志中 API key 脱敏为 `***`。

### 🎯 提示词卡片 P-S0

- **使用位置**：S0 阶段的 4 轮会话，分别服务任务 M-S0-T01 ~ T04（一轮一任务）。
- **服务环节**：**工程初始化环节**——项目从零到"可运行空壳 + 基础设施在位"。
- **作用**：约束 AI 只搭骨架不写业务逻辑，并强制基础组件与需求文档第二节职责表一致，防止 AI 擅自替换组件（如用 SQLite 走捷径）。
- **影响输出**：直接决定工程可复现性（uv 锁文件）、三服务可用性（compose）、配置与日志规范（脱敏）。这三项做错，后续所有阶段的调试成本会翻倍。

```text
【P-S0 模板正文】
在 {仓库路径} 执行 MiniKnora S0 阶段的唯一任务 {M-S0-T01/T02/T03/T04}。
先读：00_需求说明.md 第二节（组件职责表）+ 第六节（脱敏细则）+ 本计划 S0 验收标准。
本轮范围（严格限定）：{该任务的完整内容，从任务表抄写}。
技术约束：
- 依赖统一用 uv 管理，全部声明进 pyproject.toml，禁止散装 pip install；
- 基础组件只允许 PostgreSQL(pgvector)/Redis/MinIO，禁止用 SQLite/Chroma 等替代；
- {该任务的额外约束，如：pgvector 镜像用 pgvector/pgvector:pg16}。
验收自检：完成后逐条列出 S0 验收标准中与本任务相关项的实际执行结果（真实命令输出）。
交付：{产出物清单} + STATUS 更新（四态）+ 下一任务建议，然后停止，不跨任务。
```

- **填写说明**：`{仓库路径}` 填你的项目根目录；任务号与范围**从 S0 任务表原样抄写**（不要让 AI 自由发挥范围）；`{该任务的额外约束}` 按需填写镜像版本、端口等细节。

---

## 三、S1：数据模型与多级隔离（W18 Day04 + W14 Day01）

**目标**：落地 7 张表的 SQLAlchemy 模型（含 pgvector 向量列与 tsvector 生成列）与三级隔离——全项目安全的地基。

**前置**：S0 完成（PG 可连接、pgvector 扩展可创建）。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S1-T01 | 7 张表 ORM 模型：chunks 含 `embedding vector(N)` 与 `tsv tsvector` 生成列（GIN 索引 + 向量索引）；建表与迁移脚本 | models.py + init_db.py |
| M-S1-T02 | workspace / document 基础 CRUD service（**每个查询方法强制 workspace_id 过滤**） | services/workspace.py 等 |
| M-S1-T03 | 版本不可变约束：document_versions 无 UPDATE/DELETE 路径；上传新文件 → 新版本行 + active_version 指针切换 | services/version.py |
| M-S1-T04 | 隔离测试：跨 workspace 读/写返回 KN-404；版本不可变测试 | tests/test_isolation.py |

**验收标准**：
- ✅ 向 workspace A 写入文档后，以 workspace B 身份查询返回**空列表**（不泄露存在性）；
- ✅ 任何"修改版本"的调用被拒绝（代码无此路径 + 测试证明）；
- ✅ 同一文档二次上传后 version_no 递增、旧行原样保留、active_version 指向新行；
- ✅ `SELECT * FROM chunks LIMIT 1` 可见 embedding 与 tsv 列有值（插入测试数据后）；
- ✅ pytest 通过且含至少 6 个隔离/版本负例断言。

### 🎯 提示词卡片 P-S1

- **使用位置**：S1 阶段 4 轮会话，服务任务 M-S1-T01 ~ T04。
- **服务环节**：**数据层建模环节**——表结构、ID 体系、隔离规则在此定型。
- **作用**：把需求文档第四节的表结构与第六节前 5 条安全细则"翻译"成 ORM 代码；关键是**字段名逐字照抄**（workspace_id/version_no/...），保证后续 API、检索、Trace 全链路命名一致。
- **影响输出**：决定全项目的数据契约。字段名一旦跑偏，S3 的引用溯源（filename+version_no+seq_no）和 S4 的身份绑定将连锁返工。

```text
【P-S1 模板正文】
在 {仓库路径} 执行 MiniKnora S1 阶段的唯一任务 {M-S1-T01/T02/T03/T04}。
先读：00_需求说明.md 第四节（表结构/核心不变量）+ 第六节第 1/2/3/4/5 条（隔离与版本细则）+ STATUS。
本轮范围：{该任务内容，从任务表抄写}。
硬性约束：
- 字段命名严格照抄需求文档第四节，全部主键用 UUID；
- 所有查询方法必须绑定 workspace_id 参数并在 SQL 中生效，禁止先查全表再内存过滤；
- document_versions 不提供任何 update/delete 接口（模型层就不定义）；
- 用户角色只从数据库判定，不从请求文本或 metadata 推断；
- embedding 维度 N 写入 .env（EMBEDDING_DIM），向量列定义引用该配置。
验收自检：逐条给出 S1 验收标准中与本任务相关项的真实测试输出。
交付：{产出物} + pytest 用例 + STATUS 更新，然后停止。
```

- **填写说明**：`{EMBEDDING_DIM}` 依所选 embedding 模型填（如 1024）；范围照抄任务表；若 AI 给出"顺便把 S2 也做了"的建议，拒绝并记录。

---

## 四、S2：Celery 异步摄取管线（W13 Day01 + Day04 + 新技术 Celery/MinIO）

**目标**：文档进得来：上传 → MinIO 存原件 → Celery 异步执行 解析（含 OCR）→ 指纹 → 版本 → 切块 → pgvector 入库 → 增量索引。

**前置**：S1 完成。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S2-T01 | MinIO 客户端封装：bucket 初始化、对象上传下载（file_path 存 object key） | services/storage.py |
| M-S2-T02 | 解析器：PDF 文本层检查（pypdf）→ 无文本层页面 PyMuPDF 渲染 + RapidOCR；Word（python-docx）；Markdown 直读 | services/parser.py |
| M-S2-T03 | Celery 基座：celery_app（Redis broker）+ 任务状态查询接口 | workers/celery_app.py + api/status.py |
| M-S2-T04 | 摄取任务：切块（300~500 字/重叠 50）→ content_hash 指纹 → embedding 写入 chunks（向量+tsv 同事务）→ 状态流转 staging→active→retired | workers/ingestion.py |
| M-S2-T05 | 增量索引：上传时对比 content_hash——未变跳过并提示；变更 → 新版本 + 旧版本 chunks 置 retired | services/version.py 扩展 |
| M-S2-T06 | 上传 API：POST /documents（multipart）→ 存 MinIO → 建 staging 版本 → 派发 Celery 任务 → 立即返回 version_id | api/documents.py |

**验收标准**：
- ✅ 上传接口在 1 秒内返回（异步生效），随后 status 接口可见 staging→active 流转；
- ✅ 扫描版 PDF 经 OCR 入库，检索层可查到 OCR 文本；
- ✅ 同一文件重复上传 → 提示"内容未变"，**chunks 表无新增行**；
- ✅ 修改后重传 → version_no +1，检索只命中新版本（旧行 status=retired）；
- ✅ Worker 停止时上传 → status 停在 staging 且有明确 pending 提示（不静默失败）；
- ✅ 三种格式各一个 pytest 冒烟用例（Celery 任务用 `.apply` 同步模式测）。

### 🎯 提示词卡片 P-S2

- **使用位置**：S2 阶段 6 轮会话，服务任务 M-S2-T01 ~ T06。
- **服务环节**：**数据摄入环节**——原件持久化（MinIO）、异步流水线（Celery）、解析质量（OCR）三条线在此汇合。
- **作用**：这是引入**未学新技术最密集**的阶段（MinIO/Celery/pgvector 写入）。提示词的职责是强制 AI 说明每个新组件的最小用法并给出可运行的验证命令，防止"看起来写了但根本没跑通"。
- **影响输出**：决定入库数据的质量与异步可靠性。指纹/增量逻辑出错会导致重复索引（检索结果重复）；Celery 状态流转出错会导致文档永远卡在 staging。

```text
【P-S2 模板正文】
在 {仓库路径} 执行 MiniKnora S2 阶段的唯一任务 {M-S2-T0x}。
先读：00_需求说明.md 第二节（MinIO/Celery 职责）+ 第六节第 5/6 条（版本状态流转）+ W13 课件 {Day01/Day04 对应章节} + STATUS。
本轮范围：{该任务内容，从任务表抄写}。
技术约束：
- 上传原件先写 MinIO 再建 version 行，file_path 存 object key，不存本地路径；
- Celery 任务里所有写库走同一事务，失败回滚并把 version.status 置 failed（不静默）；
- OCR 只对无文本层页面触发；embedding 走 .env 的 compatible-mode 配置，key 不入日志；
- 切块指纹 = chunk content_hash；文档指纹 = 全文 content_hash，两者分开存；
- 解析失败的文件置 failed 并返回 KN-422，不影响其他任务。
新组件验证要求（未学技术必须实证）：
- {MinIO/Celery/...}：给出本任务涉及的最小验证命令与我应看到的预期输出。
验收自检：逐条给出 S2 验收标准中与本任务相关项的真实输出。
交付：{产出物} + 测试 + STATUS 更新，然后停止。
```

- **填写说明**：`W13 课件对应章节`按任务填（T02 填 Day01 解析、T04/T05 填 Day04 增量）；**"新组件验证要求"一段不可删**——这是你在未学技术上不踩坑的保险。

---

## 五、S3：混合检索 + RAG Graph + SSE + 评测基线（W13 Day02/03 + W17 Day02）

**目标**：答案出得去：pgvector 向量路 + tsvector 全文路 双路召回 → RRF 融合 → Rerank 精排 → LangGraph RAG Graph（Checkpointer）→ SSE 流式回答 + 引用。

**前置**：S2 完成（库内有 active 状态的 chunks）。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S3-T01 | 稀疏路：tsvector 全文检索 top-k（同事务带 workspace + active 过滤） | services/retrieval_fts.py |
| M-S3-T02 | 稠密路：query embedding → pgvector 余弦近邻 top-k（同样过滤） | services/retrieval_vec.py |
| M-S3-T03 | 融合层：chunk_id 去重 → RRF（k=60）→ 百炼 rerank 精排（**失败自动降级 RRF 分数**，日志可见降级原因） | services/fusion.py |
| M-S3-T04 | LangGraph RAG Graph：State{query, workspace_id, thread_id, retrieved, answer, citations} → 节点：检索→重排→生成→引用组装；接 PostgreSQL Checkpointer（run_id/thread_id） | graphs/rag_graph.py |
| M-S3-T05 | 问答 API：POST /chat（SSE 流式），事件含 token 增量与最终 citations | api/chat.py |
| M-S3-T06 | 黄金测试集（10~20 条 QA）+ 评测脚本：recall@5、引用正确率 | eval/golden_set.json + eval/run_eval.py |

**验收标准**：
- ✅ 混合检索 recall@5 **≥ 任一单路**（评测脚本输出三列对照表证明）；
- ✅ rerank 不可用时（假 key）系统仍返回 RRF 结果，日志有降级记录；
- ✅ 每条引用可回溯 filename + version_no + seq_no，且全部属于当前 workspace（**引用越权 = 验收失败**）；
- ✅ `curl -N -X POST .../chat` 可观察流式输出；
- ✅ 进程重启后同 thread_id 继续会话（Checkpointer 生效——新技术验证点）。

### 🎯 提示词卡片 P-S3

- **使用位置**：S3 阶段 6 轮会话，服务任务 M-S3-T01 ~ T06。
- **服务环节**：**检索与生成环节**——项目面向用户的核心价值链（检索质量 + 回答可信度）。
- **作用**：强制两路检索的过滤条件一致（workspace + active）、RRF 公式标准化（k=60）、引用来自真实检索结果而非模型编造——这三点是 RAG 质量工程的底线。
- **影响输出**：直接决定检索质量指标（recall@5）、引用可信度与流式体验；Checkpointer 决定会话可恢复性。

```text
【P-S3 模板正文】
在 {仓库路径} 执行 MiniKnora S3 阶段的唯一任务 {M-S3-T0x}。
先读：00_需求说明.md 第三节 MF-06/07 + 第六节第 10 条（引用溯源）+ W13 课件 {Day02/Day03 对应章节} + W17 课件 Day02 的 POST SSE 模式 + STATUS。
本轮范围：{该任务内容，从任务表抄写}。
技术约束：
- 稀疏路与稠密路的 SQL 都必须带 workspace_id 过滤与 status='active' 条件，两路条件完全一致；
- RRF 公式：score = Σ 1/(60 + rank)，两路各自排名后合并，chunk_id 去重后再融合；
- rerank 失败降级为 RRF 分数排序，不抛错不中断，降级事件写入日志；
- Graph 用 LangGraph StateGraph，Checkpointer 持久化到 PostgreSQL（连接串复用 DATABASE_URL）；
- citations 只能从 retrieved chunks 组装（filename+version_no+seq_no），禁止把模型生成文本当引用；
- SSE 用 POST + fetch 可消费的事件格式（W17 模式），事件类型：token / citation / done / error。
新组件验证要求：{pgvector 算子/Checkpointer/SSE}：给出最小验证命令与预期输出。
验收自检：逐条给出 S3 验收标准中与本任务相关项的真实输出（评测脚本的对照表必须贴真实数字）。
交付：{产出物} + STATUS 更新，然后停止。
```

- **填写说明**：T01/T02 填 W13 Day03 检索章节；T06 填 Day02 评测章节；评测脚本输出的对照表是**量化证据**，必须贴进 STATUS。

---

## 六、S4：Harness 七组件与 Agent（W14 Day01–05 + ADR0003 新技术）

**目标**：把"能用的 RAG"升级为"受控的 Agent"：七组件 Harness 全套落地（轻量=单模块实现，结构不删）+ interrupt 审批 + JSON Trace。

**前置**：S3 完成。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S4-T01 | ModelGateway + ContextManager：统一模型调用入口（重试/超时/用量统计）与上下文装配（身份/历史/证据） | core/gateway.py + core/context.py |
| M-S4-T02 | ToolRegistry + PolicyEngine：混合检索注册为 Tool（schema/只读标记/失败策略）；策略判定（只读可并行、写入需审批） | core/tool_registry.py + core/policy.py |
| M-S4-T03 | Agent Graph：Router 判断是否检索 → 调用工具 → 生成（W15 Router 模式，单 Agent + 工具） | graphs/agent_graph.py |
| M-S4-T04 | BudgetManager：每 run 限 token 与工具调用次数，超限中断返回 KN-429 | core/budget.py |
| M-S4-T05 | ApprovalManager（🆕）：删除类操作 → LangGraph interrupt 挂起 → confirm=true 恢复执行；审批事件入 messages 审计 | core/approval.py |
| M-S4-T06 | Observability：每次 run 输出 JSON Trace（工具调用链/耗时/token），中间件式接入 | core/trace.py |

**验收标准**：
- ✅ 负例 1：用户 A 访问 workspace B 文档 → 全链路不出现 B 的内容（**以 Trace 为证据**）；
- ✅ 负例 2：构造超预算 run → 中断并返回 KN-429，Trace 记录中断点；
- ✅ 负例 3：不带 confirm 的删除 → 挂起（KN-410）；confirm=true → 执行且审计有记录；
- ✅ 七组件均有独立模块与最小单测（结构完整性检查）；
- ✅ 每条 Trace 为合法 JSON，含 run_id、工具调用次数、token 消耗，不含 API key 与文档正文。

### 🎯 提示词卡片 P-S4

- **使用位置**：S4 阶段 6 轮会话，服务任务 M-S4-T01 ~ T06。
- **服务环节**：**工程控制环节**——给 S3 的"能力"加上"约束"。身份/预算/审批/观测四类控制在此成型。
- **作用**：这是**最贴近原项目精髓**的阶段（对应 ADR0003 与 Harness 契约）。提示词必须强制"身份只来自程序侧"、"审批用 LangGraph 原生 interrupt 不自造轮子"，否则 AI 容易用快捷但错误的方式实现（比如从对话文本判断角色）。
- **影响输出**：决定系统的安全下限与可观测性；三类负例测试是本阶段的硬验收，也是 M3 里程碑的直接依据。

```text
【P-S4 模板正文】
在 {仓库路径} 执行 MiniKnora S4 阶段的唯一任务 {M-S4-T0x}（Harness 控制层组件）。
先读：00_需求说明.md 第八节（Harness 七组件职责表）+ 第六节全部细则 + W14 课件 {对应 Day} + ADR0003 的 interrupt 设计思想 + STATUS。
本轮范围：{该任务内容，从任务表抄写}。
硬性约束：
- 身份只来自程序侧（JWT/数据库），对话文本、检索结果、文档 metadata 一律不参与权限判定；
- 审批用 LangGraph 原生 interrupt + Checkpointer 恢复，不自造审批轮询轮子；
- 预算在每次模型/工具调用前检查，超限抛出携带 KN-429 的业务异常并终止 run；
- Trace 中间件式接入：不改 S3 的 Graph 节点内部逻辑，只在外层包装；
- Trace 不含 API key 与文档正文（只含摘要与统计值）；
- 七组件各自独立成模块（core/ 下），接口签名写类型注解。
验收自检：给出三类负例（越权/超预算/未审批）中与本任务相关者的真实测试输出。
交付：{产出物} + 负例测试 + STATUS 更新，然后停止。
```

- **填写说明**：课件章节按任务填（T01 填 W14 Day01/02、T05 填 ADR0003 思路、T06 填 Day03）；若 AI 建议合并多个组件到一个文件，**拒绝**——结构完整性是本阶段验收项。

---

## 七、S5：认证与自动化测试（W18 Day05–07）

**目标**：补齐 JWT 登录权限，用 pytest 建立全量回归防线。

**前置**：S4 完成（权限测试需要 Harness 在位）。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S5-T01 | JWT 登录：/auth/login 签发；依赖注入当前用户；密码 bcrypt | api/auth.py + core/security.py |
| M-S5-T02 | 权限过滤回归：workspace_members 授权检查接入全部业务端点 | 中间件/依赖 |
| M-S5-T03 | pytest 全量：模型/隔离/摄取/检索/审批/认证 六组用例 + 覆盖率报告 | tests/ 完整套件 |

**验收标准**：
- ✅ 无 token → KN-401；无效 token → KN-401；有 token 无权限 → KN-404（不泄露存在性）；
- ✅ `uv run pytest` 全绿，真实输出贴 STATUS；
- ✅ 覆盖率 ≥ 70%（核心 services 模块）；
- ✅ Celery 相关测试用同步模式（`.apply`）跑通，不依赖 Worker 常驻。

### 🎯 提示词卡片 P-S5

- **使用位置**：S5 阶段 3 轮会话，服务任务 M-S5-T01 ~ T03。
- **服务环节**：**认证与质量防线环节**——对外暴露前的最后一道安全门 + 回归基线。
- **作用**：把前四阶段的隔离/审批/预算规则**从"代码里存在"变成"测试里被证明"**；并约束测试不得为了变绿而放宽规则。
- **影响输出**：决定项目能否宣称"核心完整"（M4 里程碑判据）；测试套件也是 S6 容器内终验的复用资产。

```text
【P-S5 模板正文】
在 {仓库路径} 执行 MiniKnora S5 阶段的唯一任务 {M-S5-T0x}。
先读：00_需求说明.md 第五节错误码 + 第六节第 1/2/3 条 + W18 课件 {Day06/Day07 对应章节} + STATUS。
本轮范围：{该任务内容，从任务表抄写}。
硬性约束：
- JWT 密钥走 .env；密码只存 bcrypt hash；
- 测试用 fixture 隔离：每个测试用独立数据库 schema 或事务回滚，禁止共用脏数据；
- Celery 任务测试用 .apply() 同步执行；
- 不得为了让测试通过而修改任何隔离/审批/预算规则本身——发现规则有 bug 先记录再单独修；
- 失败用例如实保留并记录原因，不删不跳过。
验收自检：贴真实 pytest 输出（含覆盖率行）；对照第三节验收标准逐条打勾。
交付：{产出物} + STATUS 更新，然后停止。
```

- **填写说明**：T01/T02 填 W18 Day06；T03 填 Day07；**"不得放宽规则"一条是本卡片的灵魂**，不可删。

---

## 八、S6：部署与收尾（W19 Day02–05，可选但推荐）

**目标**：应用容器化、全栈 Compose 一键起、冻结前端契约、项目收官。

**前置**：S5 完成。

| 任务 | 内容 | 产出物 |
|---|---|---|
| M-S6-T01 | 应用 Dockerfile + 扩展 compose：加入 api 与 worker 两个服务（复用 S0 的三基础服务） | 部署文件 |
| M-S6-T02 | 可观测性：/metrics 基础指标（请求数/延迟/token 消耗/摄取队列深度）+ 请求日志中间件 | core/metrics.py |
| M-S6-T03 | 终验：容器内跑黄金测试集 + 全量 pytest + 前端契约文档冻结（对照需求文档第十一节逐端点核对） | 验收报告 |

**验收标准**：
- ✅ `docker compose up` 后从上传到问答的端到端链路可用（api + worker + 三基础服务共 5 容器 healthy）；
- ✅ 容器内评测 recall@5 与本地一致（偏差 < 5%）；
- ✅ 前端契约文档与实际 API 一致（逐端点核对）；
- ✅ 镜像内无 .env / 密钥（运行时挂载），容器非 root 运行。

### 🎯 提示词卡片 P-S6

- **使用位置**：S6 阶段 3 轮会话，服务任务 M-S6-T01 ~ T03。
- **服务环节**：**交付环节**——从"我电脑上能跑"到"任何人一键可复现"（对应 W19 Day01 的三层状态区分）。
- **作用**：约束镜像安全（无密钥、非 root）与终验的**证据性**（评测数字必须容器内真实产出，不允许引用本地结果）。
- **影响输出**：决定 M5 里程碑（交付完整）判据与前端后续开发的契约稳定性。

```text
【P-S6 模板正文】
在 {仓库路径} 执行 MiniKnora S6 阶段的唯一任务 {M-S6-T0x}。
先读：00_需求说明.md 第十一节（前端契约）+ W19 课件 {对应 Day} + STATUS。
本轮范围：{该任务内容，从任务表抄写}。
硬性约束：
- 镜像内不打包 .env 与任何密钥，运行时以环境变量/挂载注入；
- 容器以非 root 用户运行；worker 与 api 共用同一镜像不同 command；
- 指标只暴露聚合值（请求数/延迟/用量），不暴露文档内容与用户输入；
- 终验数字（recall@5、pytest 结果）必须在容器内真实执行后贴原始输出，不得引用本地历史结果。
验收自检：对照 S6 验收标准逐条给出容器内真实证据。
交付：{产出物} + STATUS 更新 + 最终阶段总结（做了什么/简化了什么/遗留什么），然后停止。
```

- **填写说明**：T01 填 W19 Day02/03；T02 填 Day05；T03 无需课件章节，重点核对需求文档第十一节。

---

## 九、里程碑检查点

| 检查点 | 判据 | 对应原项目思想 |
|---|---|---|
| 🎯 M1（S1 后） | 隔离与版本不变量测试全绿 | ADR0002/0005 落地 |
| 🎯 M2（S3 后） | 混合检索 ≥ 单路 + 引用可溯源 + 断线重启可续 | PoC-01/09 等价验证 |
| 🎯 M3（S4 后） | 三类负例（越权/超预算/未审批）全拦截 + 七组件结构完整 | ADR0003 + Harness 契约 |
| 🎯 M4（S5 后） | 全量 pytest 绿 + 认证链路完整 | tdd/08 出口条件 |
| 🎯 M5（S6 后） | 5 容器端到端 + 契约冻结 | G-FULL 简化版门禁 |

> 💡 完成度自查：走到 M4 即为"核心完整"；M5 为"交付完整"。每过一个里程碑，在 STATUS 写一段 3~5 行阶段总结（做了什么/简化了什么/遗留什么）。
