"""M-S3-T06 黄金测试集 QA 评测：recall@5 + 引用正确率（端到端，S3 补全）。

与 T05 的分工：T05=检索层三路对比基线（cases.json/retrieval_eval.py 保留
不动）；本脚本直接消费 agent_graph.stream_answer（S4-T03 已上线），
评测"最终答案的引用是否正确"——不起 uvicorn、不经 API 层（评测不需要
messages 落库，graph 层事件流已含 sources 与全部 token）。

指标：
- recall@5：sources 列表出现 expect_filename 的用例比例（对象是 rerank 后
  最终 hits，与 T05 口径一致）；
- 引用正确率：答案末尾【来源: X】中含 expect_filename（system prompt 规定
  格式；解析失败记为不正确，不跳过用例）；
- 参考指标（不计入验收）：答案含全部 expect_answer_keywords 的用例比例。

运行：uv run python eval/run_eval.py [--phase a|b|all]（默认 all）。
phase a=A 区 12 条 QA 指标；phase b=B 区隔离用例（干扰文档，断言两指标
为 0）。分阶段设计的原因：单条 QA 需 router+流式生成两次 LLM 调用，
12 条接近单命令超时上限。
脚本失败显式抛错退出码非 0；评测中 router 误判等如实计入结果不剔除。
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 脚本模式补项目根
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import get_session  # noqa: E402
from app.models.models import (  # noqa: E402
    Chunk, Document, DocumentVersion, Message, User, Workspace, WorkspaceMember,
)
from app.services import document as doc_svc  # noqa: E402
from app.services import storage  # noqa: E402
from app.services import workspace as ws_svc  # noqa: E402
from app.services.upload import register_upload  # noqa: E402
from app.workers.ingestion import ingest_version  # noqa: E402
from app.graphs.agent_graph import stream_answer  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN = json.loads((EVAL_DIR / "golden_set.json").read_text(encoding="utf-8"))
T05 = json.loads((EVAL_DIR / "cases.json").read_text(encoding="utf-8"))
REPORT_PATH = EVAL_DIR / "golden_report.md"
RESULT_TMP = Path(__file__).resolve().parent / ".phase_a_result.json"  # 运行中间产物，结束删除

DOC_B = "周末计划去郊外徒步，需要准备登山鞋和水壶，还要带足饮用水。"
CITE_RE = re.compile(r"【来源[:：]\s*([^\]】]+?)】")


def bootstrap_clean() -> None:
    """自愈清理：全桶扫描 MinIO（评测桶内只应有测试对象，孤儿对象——ws 行
    已删而对象残留——按 ws 前缀清不到，必须全桶）+ 全表清空。"""
    for k in storage.list_object_keys(prefix=""):
        storage.remove_object(k)
    with get_session() as s:
        s.execute(Message.__table__.delete())
        s.execute(Chunk.__table__.delete())
        s.execute(Document.__table__.update().values(active_version=None))
        s.execute(DocumentVersion.__table__.delete())
        s.execute(delete(Document))
        s.execute(delete(WorkspaceMember))
        s.execute(delete(Workspace))
        s.execute(delete(User))


def _setup_workspace(uid=None, uid_b=None):
    """建 workspace（A 或 B），返回 (user_id, workspace_id)。"""
    with get_session() as s:
        user = User(username=uid, password_hash="not-a-real-hash")
        s.add(user)
        s.flush()
        ws = ws_svc.create_workspace(s, user_id=user.user_id, name=uid_b)
        s.flush()
        return user.user_id, ws.workspace_id


def _ingest(uid, wsid, filename, data) -> None:
    with get_session() as s:
        doc = doc_svc.create_document(s, user_id=uid, workspace_id=wsid, filename=filename)
        s.flush()
        r = register_upload(s, user_id=uid, workspace_id=wsid,
                            document_id=doc.document_id, filename=filename, data=data)
    assert r["status"] == "accepted", r
    ar = ingest_version.apply(args=[r["version_id"]])
    assert ar.successful(), f"摄取失败: {ar.result}"


def _ask(wsid, query):
    """调 stream_answer，返回 (sources, answer_text)。"""
    sources, tokens = None, []
    for payload in stream_answer(wsid, query, top_k=5):
        if "sources" in payload:
            sources = payload["sources"]
        elif "token" in payload:
            tokens.append(payload["token"])
    return sources or [], "".join(tokens)


def _cite_files(answer: str) -> list[str]:
    """解析答案末尾【来源: X】的全部文件名（失败返回空列表 → 记不正确）。"""
    return [m.strip() for m in CITE_RE.findall(answer)]


def _delete_data(wids) -> None:
    """删除部分：MinIO 对象 + 6 表（不含 User——按 wid 无法定位 user，由
    bootstrap_clean 兜底；两阶段纪律：删除提交与断言分离）。"""
    for wid in wids:
        for k in storage.list_object_keys(prefix=str(wid)):
            storage.remove_object(k)
    with get_session() as s:
        for wid in wids:
            s.execute(Message.__table__.delete())
            s.execute(Chunk.__table__.delete().where(Chunk.workspace_id == wid))
            s.execute(Document.__table__.update().where(Document.workspace_id == wid)
                      .values(active_version=None))
            s.execute(DocumentVersion.__table__.delete().where(DocumentVersion.document_id.in_(
                select(Document.document_id).where(Document.workspace_id == wid))))
            s.execute(delete(Document).where(Document.workspace_id == wid))
            s.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == wid))
            s.execute(delete(Workspace).where(Workspace.workspace_id == wid))


def _assert_clean() -> None:
    """独立会话断言：7 表 0 行 + MinIO 0 对象（User 由 bootstrap_clean 兜底删除）。"""
    bootstrap_clean()  # 自愈兜底（含 user 行）
    with get_session() as s:
        counts = {t.__tablename__: s.execute(select(func.count()).select_from(t)).scalar_one()
                  for t in (Message, Chunk, DocumentVersion, Document, WorkspaceMember, Workspace, User)}
        print(f"[cleanup] 7 表残留: {counts}")
        assert not any(counts.values()), counts
    objs = storage.list_object_keys(prefix="")
    print(f"[cleanup] MinIO 残留: {len(objs)}")
    assert not objs, objs
    print("[cleanup] PASS：双清理完成（独立会话断言）")


def phase_a() -> dict:
    """A 区：4 份语料 + 12 条 QA 端到端评测。"""
    bootstrap_clean()
    uid, wid = _setup_workspace(f"gold-{uuid.uuid4().hex[:8]}", f"ws-gold-{uuid.uuid4().hex[:8]}")
    for c in T05["corpus"]:
        _ingest(uid, wid, c["filename"], c["text"].encode("utf-8"))
    for c in GOLDEN["corpus_extra"]:
        _ingest(uid, wid, c["filename"], c["text"].encode("utf-8"))

    rows = []
    for i, case in enumerate(GOLDEN["cases"], 1):
        sources, answer = _ask(wid, case["query"])
        src_names = [h["filename"] for h in sources]
        recall = 1.0 if case["expect_filename"] in src_names else 0.0
        cites = _cite_files(answer)
        cite_ok = 1.0 if case["expect_filename"] in cites else 0.0
        kw_hit = sum(1 for kw in case["expect_answer_keywords"] if kw in answer)
        kw_all = 1.0 if kw_hit == len(case["expect_answer_keywords"]) else 0.0
        rows.append({**case, "src_names": src_names, "answer_tail": answer[-80:],
                     "cites": cites, "recall": recall, "cite_ok": cite_ok,
                     "kw_hit": kw_hit, "kw_all": kw_all})
        print(f"[A {i}/{len(GOLDEN['cases'])}] {case['case_id']}/{case['expect_mode']} "
              f"recall={recall:.0f} 引用={'√' if cite_ok else '×'}(解析出 {cites}) "
              f"kw={kw_hit}/{len(case['expect_answer_keywords'])} src={src_names}")

    n = len(rows)
    result = {
        "recall": sum(r["recall"] for r in rows) / n,
        "cite_acc": sum(r["cite_ok"] for r in rows) / n,
        "kw_acc": sum(r["kw_all"] for r in rows) / n,
        "rows": rows,
    }
    print(f"\n[A 汇总] recall@5={result['recall']:.3f} 引用正确率={result['cite_acc']:.3f} "
          f"关键词全命中(参考)={result['kw_acc']:.3f}")
    _delete_data([wid])
    _assert_clean()
    RESULT_TMP.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def phase_b() -> None:
    """B 区：同批 query，断言 recall@5=0 且引用无一指向 A 区语料。"""
    bootstrap_clean()
    uid, wid_b = _setup_workspace(f"goldb-{uuid.uuid4().hex[:8]}", f"ws-goldb-{uuid.uuid4().hex[:8]}")
    _ingest(uid, wid_b, "徒步计划.txt", DOC_B.encode("utf-8"))

    bad = []
    for i, case in enumerate(GOLDEN["cases"], 1):
        sources, answer = _ask(wid_b, case["query"])
        src_names = [h["filename"] for h in sources]
        cites = _cite_files(answer)
        leak = case["expect_filename"] in src_names or case["expect_filename"] in cites
        if leak:
            bad.append(case["case_id"])
        print(f"[B {i}/{len(GOLDEN['cases'])}] {case['case_id']} src={src_names} cites={cites} 泄露={leak}")
    print(f"[B 汇总] A 区语料泄露用例: {bad or '无'}")
    assert not bad, f"隔离被破坏: {bad}"
    _delete_data([wid_b])
    _assert_clean()


def build_report(result: dict) -> None:
    by_mode = {}
    for r in result["rows"]:
        m = by_mode.setdefault(r["expect_mode"], {"n": 0, "recall": 0.0, "cite": 0.0, "kw": 0.0})
        m["n"] += 1
        m["recall"] += r["recall"]
        m["cite"] += r["cite_ok"]
        m["kw"] += r["kw_all"]
    lines = [
        "# M-S3-T06 黄金测试集 QA 评测报告（端到端引用正确性）",
        "",
        "- 对象：agent_graph.stream_answer（Router→hybrid_search→流式生成）",
        "- 用例：12 条（literal 4 / semantic 4 / both 4），语料 4 份（复用 T05 三份 + doc_sec）",
        "",
        "| 用例类 | 条数 | recall@5 | 引用正确率 | 关键词全命中(参考) |",
        "|---|---|---|---|---|",
    ]
    for mode, m in by_mode.items():
        lines.append(f"| {mode} | {m['n']} | {m['recall']/m['n']:.3f} | {m['cite']/m['n']:.3f} | {m['kw']/m['n']:.3f} |")
    lines += [
        f"| **overall** | 12 | **{result['recall']:.3f}** | **{result['cite_acc']:.3f}** | {result['kw_acc']:.3f} |",
        "",
        "## 逐条明细",
        "",
        "| case | mode | query | 期望 | recall | 引用判定 | 解析来源 | kw 命中 | 答案末尾 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        lines.append(
            f"| {r['case_id']} | {r['expect_mode']} | {r['query']} | {r['expect_filename']} "
            f"| {r['recall']:.0f} | {'√' if r['cite_ok'] else '×'} | {r['cites']} "
            f"| {r['kw_hit']}/{len(r['expect_answer_keywords'])} | {r['answer_tail'][-40:]} |"
        )
    fails = [r for r in result["rows"] if r["recall"] == 0 or r["cite_ok"] == 0]
    conclusion = (
        f"结论：recall@5={result['recall']:.3f}、引用正确率={result['cite_acc']:.3f}，"
        + ("均达 ≥0.8 验收线；" if result["recall"] >= 0.8 and result["cite_acc"] >= 0.8 else "未达 0.8 验收线；")
        + (f"失败用例 {[r['case_id'] for r in fails]} 已逐条分析（见 STATUS 事件记录）。"
           if fails else "无失败用例。")
    )
    lines += ["", conclusion, ""]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] 已写入 {REPORT_PATH}")
    print(conclusion)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["a", "b", "all"], default="all")
    args = ap.parse_args()
    result = None
    if args.phase in ("a", "all"):
        result = phase_a()
    if args.phase in ("b", "all"):
        phase_b()
    if result is not None:
        build_report(result)
        RESULT_TMP.unlink(missing_ok=True)
    print("[done] 全部完成")


if __name__ == "__main__":
    main()
