# -*- coding: utf-8 -*-
"""知识库构建与加载：医案分块向量化入 FAISS，构建 BM25 关键词索引，产物落盘"""
import hashlib
import json
import pickle
import shutil
import time

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi

from config import (
    BM25_FILE,
    CHUNKS_FILE,
    EMBED_BATCH_SIZE,
    EMB_CACHE_FILE,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    KB_DIR,
    KB_TMP_DIR,
    MEDICAL_CASES_DIR,
    get_api_key,
)
from kb.loader import load_case_documents, split_documents, tokenize


def make_embeddings() -> DashScopeEmbeddings:
    """创建 DashScope 向量化客户端"""
    return DashScopeEmbeddings(model=EMBEDDING_MODEL, dashscope_api_key=get_api_key())


def chunk_hash(text: str) -> str:
    """计算块文本的 sha1 哈希，作为向量缓存键"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_emb_cache(path=None) -> dict:
    """加载向量缓存，文件不存在或损坏时返回空字典

    path 缺省时在调用时读取 EMB_CACHE_FILE，便于测试重定向路径
    """
    path = path or EMB_CACHE_FILE
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        cache = pickle.load(f)
    return cache if isinstance(cache, dict) else {}


def save_emb_cache(cache: dict, path=None) -> None:
    """向量缓存落盘，父目录不存在时自动创建

    path 缺省时在调用时读取 EMB_CACHE_FILE，便于测试重定向路径
    """
    path = path or EMB_CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(cache, f)


def iter_batches(items: list, size: int = EMBED_BATCH_SIZE):
    """按固定大小切分列表，产出 (起始下标, 批次列表)"""
    for start in range(0, len(items), size):
        yield start, items[start : start + size]


def embed_texts(
    texts: list[str], embeddings: DashScopeEmbeddings, cache: dict, use_cache: bool = True
) -> tuple[list[list[float]], int]:
    """分批向量化文本，返回 (向量列表, 实际请求向量化的块数)

    缓存命中的块不再请求接口；每批完成打印中文进度
    """
    vectors: list[list[float]] = [None] * len(texts)  # type: ignore[list-item]
    pending: list[int] = []
    for index, text in enumerate(texts):
        key = chunk_hash(text)
        if use_cache and key in cache:
            vectors[index] = cache[key]
        else:
            pending.append(index)
    if pending:
        pending_texts = [texts[i] for i in pending]
        for start, batch in iter_batches(pending_texts, EMBED_BATCH_SIZE):
            done = start + len(batch)
            print(f"  向量化进度：{done}/{len(pending_texts)} 块")
            batch_vectors = embeddings.embed_documents(batch)
            for offset, vector in zip(range(start, start + len(batch)), batch_vectors):
                vectors[pending[offset]] = vector
        for index in pending:
            cache[chunk_hash(texts[index])] = vectors[index]
    return vectors, len(pending)


def _write_artifacts(documents, vectors, chunks) -> None:
    """将三件产物先写入临时目录，成功后原子替换正式目录"""
    if KB_TMP_DIR.exists():
        shutil.rmtree(KB_TMP_DIR)
    KB_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_faiss_dir = KB_TMP_DIR / "faiss_index"
    tmp_chunks_file = KB_TMP_DIR / "chunks.json"
    tmp_bm25_file = KB_TMP_DIR / "bm25.pkl"

    faiss_store = FAISS.from_embeddings(
        text_embeddings=list(zip([d.page_content for d in documents], vectors)),
        embedding=make_embeddings(),
        metadatas=[d.metadata for d in documents],
    )
    faiss_store.save_local(str(tmp_faiss_dir))
    tmp_chunks_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    tokenized = [tokenize(chunk["text"]) for chunk in chunks]
    with open(tmp_bm25_file, "wb") as f:
        pickle.dump(BM25Okapi(tokenized), f)

    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    for item in KB_TMP_DIR.iterdir():
        shutil.move(str(item), str(KB_DIR / item.name))
    shutil.rmtree(KB_TMP_DIR)


def build_knowledge_base(cases_dir=MEDICAL_CASES_DIR, use_cache: bool = True) -> dict:
    """构建知识库：加载医案并分块，分批向量化入 FAISS，构建 BM25，产物落盘

    返回统计信息字典：块数 / 向量化块数 / 耗时秒；医案为空或目录无 .md 文件时抛出异常
    """
    started = time.time()
    documents = split_documents(load_case_documents(cases_dir))
    if not documents:
        raise ValueError("医案分块结果为空，无法构建知识库")
    texts = [doc.page_content for doc in documents]
    chunks = [
        {"text": text, "metadata": doc.metadata} for text, doc in zip(texts, documents)
    ]
    embeddings = make_embeddings()
    cache = load_emb_cache() if use_cache else {}
    vectors, embedded_count = embed_texts(texts, embeddings, cache, use_cache=use_cache)
    if use_cache:
        save_emb_cache(cache)
    _write_artifacts(documents, vectors, chunks)
    return {
        "块数": len(documents),
        "向量化块数": embedded_count,
        "耗时秒": round(time.time() - started, 1),
    }


def rebuild_bm25() -> dict:
    """按当前分词词典重建 BM25 索引，复用 chunks.json，不重新向量化

    词典或分块语料变化后调用，避免为更新关键词索引付出向量化成本
    """
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError("知识库尚未构建，请先运行：python scripts/build_kb.py")
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    bm25 = BM25Okapi([tokenize(chunk["text"]) for chunk in chunks])
    BM25_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_FILE, "wb") as f:
        pickle.dump(bm25, f)
    return {"块数": len(chunks)}


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
