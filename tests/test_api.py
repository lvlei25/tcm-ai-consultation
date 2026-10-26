# -*- coding: utf-8 -*-
"""api.py 测试：健康检查、主诉校验、SSE 事件流顺序与结构（mock LLM 与检索）"""
import json

import pytest
from fastapi.testclient import TestClient

import api as api_module
from api import app

client = TestClient(app)

# 与 spec-005 样例一致的完整问诊单
FORM = {
    "姓名": "张三", "性别": "女", "年龄": 30, "病程": "1月内",
    "望诊": {"面色": "萎黄", "舌质": "淡", "舌苔": "薄白"}, "脉象": "细弱",
    "寒热": "畏寒怕冷", "汗出": "自汗", "头身胸腹不适": ["头晕", "心悸"],
    "饮食": "食欲不振", "口渴": "口不渴", "口味": "淡",
    "睡眠": "入睡困难", "情志": "思虑过度",
    "大便": "溏薄", "小便": "清长", "经期": "量少色淡",
    "主诉": "反复入睡困难、多梦易醒一月，伴神疲乏力、心悸头晕", "既往史": "",
    "其他伴随症状": [],
}

SECTION_TITLES = ["辨证分析", "证型诊断", "治法", "推荐方药与加减", "调护建议", "引用医案依据"]


def _parse_sse(body: str) -> list[dict]:
    """把 SSE 文本解析为事件列表"""
    events = []
    for frame in body.split("\n\n"):
        for line in frame.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


@pytest.fixture()
def mocked_pipeline(monkeypatch):
    """替换 LLM 调用与知识库检索为固定桩，不发真实请求"""
    evidences = [
        {"text": "心脾两虚用归脾汤。", "metadata": {"source": "a.md", "章": "不寐"},
         "score": 0.9, "vec_score": 0.9, "bm25_score": 0.0},
        {"text": "心肾不交用黄连阿胶汤。", "metadata": {"source": "b.md", "节": "医案二"},
         "score": 0.5, "vec_score": 0.0, "bm25_score": 0.5},
    ]
    monkeypatch.setattr(api_module, "generate_query", lambda form: "不寐 心脾两虚")
    monkeypatch.setattr(api_module, "_build_retriever", lambda: type(
        "FakeRetriever", (), {"retrieve": lambda self, query, top_k=6: evidences}
    )())
    diagnosis_text = "".join(f"## {title}\n{title}内容。\n" for title in SECTION_TITLES)
    monkeypatch.setattr(api_module, "stream_diagnosis", lambda form, evs: iter([diagnosis_text]))
    return evidences


def test_health():
    """用例 58（正常）：健康检查返回状态与检索后端类型"""
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["retriever"] in ("local", "mcp")


def test_stream_missing_chief_yields_error_only():
    """用例 59（异常）：主诉缺失时只返回 error 事件，不进入后续步骤"""
    response = client.post("/api/diagnose/stream", json={})
    events = _parse_sse(response.text)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "主诉" in events[0]["message"]


def test_stream_event_order_and_sections(mocked_pipeline):
    """用例 60（正常）：SSE 事件按 query → evidences → chunk → sections → done 顺序，
    证据明细与六小节结构完整"""
    response = client.post("/api/diagnose/stream", json=FORM)
    events = _parse_sse(response.text)
    types = [event["type"] for event in events]
    assert types[0] == "query" and types[1] == "evidences"
    assert "chunk" in types and types[-1] == "done"

    query_event = events[0]
    assert query_event["query"] == "不寐 心脾两虚"

    evidence_event = events[1]
    assert len(evidence_event["items"]) == 2
    assert evidence_event["items"][0]["metadata"]["source"] == "a.md"

    full_text = "".join(event["text"] for event in events if event["type"] == "chunk")
    sections_event = next(event for event in events if event["type"] == "sections")
    assert list(sections_event["sections"].keys()) == SECTION_TITLES
    assert "辨证分析内容" in full_text
    # 证据文本只出现在 evidences 事件，不混入诊断正文
    assert "归脾汤" in json.dumps(evidence_event, ensure_ascii=False)


def test_stream_retriever_error_surfaces(mocked_pipeline, monkeypatch):
    """用例 61（异常）：检索后端初始化失败时返回 error 事件且无后续步骤"""
    monkeypatch.setattr(
        api_module,
        "_build_retriever",
        lambda: (_ for _ in ()).throw(RuntimeError("知识库尚未构建，请先运行：python scripts/build_kb.py")),
    )
    response = client.post("/api/diagnose/stream", json=FORM)
    events = _parse_sse(response.text)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "build_kb" in events[0]["message"]
