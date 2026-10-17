# -*- coding: utf-8 -*-
"""app.py 界面测试：问诊单分组标题与知识库缺失提示"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest 的相对路径按调用方文件解析，这里统一用项目根目录绝对路径
APP_FILE = str(Path(__file__).resolve().parents[1] / "app.py")

# spec-004 定义的八个问诊单分组标题
GROUP_TITLES = [
    "基本信息",
    "望诊与切诊",
    "问寒热与汗出",
    "问头身胸腹",
    "问饮食口味",
    "问睡眠情志",
    "问二便与经期",
    "其他伴随症状",
]


def test_form_groups_rendered():
    """用例 39（正常）：问诊单八个分组标题全部渲染，运行无异常"""
    app = AppTest.from_file(APP_FILE, default_timeout=120).run()
    assert not app.exception
    rendered = "\n".join(md.value for md in app.markdown)
    for title in GROUP_TITLES:
        assert title in rendered


def test_header_and_submit_button():
    """用例 40（正常）：页面头部标题与开始诊断按钮存在"""
    app = AppTest.from_file(APP_FILE, default_timeout=120).run()
    assert not app.exception
    rendered = "\n".join(md.value for md in app.markdown)
    assert "中医在线问诊系统" in rendered
    assert app.button
