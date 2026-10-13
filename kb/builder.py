# -*- coding: utf-8 -*-
"""知识库构建与加载：医案分块向量化入 FAISS，构建 BM25 关键词索引，产物落盘"""
import json
import pickle
import shutil

import jieba
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi

from config import (
    BM25_FILE,
    CHUNKS_FILE,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    KB_DIR,
    MEDICAL_CASES_DIR,
    get_api_key,
)
from kb.loader import load_case_documents, split_documents


def make_embeddings() -> DashScopeEmbeddings:
    """创建 DashScope 向量化客户端"""
    return DashScopeEmbeddings(model=EMBEDDING_MODEL, dashscope_api_key=get_api_key())


def build_knowledge_base(cases_dir=MEDICAL_CASES_DIR) -> dict:
    """构建知识库：加载医案并分块，向量化入 FAISS，构建 BM25，产物落盘

    返回统计信息字典；医案为空或目录无 .md 文件时抛出异常
    """
    documents = split_documents(load_case_documents(cases_dir))
    if not documents:
        raise ValueError("医案分块结果为空，无法构建知识库")
    # 清空旧产物，避免索引与语料版本不一致
    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    # 向量库：构建并落盘
    embeddings = make_embeddings()
    faiss_store = FAISS.from_documents(documents, embeddings)
    faiss_store.save_local(str(FAISS_INDEX_DIR))
    # BM25：分词构建索引，语料与索引分别落盘
    texts = [doc.page_content for doc in documents]
    tokenized = [jieba.lcut(text) for text in texts]
    bm25 = BM25Okapi(tokenized)
    chunks = [
        {"text": text, "metadata": doc.metadata}
        for text, doc in zip(texts, documents)
    ]
    CHUNKS_FILE.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with open(BM25_FILE, "wb") as f:
        pickle.dump(bm25, f)
    return {"块数": len(documents)}


def load_knowledge_base():
    """加载已构建的知识库产物，返回 (faiss_store, chunks, bm25)

    产物缺失时抛出 FileNotFoundError，提示先运行构建脚本
    """
    index_file = FAISS_INDEX_DIR / "index.faiss"
    if not (index_file.exists() and CHUNKS_FILE.exists() and BM25_FILE.exists()):
        raise FileNotFoundError("知识库尚未构建，请先运行：python scripts/build_kb.py")
    faiss_store = FAISS.load_local(
        str(FAISS_INDEX_DIR), make_embeddings(), allow_dangerous_deserialization=True
    )
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    with open(BM25_FILE, "rb") as f:
        bm25 = pickle.load(f)
    return faiss_store, chunks, bm25
