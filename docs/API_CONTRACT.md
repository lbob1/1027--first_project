# MiniKnora 前端 API 契约（冻结版 v1.0）

> **冻结声明**：本文档为 MiniKnora v1.0 交付冻结版，冻结日期 **2026-10-30**（M-S6-T03）。
> 依据 `00_MiniKnora_项目需求说明.md` 第十一节（前端契约）逐端点核对实际实现产出；
> 与 00 契约不一致处（实现演进产生的偏差）已显式列于文末差异表，**后续前端对接以本文档为准**。
> 错误码语义以 00 第五节 12+1 码表为准，全部响应统一 `{code, message, data}` 结构。

## 通用约定

- **Base URL**：`http://<host>:8000`（容器部署经 compose `8000:8000`）。
- **认证**：除 `/healthz`、`/metrics` 外全部端点要求 `Authorization: Bearer <token>`（M-S5-T02 起身份唯一来源；`X-User-ID` 过渡头已彻底退役，传入也不生效）。
- **响应结构**：所有 JSON 响应为 `{"code": "KN-xxx", "message": "...", "data": {...}}`；成功码 `KN-000`。
- **错误码表**（HTTP 状态见括号）：KN-400(400) 参数校验 / KN-401(401) 未认证或 token 失效 / KN-403(403) 无 workspace 权限 / KN-404(404) 资源不存在（不泄露其他 workspace 存在性）/ KN-409(409) 状态冲突 / KN-410(410) 需二次确认 / KN-422(422) 文档格式不支持或解析失败 / KN-429(429) 预算超限 / KN-500(500) 内部错误 / KN-502(502) 上游模型失败 / KN-503(503) 基础设施不可用 / KN-ORG-001(400) 上游结构解析失败。

## 端点 1：登录

- **方法/路径**：`POST /api/v1/auth/login`
- **认证**：无（换取 token 的入口）。
- **请求体**：`{"username": "string", "password": "string"}`
- **成功响应**（200，KN-000）：
  `{"code":"KN-000","message":"ok","data":{"token":"<JWT>","token_type":"bearer","expires_in":1800}}`
- **错误示例**：用户名不存在或密码错误 → **同一响应逐字节一致**（不泄露账号存在性）：
  HTTP 401 `{"code":"KN-401","message":"用户名或密码错误","data":null}`

## 端点 2：上传文档

- **方法/路径**：`POST /api/v1/workspaces/{workspace_id}/documents`（multipart/form-data）
- **认证**：Bearer（须为该 workspace 成员，非成员 KN-404）。
- **请求体**：`file: <binary>`（md/txt/docx/pdf；超 MAX_UPLOAD_MB → KN-422）。
- **成功响应**（200，KN-000）：
  `{"code":"KN-000","message":"ok","data":{"status":"accepted","workspace_id":"...","document_id":"...","version_id":"...","version_no":1,"task_id":"<celery-id>"}}`
  摄取为异步（staging），进度经端点 3 查询。
- **错误示例**：`.xyz` → HTTP 422 `{"code":"KN-422","message":"不支持的文档格式: .xyz","data":null}`

## 端点 3：摄取状态查询

- **方法/路径**：`GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/status`
- **认证**：Bearer（成员判定 + 双 WHERE 过滤）。
- **请求体**：无。
- **成功响应**（200，KN-000）：`data.versions` 为该文档全部版本（新→旧）：
  `{"code":"KN-000","message":"ok","data":{"document_id":"...","active_version_id":"...|null","versions":[{"version_no":1,"version_id":"...","status":"active|staging|retired|failed","processing_or_pending":"...仅 staging 出现"}]}}`
- **说明**：`failure_reason` 恒为 null（document_versions 无 reason 字段，v1 未做持久化失败原因）。

## 端点 4：问答（SSE 流式）

- **方法/路径**：`POST /api/v1/workspaces/{workspace_id}/chat`（`Accept: text/event-stream`）
- **认证**：Bearer（成员判定）。
- **请求体**：
  `{"question": "string(1..)", "top_k": 1..20 默认5, "thread_id": "string|null 传入则复用会话历史", "confirm": "bool|null（审批恢复用，见事件 7）"}`
- **成功响应**：HTTP 200，`text/event-stream`，事件序列：

  1. `event: sources` — `data: {"sources":[{chunk_id,document_id,document_title,version_id,snippet,rank,rrf_score,relevance_score}]}`（六字段+rrf_score+relevance_score，rank=0 最新）；
  2. `event: token` — `data: {"delta":"..."}` 多个，顺序累拼为完整答案；
  3. `event: budget` — `data: {"prompt_tokens":..,"completion_tokens":..,"total_tokens":..,...}`（预算观测）；
  4. `event: trace` — `data: {intent,latency_ms,stages:[...],...}`（done 前最后事件）；
  5. `event: done` — `data: {}`（正常收尾）。

  **专有序列**：
  - **审批挂起（删除意图，事件 7）**：`approval_required` → `trace` → `done`（本 run **无 token/budget/answer 落库**，等待 confirm 恢复）；
  - **错误**：`event: error` — `data: {"code":"KN-xxx","message":"..."}` 随后 `event: done`（流不崩，服务继续）。
- **审批恢复**：同一 chat 端点，传 `{"thread_id":"<挂起会话>","confirm":true}` 恢复执行删除（`false` 拒绝）；`confirm` 传 bool 而 `thread_id` 缺失 → KN-400；无挂起 thread 恢复 → KN-400。
- **错误示例**：预算超限 → 流内 `{"code":"KN-429","message":"..."}`。

## 端点 5：健康检查

- **方法/路径**：`GET /healthz`；**认证豁免**。
- **响应**（200）：`{"code":"KN-000","message":"ok","data":{"service":"MiniKnora","version":"0.1.0"}}`

## 端点 6：监控指标

- **方法/路径**：`GET /metrics`；**认证豁免**（理由：仅聚合值，无文档内容与用户数据）。
- **响应**：Prometheus exposition 格式（非 `{code,message,data}`）。含：
  `http_requests_total{method,path,status}`（path=路由模板）/ `http_request_duration_seconds{method,path}` / `llm_tokens_total{kind=prompt|completion}` / `ingestion_queue_depth`（staging 计数）。

## 与 00 第十一节契约的差异表（实现演进偏差，以本文档为准）

| # | 00 契约端点 | v1.0 实际状态 | 说明 |
|---|---|---|---|
| 1 | `GET/POST /api/v1/workspaces` | **未实现 HTTP 端点** | 能力在 service 层完整（tests 覆盖），v1 前端无对接需求；造数走脚本 |
| 2 | `DELETE /api/v1/workspaces/{workspace_id}` | **未实现 HTTP 端点** | 同上；阻断式删除（子资源非空 KN-409）已在 service 层 |
| 3 | `GET /api/v1/workspaces/{ws}/documents`（列表） | **未实现 HTTP 端点** | service 层完整（workspace_id 强制进 WHERE） |
| 4 | `DELETE /api/v1/workspaces/{ws}/documents/{document_id}` | **未实现 HTTP 端点** | 删除改为 **chat 删除意图 → approval_required 审批流**（00 第十节演进为准绳）；service 层阻断式删除保留 |
| 5 | `GET /api/v1/workspaces/{ws}/threads/{thread_id}/messages` | **未实现 HTTP 端点** | messages 落库完整（user/assistant 行+citations），读取经 chat 的 `thread_id` 多轮复用；HTTP 读取端点留 v2 |
| 6 | `POST /api/v1/workspaces/{ws}/eval` | **未实现 HTTP 端点** | 评测为脚本形态 `eval/run_eval.py`（--phase a/b），不暴露 HTTP |
| 7 | 审批恢复 `chat/confirm` 类端点 | **合并进 chat 端点** | 00 未单列；实现以 `confirm` 字段 + `thread_id` 复用同一 SSE 端点（本文档端点 4） |
| 8 | （00 未定义） | **新增** `GET /metrics` | M-S6-T02 监控端点，认证豁免 |
| 9 | （00 未定义） | **新增** JWT 认证 | 00 契约写 `X-User-ID` 开发过渡头；M-S5-T02 起改 Bearer JWT，过渡头彻底失效 |
| 10 | （00 未定义） | **新增** SSE `error` 事件 | 流内 AppError 以 `event: error` 显式暴露后收尾 `done`（00 仅定义正常序列） |

## 已知行为约定（冻结）

- 摄取版本状态机：`staging → active ⇄ retired`，失败 `failed`；仅 staging 可激活（KN-409 阻断其他流转）。
- 版本不可变：version_no/content_hash/file_path 只写一次；`documents.active_version` 指针指向当前 active。
- 隔离语义：一切跨 workspace 访问返回 KN-404（不泄露存在性）；非成员同码。
- B 区检索隔离：sources 只含当前 workspace 的 chunk（eval phase b 零泄露）。
