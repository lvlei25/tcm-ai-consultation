# -*- coding: utf-8 -*-
"""集成测试：真实调用 DashScope 与已构建知识库，默认不执行

运行方式：python -m pytest tests/ -m integration -q
前置条件：.env 已配置 DASHSCOPE_API_KEY 且已执行 python scripts/build_kb.py
"""
import re

import pytest

from config import TOP_K
from kb.builder import load_knowledge_base
from kb.retriever import HybridRetriever
from pipeline.diagnoser import stream_diagnosis
from pipeline.form_query import generate_query

pytestmark = pytest.mark.integration

# 与 spec-005 记录一致的样例问诊单
FORM = {
    "基本信息": {"姓名": "张三", "性别": "女", "年龄": 30, "病程": "1月内"},
    "望诊与切诊": {"面色": "萎黄", "舌质": "淡", "舌苔": "薄白", "脉象": "细弱"},
    "问寒热与汗出": {"寒热": "怕冷", "汗出": "自汗"},
    "问头身胸腹": {"不适": ["头晕", "心悸"]},
    "问饮食口味": {"饮食": "食欲不振", "口渴": "口不渴", "口味": "淡"},
    "问睡眠情志": {"睡眠": "入睡困难", "情志": "思虑过度"},
    "问二便与经期": {"大便": "溏薄", "小便": "清长", "经期": "量少色淡"},
    "主诉": "反复入睡困难、多梦易醒一月，伴神疲乏力、心悸头晕",
    "既往史": "",
}

SECTION_TITLES = [
    "辨证分析",
    "证型诊断",
    "治法",
    "推荐方药与加减",
    "调护建议",
    "引用医案依据",
]


@pytest.fixture(scope="module")
def retriever():
    """加载真实知识库产物，未构建时跳过集成用例"""
    try:
        store, chunks, bm25 = load_knowledge_base()
    except FileNotFoundError as exc:
        pytest.skip(f"集成用例需先构建知识库：{exc}")
    return HybridRetriever(store, chunks, bm25)


def test_generate_query_within_limit():
    """用例 42（集成）：真实生成检索语句，非空且不超过 80 字"""
    query = generate_query(FORM)
    assert query
    assert len(query) <= 80


def test_retrieve_returns_scored_evidence(retriever):
    """用例 43（集成）：真实混合检索返回不超过 TOP_K 条带得分证据"""
    query = generate_query(FORM)
    evidences = retriever.retrieve(query)
    assert 1 <= len(evidences) <= TOP_K
    for item in evidences:
        assert 0.0 <= item["score"] <= 1.0
        assert item["text"]


def test_stream_diagnosis_sections(retriever):
    """用例 44（集成）：真实流式诊断输出包含六个小节标题"""
    query = generate_query(FORM)
    text = "".join(stream_diagnosis(FORM, retriever.retrieve(query)))
    titles = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    for title in SECTION_TITLES:
        assert title in titles
