# -*- coding: utf-8 -*-
"""pipeline 模块测试：问诊单校验、检索词消息构造与诊断消息构造"""
from pipeline.diagnoser import build_diagnosis_messages, format_evidences
from pipeline.form_query import build_query_messages, validate_form

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
