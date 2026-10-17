# -*- coding: utf-8 -*-
"""pipeline 模块测试：问诊单校验、检索词消息构造与诊断消息构造"""
import pytest

from pipeline.diagnoser import (
    SECTION_TITLES,
    build_diagnosis_messages,
    format_evidences,
    parse_diagnosis_sections,
)
from pipeline.form_query import (
    MAX_QUERY_LEN,
    build_query_messages,
    check_query_length,
    validate_form,
)
from config import EVIDENCE_SNIPPET_LEN

# 标准问诊单样例
FORM = {
    "姓名": "张三",
    "年龄": 30,
    "性别": "女",
    "病程": "1周内",
    "舌象": "舌质淡红 苔薄白 润",
    "寒热": "怕冷",
    "主诉": "反复入睡困难，多梦易醒",
    "既往史": "",
    "睡眠": "入睡困难",
    "饮食": "正常",
    "大便": "正常",
    "小便": "正常",
    "伴随症状": ["乏力", "头晕"],
}


def test_validate_form_pass():
    """用例 24（正常）：主诉齐全的问诊单校验通过"""
    assert validate_form(FORM) == []


def test_validate_form_missing_chief():
    """用例 25（异常）：主诉缺失、为空或纯空格时均返回错误"""
    for bad in ({}, {"主诉": ""}, {"主诉": "   "}):
        errors = validate_form(bad)
        assert len(errors) == 1
        assert "主诉" in errors[0]


def test_build_query_messages_structure():
    """用例 26（正常）：检索词消息包含 system 与 user 两条，user 含主诉原文"""
    messages = build_query_messages(FORM)
    assert len(messages) == 2
    assert messages[0][0] == "system" and messages[1][0] == "user"
    assert "反复入睡困难" in messages[1][1]
    assert "问诊单信息" in messages[1][1]


def test_build_query_messages_symptoms():
    """用例 27（正常）：伴随症状列表被序列化进 user 消息"""
    messages = build_query_messages(FORM)
    assert "乏力" in messages[1][1] and "头晕" in messages[1][1]


def test_build_query_messages_chinese_readable():
    """用例 28（边界）：中文以非转义形式序列化，无乱码"""
    messages = build_query_messages({"主诉": "胃脘胀痛"})
    assert "胃脘胀痛" in messages[1][1]
    assert "\\u" not in messages[1][1]


def test_format_evidences_numbering_and_source():
    """用例 29（正常）：证据按 [1][2] 编号并包含出处文件名与标题层级"""
    evidences = [
        {"text": "心脾两虚用归脾汤。", "metadata": {"source": "a.md", "章": "不寐"}},
        {"text": "心肾不交用黄连阿胶汤。", "metadata": {"source": "b.md", "节": "医案二"}},
    ]
    block = format_evidences(evidences)
    assert "[1] 出处：a.md 不寐" in block
    assert "[2] 出处：b.md 医案二" in block
    assert "归脾汤" in block


def test_format_evidences_empty():
    """用例 30（边界）：证据列表为空时输出占位说明"""
    assert format_evidences([]) == "（未检索到相关医案证据）"


def test_build_diagnosis_messages_structure():
    """用例 31（正常）：诊断消息包含 system 角色设定、问诊单与证据块"""
    evidences = [{"text": "归脾汤主之。", "metadata": {"source": "a.md"}}]
    messages = build_diagnosis_messages(FORM, evidences)
    assert len(messages) == 2
    assert messages[0][0] == "system" and messages[1][0] == "user"
    assert "名老中医" in messages[0][1]
    assert "【问诊单】" in messages[1][1]
    assert "【医案证据】" in messages[1][1]
    assert "[1]" in messages[1][1]


def test_parse_diagnosis_sections_full():
    """用例 45（正常）：完整六小节文本解析出六个键且顺序与小节常量一致"""
    text = "".join(f"## {title}\n{title}的内容。\n" for title in SECTION_TITLES)
    sections = parse_diagnosis_sections(text)
    assert list(sections.keys()) == SECTION_TITLES
    assert sections["治法"] == "治法的内容。"


def test_parse_diagnosis_sections_missing_raises():
    """用例 46（异常）：缺少任一小节时抛出明确中文异常"""
    text = "".join(f"## {title}\n内容。\n" for title in SECTION_TITLES[:-1])
    with pytest.raises(ValueError) as exc_info:
        parse_diagnosis_sections(text)
    assert SECTION_TITLES[-1] in str(exc_info.value)


def test_check_query_length_boundary():
    """用例 47（边界）：80 字通过、81 字抛错"""
    ok = "字" * MAX_QUERY_LEN
    assert check_query_length(ok) == ok
    with pytest.raises(ValueError):
        check_query_length("字" * (MAX_QUERY_LEN + 1))


def test_format_evidences_truncates_long_text():
    """用例 48（边界）：超过 EVIDENCE_SNIPPET_LEN 的证据被截断并标注，短证据不变"""
    long_text = "医" * (EVIDENCE_SNIPPET_LEN + 50)
    block = format_evidences([{"text": long_text, "metadata": {"source": "a.md"}}])
    assert "医" * EVIDENCE_SNIPPET_LEN in block
    assert ("医" * (EVIDENCE_SNIPPET_LEN + 50)) not in block
    assert "（原文过长已截断）" in block
    short_block = format_evidences(
        [{"text": "归脾汤主之。", "metadata": {"source": "a.md"}}]
    )
    assert "（原文过长已截断）" not in short_block
