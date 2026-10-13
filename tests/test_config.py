# -*- coding: utf-8 -*-
"""config 模块测试：.env 解析与 API Key 读取"""
import os

import pytest

from config import get_api_key, load_env


def test_load_env_parses_key_value(tmp_path):
    """用例 1（正常）：.env 中的 KEY=VALUE 被正确解析并写入环境变量"""
    env_file = tmp_path / ".env"
    env_file.write_text("DASHSCOPE_API_KEY=sk-test-123\n", encoding="utf-8")
    load_env(env_file)
    assert os.environ["DASHSCOPE_API_KEY"] == "sk-test-123"


def test_load_env_ignores_comments_and_blank(tmp_path):
    """用例 2（正常）：空行与 # 注释行被忽略，不影响解析"""
    env_file = tmp_path / ".env"
    content = "# 这是注释\n\nLLM_MODEL=qwen-max\n   \n"
    env_file.write_text(content, encoding="utf-8")
    load_env(env_file)
    assert os.environ["LLM_MODEL"] == "qwen-max"


def test_load_env_missing_file_silent(tmp_path):
    """用例 3（边界）：.env 文件不存在时不抛异常"""
    load_env(tmp_path / "not_exists.env")


def test_get_api_key_missing_raises(monkeypatch):
    """用例 4（异常）：缺少 DASHSCOPE_API_KEY 时抛出 RuntimeError"""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_api_key()


def test_get_api_key_present(monkeypatch):
    """用例 5（正常）：存在 DASHSCOPE_API_KEY 时返回该值"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-ok")
    assert get_api_key() == "sk-ok"


def test_get_api_key_blank_raises(monkeypatch):
    """用例 6（边界）：DASHSCOPE_API_KEY 为纯空格时同样抛出 RuntimeError"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "   ")
    with pytest.raises(RuntimeError):
        get_api_key()
