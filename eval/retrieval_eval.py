"""M-S3-T05 检索评测基线：三路（fts/vec/hybrid）对比 + recall@5 / MRR@5 数字化。

只消费既有公共函数（search_fts/search_vec/search_hybrid），不改 app/ 任何一行。
运行：uv run python eval/retrieval_eval.py（在 pyknora 目录下）
流程：service 正例路径造数（3 份语料到评测 A 区 + 1 份干扰文档到 B 区）
  → 逐用例三路查询 → 指标汇总（控制台表 + eval/report.md）
  → 隔离用例（B 区同批 query，断言 recall@5=0）
  → 双清理（两阶段：删除提交与独立会话断言分离）。
脚本失败显式抛错退出码非 0；指标数字以真实 API 调用为准，不 mock。
"""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 脚本模式 sys.path[0]=eval/，补项目根以导入 app 包
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import get_session  # noqa: E402
from app.models.models import (  # noqa: E402
    Chunk,
    Document,
    DocumentVersion,
    Message,
    User,
    Workspace,
    WorkspaceMember,
)
from app.services import storage  # noqa: E402
from app.services import document as doc_svc  # noqa: E402
from app.services import workspace as ws_svc  # noqa: E402
from app.services.retrieval_fts import search_fts  # noqa: E402
from app.services.retrieval_vec import search_vec  # noqa: E402
from app.services.retrieval_hybrid import search_hybrid  # noqa: E402
from app.services.upload import register_upload  # noqa: E402
from app.workers.ingestion import ingest_version  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
REPORT_PATH = Path(__file__).resolve().parent / "report.md"
ROUTES = ("fts", "vec", "hybrid")
TOP_K = 5
DOC_B = "周末计划去郊外徒步，需要准备登山鞋和水壶，还要带足饮用水。"

CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _bootstrap_clean() -> None:
    """自愈清理：清除上次运行可能残留的数据（干净起步）。"""
    with get_session() as s:
        ws_ids = list(s.execute(select(Workspace.workspace_id)).scalars())
    for wid in ws_ids:
        for k in storage.list_object_keys(prefix=str(wid)):
            storage.remove_object(k)
    with get_session() as s:
        s.execute(Message.__table__.delete())
        s.execute(Chunk.__table__.delete())
        s.execute(Document.__table__.update().values(active_version=None))  # 先断 FK 再删版本行
        s.execute(DocumentVersion.__table__.delete())
        s.execute(delete(Document))
        s.execute(delete(WorkspaceMember))
        s.execute(delete(Workspace))
        s.execute(delete(User))


def _ingest(uid, wsid, filename, data) -> None:
    with get_session() as s:
        doc = doc_svc.create_document(s, user_id=uid, workspace_id=wsid, filename=filename)
        s.flush()
        doc_id = doc.document_id
        r = register_upload(s, user_id=uid, workspace_id=wsid,
                            document_id=doc.document_id, filename=filename, data=data)
    assert r["status"] == "accepted", r
    ar = ingest_version.apply(args=[r["version_id"]])
    assert ar.successful(), f"摄取失败: {ar.result}"
    with get_session() as s:
        v = s.get(DocumentVersion, uuid.UUID(r["version_id"]))
        assert v.status == "active", v.status


def _search(route, wsid, query):
    with get_session() as s:
        fn = {"fts": search_fts, "vec": search_vec, "hybrid": search_hybrid}[route]
        return fn(s, workspace_id=wsid, query=query, top_k=TOP_K)


def mrr_at_5(hits, expect_filename) -> float:
    for i, h in enumerate(hits, start=1):
        if h["filename"] == expect_filename:
            return 1.0 / i
    return 0.0


def recall_at_5(hits, expect_filename) -> float:
    return 1.0 if any(h["filename"] == expect_filename for h in hits) else 0.0


def main() -> None:
    _bootstrap_clean()

    # ---- 造数：A 区三份语料 + B 区干扰文档 ----
    with get_session() as s:
        user = User(username=f"eval-{uuid.uuid4().hex[:8]}", password_hash="not-a-real-hash")
        s.add(user)
        s.flush()
        ws_a = ws_svc.create_workspace(s, user_id=user.user_id, name=f"ws-eval-{uuid.uuid4().hex[:8]}")
        user_b = User(username=f"eval-b-{uuid.uuid4().hex[:8]}", password_hash="not-a-real-hash")
        s.add(user_b)
        s.flush()
        ws_b = ws_svc.create_workspace(s, user_id=user_b.user_id, name=f"ws-eval-b-{uuid.uuid4().hex[:8]}")
        s.flush()
        uid, wid_a = user.user_id, ws_a.workspace_id
        uid_b, wid_b = user_b.user_id, ws_b.workspace_id
    for c in CASES["corpus"]:
        assert len(c["text"]) >= 500, f"{c['filename']} 语料不足 500 字（{len(c['text'])}）"
        _ingest(uid, wid_a, c["filename"], c["text"].encode("utf-8"))
    _ingest(uid_b, wid_b, "徒步计划.txt", DOC_B.encode("utf-8"))

    # ---- 逐用例三路查询 ----
    rows = []  # {case_id, mode, expect, fts/vec/hybrid: (hits, recall, mrr)}
    for case in CASES["cases"]:
        per = {}
        for route in ROUTES:
            hits = _search(route, wid_a, case["query"])
            per[route] = (hits, recall_at_5(hits, case["expect_filename"]),
                          mrr_at_5(hits, case["expect_filename"]))
        rows.append({**case, **per})
        detail = "  ".join(
            f"{r}={[f'{h[chr(102)+chr(105)+chr(108)+chr(101)+chr(110)+chr(97)+chr(109)+chr(101)]}@{i+1}' for i, h in enumerate(per[r][0])]}"
            for r in ROUTES
        )
        print(f"[{case['case_id']}/{case['expect_mode']}] {case['query']!r} 期望={case['expect_filename']}")
        print(f"    {detail}")

    # ---- 指标汇总 ----
    summary = {mode: {r: {"recall": 0.0, "mrr": 0.0} for r in ROUTES} for mode in ("literal", "semantic", "both")}
    for mode in summary:
        sub = [row for row in rows if row["expect_mode"] == mode]
        for r in ROUTES:
            summary[mode][r]["recall"] = sum(x[r][1] for x in sub) / len(sub)
            summary[mode][r]["mrr"] = sum(x[r][2] for x in sub) / len(sub)
    overall = {r: {"recall": sum(x[r][1] for x in rows) / len(rows),
                   "mrr": sum(x[r][2] for x in rows) / len(rows)} for r in ROUTES}

    print("\n===== 指标汇总（recall@5 / MRR@5）=====")
    header = f"{'用例类':<10}{'指标':<10}{'fts':>8}{'vec':>8}{'hybrid':>8}"
    print(header)
    for mode in ("literal", "semantic", "both"):
        for metric in ("recall", "mrr"):
            line = f"{mode:<10}{metric+'@5':<10}"
            for r in ROUTES:
                line += f"{summary[mode][r][metric]:>8.3f}"
            print(line)
    for metric in ("recall", "mrr"):
        line = f"{'overall':<10}{metric+'@5':<10}"
        for r in ROUTES:
            line += f"{overall[r][metric]:>8.3f}"
        print(line)

    # ---- 结论（按真实数字生成）----
    conclusions = []
    if summary["semantic"]["vec"]["recall"] > summary["semantic"]["fts"]["recall"]:
        conclusions.append("semantic 类用例上 vec（稠密路）recall 优于 fts（稀疏路），混合对中文语义查询必要")
    if summary["both"]["hybrid"]["mrr"] >= max(summary["both"]["fts"]["mrr"], summary["both"]["vec"]["mrr"]) - 1e-9:
        conclusions.append("both 类用例上 hybrid MRR 不差于任一单路（双路贡献相加的 RRF 生效）")
    if summary["literal"]["fts"]["mrr"] >= summary["literal"]["vec"]["mrr"]:
        conclusions.append("literal 类用例上 fts（稀疏路）字面命中不弱于 vec")
    if overall["hybrid"]["recall"] >= max(overall["fts"]["recall"], overall["vec"]["recall"]):
        conclusions.append("整体 recall@5：hybrid 不低于任一单路（融合去重不误删）")
    conclusion = "结论：" + "；".join(conclusions) + "。"

    # ---- report.md 落盘 ----
    lines = [
        "# M-S3-T05 检索评测基线报告",
        "",
        f"- 语料：{len(CASES['corpus'])} 份主题互不重叠文档（{', '.join(c['filename'] + '/' + c['topic'] for c in CASES['corpus'])}），均 500+ 字",
        f"- 用例：{len(CASES['cases'])} 条（literal/semantic/both 各 2）",
        f"- 检索参数：top_k={TOP_K}，三路为 search_fts / search_vec / search_hybrid（RRF_K=60）",
        "",
        "| 用例类 | 指标 | fts | vec | hybrid |",
        "|---|---|---|---|---|",
    ]
    for mode in ("literal", "semantic", "both"):
        for metric in ("recall", "mrr"):
            lines.append(
                f"| {mode} | {metric}@5 | {summary[mode]['fts'][metric]:.3f} | "
                f"{summary[mode]['vec'][metric]:.3f} | {summary[mode]['hybrid'][metric]:.3f} |"
            )
    for metric in ("recall", "mrr"):
        lines.append(
            f"| overall | {metric}@5 | {overall['fts'][metric]:.3f} | "
            f"{overall['vec'][metric]:.3f} | {overall['hybrid'][metric]:.3f} |"
        )
    lines += ["", conclusion, ""]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[report] 已写入 {REPORT_PATH}")
    print(conclusion)

    # ---- semantic 专项断言：至少一条 vec 命中而 fts 未命中（T02 结论复现）----
    sem_fts0_vec1 = [row for row in rows if row["expect_mode"] == "semantic"
                     and row["vec"][1] == 1.0 and row["fts"][1] == 0.0]
    print(f"\n[semantic 复现] vec 命中而 fts 未命中的用例: {[r['case_id'] for r in sem_fts0_vec1]}")
    assert sem_fts0_vec1, "应有至少一条 semantic 用例 vec 命中而 fts 未命中"

    # ---- 隔离用例：B 区同批 query，recall@5=0 ----
    b_recall = []
    for case in CASES["cases"]:
        for route in ROUTES:
            hits = _search(route, wid_b, case["query"])
            assert all(h["filename"] != case["expect_filename"] for h in hits), \
                f"隔离失败: B 区 {route} 返回了 A 区语料 {case['expect_filename']}"
            b_recall.append(recall_at_5(hits, case["expect_filename"]))
    print(f"[隔离] B 区 {len(CASES['cases']) * 3} 次查询 recall@5 全部为 0: {sum(b_recall) == 0}")
    assert sum(b_recall) == 0

    # ---- 双清理（两阶段）----
    for wid in (wid_a, wid_b):
        for k in storage.list_object_keys(prefix=str(wid)):
            storage.remove_object(k)
    with get_session() as s:
        for wid, u in ((wid_a, uid), (wid_b, uid_b)):
            s.execute(Message.__table__.delete())
            s.execute(Chunk.__table__.delete().where(Chunk.workspace_id == wid))
            s.execute(Document.__table__.update().where(Document.workspace_id == wid)
                      .values(active_version=None))
            s.execute(DocumentVersion.__table__.delete().where(DocumentVersion.document_id.in_(
                select(Document.document_id).where(Document.workspace_id == wid))))
            s.execute(delete(Document).where(Document.workspace_id == wid))
            s.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == wid))
            s.execute(delete(Workspace).where(Workspace.workspace_id == wid))
            s.execute(delete(User).where(User.user_id == u))
    with get_session() as s:
        counts = {t.__tablename__: s.execute(select(func.count()).select_from(t)).scalar_one()
                  for t in (Message, Chunk, DocumentVersion, Document, WorkspaceMember, Workspace, User)}
        print(f"[cleanup] 7 表残留: {counts}")
        assert not any(counts.values()), counts
    objs = storage.list_object_keys(prefix="")
    print(f"[cleanup] MinIO 残留对象: {len(objs)}")
    assert not objs, objs
    print("[cleanup] PASS：双清理完成（独立会话断言）")


if __name__ == "__main__":
    main()
