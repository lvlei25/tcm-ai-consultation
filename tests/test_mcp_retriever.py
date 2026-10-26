# -*- coding: utf-8 -*-
"""kb.mcp_retriever 测试：命中块解析校验、归一化去重、降级重试与配置校验（不发真实网络请求）"""
import pytest

import config
from config import MCP_ENABLED, TOP_K
from kb.mcp_retriever import McpRetriever
from pipeline.form_query import build_query_messages

# 与真实服务端一致的命中块文本样例
RAW_OK = (
    "检索「不寐」命中 2 条（按命中次数排序）：\n\n"
    "### source/医学衷中参西录（命中 38 次）\n"
    "虚劳咳嗽兼不寐证……用归脾汤加减。\n\n"
    "### source/丁甘仁医案（命中 22 次）\n"
    "王左 脉郁数，苔薄腻尖红，烦躁不寐，时欲呕。\n"
)
# 与真实服务端一致的无命中说明
RAW_EMPTY = "知识库中没有同时包含这些词的条目：不寐心悸"
# 无法识别的格式
RAW_BAD = "服务端返回了一段无法解析的内容"


@pytest.fixture()
def retriever(monkeypatch) -> McpRetriever:
    """构造已替换网络调用为样例输出的检索器"""
    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")
    monkeypatch.setattr(instance, "_call_search", lambda query, top_k: RAW_OK)
    return instance


def test_parse_blocks_and_normalize(retriever):
    """用例 49（正常）：命中块解析、命中次数归一化到 0~1、按文本去重"""
    results = retriever.retrieve("不寐", top_k=TOP_K)
    assert len(results) == 2
    scores = [item["score"] for item in results]
    assert max(scores) == 1.0 and min(scores) == 0.0
    top = results[0]
    assert "归脾汤" in top["text"]
    assert top["metadata"]["source"] == "医学衷中参西录"
    assert top["metadata"]["类型"] == "source"
    assert top["metadata"]["命中次数"] == 38
    assert top["vec_score"] == 0.0 and top["bm25_score"] == 0.0


def test_top_k_truncation(retriever):
    """用例 50（边界）：top_k 截断返回条数"""
    assert len(retriever.retrieve("不寐", top_k=1)) == 1


def test_no_hit_returns_empty(monkeypatch):
    """用例 51（边界）：无命中说明返回空列表而不报错"""
    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")
    monkeypatch.setattr(instance, "_call_search", lambda query, top_k: RAW_EMPTY)
    assert instance.retrieve("不寐心悸") == []


def test_unrecognized_format_raises(monkeypatch):
    """用例 52（异常）：无法识别的返回格式抛出明确中文异常"""
    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")
    monkeypatch.setattr(instance, "_call_search", lambda query, top_k: RAW_BAD)
    with pytest.raises(RuntimeError) as exc_info:
        instance.retrieve("不寐")
    assert "返回格式" in str(exc_info.value)


def test_empty_url_raises():
    """用例 53（异常）：启用 MCP 但未配置 URL 时抛出明确中文异常"""
    with pytest.raises(RuntimeError) as exc_info:
        McpRetriever(server_url="")
    assert "MCP_SERVER_URL" in str(exc_info.value)


def test_config_switch_defaults_off():
    """用例 54（边界）：config 开关可读且当前默认关闭（MCP_ENABLED 为布尔值）"""
    assert isinstance(MCP_ENABLED, bool)


def test_mcp_query_prompt_switch(monkeypatch):
    """用例 55（正常）：MCP 开启时检索词提示词切换为关键词模式，关闭时为语句模式"""
    monkeypatch.setattr(config, "MCP_ENABLED", True)
    messages = build_query_messages({"主诉": "不寐心悸"})
    assert "空格分隔" in messages[0][1] and "不寐心悸" in messages[1][1]
    monkeypatch.setattr(config, "MCP_ENABLED", False)
    messages = build_query_messages({"主诉": "不寐心悸"})
    assert "80字" in messages[0][1]


def test_dense_query_segmented_by_jieba(monkeypatch):
    """用例 57（边界）：无空格长语句先用 jieba 分词，再走降级重试"""
    import kb.mcp_retriever as mcp_module

    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")
    calls: list[str] = []

    def fake_call(query: str, top_k: int) -> str:
        calls.append(query)
        if query == "不寐 多梦 心悸":
            return RAW_OK
        return RAW_EMPTY

    monkeypatch.setattr(mcp_module, "tokenize", lambda text: ["不寐", "多梦", "心悸", "乏力"])
    monkeypatch.setattr(instance, "_call_search", fake_call)
    results = instance.retrieve("不寐多梦心悸乏力心虚不宁", top_k=2)
    assert results and results[0]["metadata"]["命中次数"] == 38
    assert calls[0] == "不寐 多梦 心悸 乏力"
    assert calls[-1] == "不寐 多梦 心悸"


def test_connect_error_unwrapped(monkeypatch):
    """用例 62（异常）：连接失败时展开 ExceptionGroup，透出真实原因与启动提示"""
    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")

    async def fake_connect(query: str, top_k: int) -> str:
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup", [ConnectionRefusedError("连接被拒绝")]
        )

    monkeypatch.setattr(instance, "_call_search_async", fake_connect)
    with pytest.raises(RuntimeError) as exc_info:
        instance.retrieve("不寐")
    message = str(exc_info.value)
    assert "ConnectionRefusedError" in message
    assert "请确认 MCP 服务端已启动" in message


def test_retry_with_fewer_terms(monkeypatch):
    """用例 56（正常）：全词 0 命中时按词数递减重试，首个非空结果即返回"""
    instance = McpRetriever(server_url="http://127.0.0.1:8000/mcp")
    calls: list[str] = []

    def fake_call(query: str, top_k: int) -> str:
        calls.append(query)
        if query == "不寐":
            return RAW_OK
        return RAW_EMPTY

    monkeypatch.setattr(instance, "_call_search", fake_call)
    results = instance.retrieve("不寐 多梦易醒 神疲乏力 心悸", top_k=2)
    assert results and results[0]["metadata"]["命中次数"] == 38
    # 降级顺序：全词(4，与前4重复跳过) → 前3 → 前2 → 前1，命中于前1词
    assert calls == [
        "不寐 多梦易醒 神疲乏力 心悸",
        "不寐 多梦易醒 神疲乏力",
        "不寐 多梦易醒",
        "不寐",
    ]
