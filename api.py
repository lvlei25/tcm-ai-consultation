# -*- coding: utf-8 -*-
"""FastAPI 接口层：复用 kb/pipeline 现有逻辑，为 Vue 前端提供 SSE 诊断流

启动：python -m uvicorn api:app --host 127.0.0.1 --port 8000
（MCP 模式占用 8000 时改用 --port 8010 并同步修改 frontend/vite.config.js）
"""
import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import MCP_ENABLED, TOP_K
from kb.builder import load_knowledge_base
from kb.mcp_retriever import McpRetriever
from kb.retriever import HybridRetriever
from pipeline.diagnoser import parse_diagnosis_sections, stream_diagnosis
from pipeline.form_query import generate_query, validate_form

app = FastAPI(title="中医在线问诊系统 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_retriever():
    """按 config 开关构造检索后端（与 app.py 同一逻辑）"""
    if MCP_ENABLED:
        return McpRetriever()
    faiss_store, chunks, bm25 = load_knowledge_base()
    return HybridRetriever(faiss_store, chunks, bm25)


@app.get("/api/health")
def health() -> dict:
    """健康检查，返回当前检索后端类型"""
    return {"status": "ok", "retriever": "mcp" if MCP_ENABLED else "local"}


def _sse(event: dict) -> str:
    """把事件字典编码为 SSE 数据帧"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _diagnose_stream(form: dict) -> Iterator[str]:
    """三步诊断的 SSE 事件流：检索语句 → 混合检索 → 流式诊断 + 结构化小节"""
    errors = validate_form(form)
    if errors:
        yield _sse({"type": "error", "message": "；".join(errors)})
        return
    try:
        retriever = _build_retriever()
    except (FileNotFoundError, RuntimeError) as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    try:
        query = generate_query(form)
        yield _sse({"type": "query", "query": query})
        evidences = retriever.retrieve(query, top_k=TOP_K)
        yield _sse({"type": "evidences", "items": evidences})
        text = ""
        for piece in stream_diagnosis(form, evidences):
            text += piece
            yield _sse({"type": "chunk", "text": piece})
        sections = parse_diagnosis_sections(text)
        yield _sse({"type": "sections", "sections": sections})
        yield _sse({"type": "done"})
    except Exception as exc:  # noqa: BLE001 - 错误统一以 error 事件透出
        yield _sse({"type": "error", "message": str(exc)})


@app.post("/api/diagnose/stream")
def diagnose_stream(form: dict) -> StreamingResponse:
    """接收问诊单 JSON，返回三步诊断的 SSE 事件流"""
    return StreamingResponse(
        _diagnose_stream(form),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
