# -*- coding: utf-8 -*-
"""kb.builder 测试：分批向量化、产物一致性、BM25 重建与空语料异常"""
import json
import pickle

import pytest

import kb.builder as builder
from config import EMBED_BATCH_SIZE

# 小型医案文本（用于构建测试，不调用真实接口）
CASE_TEXT = (
    "# 不寐门\n## 心脾两虚\n患者不寐多梦，神疲乏力，舌淡苔薄白，脉细弱，治以归脾汤。\n"
    "## 心肾不交\n患者心烦不寐，头晕耳鸣，舌红少苔，脉细数，治以黄连阿胶汤。"
)


class _FakeEmbeddings:
    """测试用向量化器：按文本长度生成确定性向量，不发起网络请求"""

    def __init__(self, dim: int = 8):
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        base = float(len(text) % 7) / 7.0
        return [base + i / self.dim for i in range(self.dim)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """将构建产物路径重定向到临时目录，并替换为测试用向量化器"""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "case.md").write_text(CASE_TEXT, encoding="utf-8")
    kb_dir = tmp_path / "kb"
    monkeypatch.setattr(builder, "KB_DIR", kb_dir)
    monkeypatch.setattr(builder, "KB_TMP_DIR", tmp_path / "kb_tmp")
    monkeypatch.setattr(builder, "EMB_CACHE_FILE", tmp_path / "emb_cache.pkl")
    monkeypatch.setattr(builder, "CHUNKS_FILE", kb_dir / "chunks.json")
    monkeypatch.setattr(builder, "BM25_FILE", kb_dir / "bm25.pkl")
    monkeypatch.setattr(builder, "FAISS_INDEX_DIR", kb_dir / "faiss_index")
    monkeypatch.setattr(builder, "make_embeddings", lambda: _FakeEmbeddings())
    return cases_dir


def test_build_produces_three_artifacts(workspace):
    """用例 33（正常）：构建后产出 faiss_index、chunks.json、bm25.pkl 三件产物"""
    stats = builder.build_knowledge_base(workspace, use_cache=False)
    assert stats["块数"] >= 1
    assert (builder.FAISS_INDEX_DIR / "index.faiss").exists()
    assert builder.CHUNKS_FILE.exists()
    assert builder.BM25_FILE.exists()


def test_build_chunks_match_documents(workspace):
    """用例 34（正常）：chunks.json 的文本与元数据与分块结果一致"""
    builder.build_knowledge_base(workspace, use_cache=False)
    chunks = json.loads(builder.CHUNKS_FILE.read_text(encoding="utf-8"))
    assert chunks
    for chunk in chunks:
        assert chunk["text"]
        assert chunk["metadata"]["source"] == "case.md"
    with open(builder.BM25_FILE, "rb") as f:
        bm25 = pickle.load(f)
    assert len(bm25.get_scores(["不寐"])) == len(chunks)


def test_build_empty_dir_raises(tmp_path, monkeypatch):
    """用例 35（异常）：医案目录无 .md 文件时抛出 FileNotFoundError"""
    monkeypatch.setattr(builder, "KB_DIR", tmp_path / "kb")
    with pytest.raises(FileNotFoundError):
        builder.build_knowledge_base(tmp_path, use_cache=False)


def test_iter_batches_covers_all_items():
    """用例 36（边界）：分批切分不丢项、不重复，最后一批为余数"""
    items = list(range(EMBED_BATCH_SIZE * 2 + 3))
    collected = []
    for _start, batch in builder.iter_batches(items, EMBED_BATCH_SIZE):
        collected.extend(batch)
    assert collected == items
    assert len(list(builder.iter_batches(items, EMBED_BATCH_SIZE))) == 3


def test_embed_cache_skips_request(workspace):
    """用例 37（正常）：二次构建命中缓存，新向量化块数为 0"""
    first = builder.build_knowledge_base(workspace, use_cache=True)
    second = builder.build_knowledge_base(workspace, use_cache=True)
    assert first["向量化块数"] == first["块数"]
    assert second["向量化块数"] == 0


def test_rebuild_bm25_reuses_chunks(workspace):
    """用例 38（正常）：BM25 重建复用 chunks.json，块数不变且不依赖向量化"""
    builder.build_knowledge_base(workspace, use_cache=False)
    stats = builder.rebuild_bm25()
    chunks = json.loads(builder.CHUNKS_FILE.read_text(encoding="utf-8"))
    assert stats["块数"] == len(chunks)
    with open(builder.BM25_FILE, "rb") as f:
        assert len(pickle.load(f).get_scores(["不寐"])) == len(chunks)
