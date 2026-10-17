# -*- coding: utf-8 -*-
"""医案文档加载与分块：扫描 MD 医案，按标题层级切分并控制块长"""
from pathlib import Path

import jieba
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from config import CHUNK_OVERLAP, CHUNK_SIZE, MEDICAL_CASES_DIR

# 按 一级/二级/三级标题 切分，元数据键分别为 章/节/条
_HEADERS_TO_SPLIT_ON = [("#", "章"), ("##", "节"), ("###", "条")]


def tokenize(text: str) -> list[str]:
    """统一分词入口，构建侧与检索侧共用"""
    return jieba.lcut(text)


def load_case_documents(cases_dir: Path = MEDICAL_CASES_DIR) -> list[Document]:
    """扫描目录下所有 .md 医案，按 Markdown 标题切分为 Document 列表

    每个 Document 的 metadata 包含：source（文件名）、章、节、条（按实际标题层级）
    目录中无 .md 文件时抛出 FileNotFoundError
    """
    md_files = sorted(cases_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"医案目录 {cases_dir} 中没有找到 .md 文件，请先放入医案")
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    documents: list[Document] = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8-sig")
        for doc in header_splitter.split_text(text):
            doc.metadata["source"] = md_file.name
            documents.append(doc)
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """对超长片段按字符数二次切分，保留原有元数据"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    return text_splitter.split_documents(documents)
