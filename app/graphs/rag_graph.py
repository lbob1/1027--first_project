"""LangGraph RAG 问答链路（M-S3-T04）。

- StateGraph：retrieve（search_hybrid → rerank 精排）→ generate（CHAT_MODEL
  compatible-mode 流式生成，复用 embedding.py 的懒创建 openai client）；
- 图在**模块级编译为常量 graph**（不每次请求重建）；
- 节点内经 langgraph custom writer 发事件：retrieve 发 {"sources": [...]}，
  generate 逐 token 发 {"token": ...}；
- stream_answer(workspace_id, question, top_k)：对外生成器——先产出
  sources 溯源事件（六字段 + rrf_score + relevance_score），再逐 token
  产出文本；不产出 done（由 SSE 层负责收尾）；
- system prompt 要求仅依据资料回答并注明来源文件名；context 由 hits 的
  content 拼接（附 filename/version_no 标号）；
- 向量/查询/文档内容/凭据不入日志（细则 9）；检索与精排的日志由各自模块记。

模块导入零网络请求（client 懒创建；graph 编译是纯内存操作）。
"""

import logging
import uuid
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END

from app.core.config import get_settings
from app.core.context import RAG_SYSTEM_PROMPT as _SYSTEM_PROMPT  # 单一来源：权威在 context.py（M-S4-T01）
from app.core.context import build_evidence_block as _build_context  # 同上，转发保持内部引用点不变
from app.core.db import get_session
from app.services.embedding import _get_client
from app.services.rerank import rerank_documents
from app.services.retrieval_hybrid import search_hybrid

log = logging.getLogger("app.graphs.rag_graph")


class RagState(TypedDict):
    question: str
    workspace_id: uuid.UUID
    top_k: int
    hits: list[dict[str, Any]]
    answer: str


def _retrieve(state: RagState) -> dict:
    writer = get_stream_writer()
    with get_session() as session:
        hits = search_hybrid(
            session,
            workspace_id=state["workspace_id"],
            query=state["question"],
            top_k=state["top_k"],
        )
    reranked = rerank_documents(state["question"], hits, top_n=state["top_k"])
    writer({"sources": reranked})  # 先流出溯源事件
    return {"hits": reranked}


def _generate(state: RagState) -> dict:
    writer = get_stream_writer()
    client = _get_client()
    stream = client.chat.completions.create(
        model=get_settings().CHAT_MODEL,
        stream=True,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"资料如下：\n{_build_context(state['hits'])}\n\n问题：{state['question']}",
            },
        ],
    )
    parts: list[str] = []
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            tok = chunk.choices[0].delta.content
            parts.append(tok)
            writer({"token": tok})
    return {"answer": "".join(parts)}


def _build_graph():
    g = StateGraph(RagState)
    g.add_node("retrieve", _retrieve)
    g.add_node("generate", _generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


graph = _build_graph()  # 模块级常量，不每次请求重建


def stream_answer(
    workspace_id: uuid.UUID, question: str, top_k: int = 5
):
    """RAG 问答流：产出 {'sources': [...]} 后逐个产出 {'token': ...}。"""
    yield from graph.stream(
        {"question": question, "workspace_id": workspace_id, "top_k": top_k,
         "hits": [], "answer": ""},
        stream_mode="custom",
    )
