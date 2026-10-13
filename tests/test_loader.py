# -*- coding: utf-8 -*-
"""kb.loader 模块测试：医案加载与分块"""
import pytest

from kb.loader import load_case_documents, split_documents

# 含两级标题的医案样例
SAMPLE_MD = (
    "# 第一章 不寐\n\n"
    "不寐多因情志失调。\n\n"
    "## 医案一\n\n"
    "患者反复入睡困难，多梦易醒，心脾两虚，方用归脾汤。\n\n"
    "## 医案二\n\n"
    "患者心肾不交，方用黄连阿胶汤。"
)


def test_load_headers_split_metadata(tmp_path):
    """用例 7（正常）：按标题切分出多个片段，元数据包含章/节/source"""
    (tmp_path / "医案集.md").write_text(SAMPLE_MD, encoding="utf-8")
    docs = load_case_documents(tmp_path)
    assert len(docs) >= 3
    assert any(d.metadata.get("节") == "医案一" for d in docs)
    assert any(d.metadata.get("章") == "第一章 不寐" for d in docs)
    assert all(d.metadata["source"] == "医案集.md" for d in docs)


def test_load_no_headers_single_doc(tmp_path):
    """用例 8（边界）：无任何标题的 MD 文件整体作为单个片段"""
    (tmp_path / "朴素医案.md").write_text("患者胃痛，温中散寒，方用理中汤。", encoding="utf-8")
    docs = load_case_documents(tmp_path)
    assert len(docs) == 1
    assert "理中汤" in docs[0].page_content
    assert docs[0].metadata["source"] == "朴素医案.md"


def test_load_empty_dir_raises(tmp_path):
    """用例 9（异常）：目录中没有 .md 文件时抛出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        load_case_documents(tmp_path)


def test_load_ignores_non_md(tmp_path):
    """用例 10（正常）：目录中的非 .md 文件被忽略"""
    (tmp_path / "医案.md").write_text("# 医案\n\n内容。", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("不是医案", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    docs = load_case_documents(tmp_path)
    assert all(d.metadata["source"] == "医案.md" for d in docs)


def test_load_bom_file_readable(tmp_path):
    """用例 11（边界）：带 BOM 的 UTF-8 文件可正常读取，不产生乱码字符"""
    (tmp_path / "bom医案.md").write_text("# 医案\n\n内容。", encoding="utf-8-sig")
    docs = load_case_documents(tmp_path)
    assert all("\ufeff" not in d.page_content for d in docs)


def test_split_long_section_chunks(tmp_path):
    """用例 12（边界）：超长段落被切分为多个片段，且单块不超过 CHUNK_SIZE"""
    from config import CHUNK_SIZE

    long_text = "中医辨证论治讲究整体观念。" * 60
    (tmp_path / "长文医案.md").write_text(f"# 医案\n\n{long_text}", encoding="utf-8")
    docs = split_documents(load_case_documents(tmp_path))
    assert len(docs) >= 2
    assert all(len(d.page_content) <= CHUNK_SIZE for d in docs)


def test_split_preserves_metadata(tmp_path):
    """用例 13（正常）：二次切分后片段保留标题层级与来源元数据"""
    long_text = "患者脾胃虚弱，运化失常，治以健脾益气。" * 40
    (tmp_path / "脾系医案.md").write_text(f"# 第二章 脾胃\n\n{long_text}", encoding="utf-8")
    docs = split_documents(load_case_documents(tmp_path))
    assert all(d.metadata.get("章") == "第二章 脾胃" for d in docs)
    assert all(d.metadata["source"] == "脾系医案.md" for d in docs)
