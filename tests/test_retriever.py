# -*- coding: utf-8 -*-
"""kb.retriever 模块测试：混合检索融合、去重、归一化与边界情况"""
import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from config import CANDIDATE_N, VECTOR_WEIGHT
from kb.retriever import HybridRetriever

# 测试语料：三个不同病证的医案片段
TEXTS = [
    "失眠多梦心脾两虚方用归脾汤",
    "咳嗽风寒袭肺方用止嗽散",
    "胃痛脾胃虚寒方用黄芪建中汤",
]


def make_chunks():
    """构造与语料对应的 chunks 列表"""
    return [
        {"text": text, "metadata": {"source": f"医案{i}.md"}}
        for i, text in enumerate(TEXTS, start=1)
    ]


def make_bm25():
    """用测试语料构建真实 BM25 索引"""
    return BM25Okapi([jieba.lcut(text) for text in TEXTS])


class FakeFaissStore:
    """模拟 FAISS：按预设 (Document, L2距离) 顺序返回，并记录最近一次 k 值"""

    def __init__(self, hits):
        self.hits = hits
        self.last_k = None

    def similarity_search_with_score(self, query, k):
        self.last_k = k
        return list(self.hits[:k])


def make_faiss_all():
    """构造按语料顺序返回的 FAISS 模拟对象，距离越小越靠前"""
    distances = [0.2, 0.5, 0.9]
    return FakeFaissStore(
        [
            (Document(page_content=text, metadata={"source": f"医案{i}.md"}), d)
            for i, (text, d) in enumerate(zip(TEXTS, distances), start=1)
        ]
    )


def test_vector_only_score_weight():
    """用例 14（正常）：仅向量路命中时，最高融合分等于向量权重"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    ranked = retriever.retrieve("天氣晴朗無關詞")
    assert ranked, "向量路应始终有候选"
    assert abs(ranked[0]["score"] - VECTOR_WEIGHT) < 1e-9


def test_vector_order_by_distance():
    """用例 15（正常）：向量距离越小相似度越高，排序第一为最近邻文本"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    ranked = retriever.retrieve("天氣晴朗無關詞")
    assert ranked[0]["text"] == TEXTS[0]


def test_fusion_both_sources_higher():
    """用例 16（正常）：双路都命中的片段融合分最高（0.6 + 0.4），且两路明细分均为 1.0"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    ranked = retriever.retrieve("失眠 归脾汤")
    assert ranked[0]["text"] == TEXTS[0]
    assert abs(ranked[0]["score"] - 1.0) < 1e-9
    assert ranked[0]["vec_score"] == 1.0
    assert ranked[0]["bm25_score"] == 1.0


def test_dedup_same_text():
    """用例 17（正常）：向量与 BM25 命中同一文本时只保留一条"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    ranked = retriever.retrieve("失眠 归脾汤")
    texts = [item["text"] for item in ranked]
    assert len(texts) == len(set(texts))


def test_top_k_limit():
    """用例 18（边界）：top_k 参数限制返回条数"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    ranked = retriever.retrieve("失眠 归脾汤", top_k=1)
    assert len(ranked) == 1


def test_normalize_all_same():
    """用例 19（边界）：归一化输入全相同时统一返回 0.5，避免除零"""
    assert HybridRetriever._normalize([3.0, 3.0, 3.0]) == [0.5, 0.5, 0.5]


def test_normalize_single_value():
    """用例 32（边界）：唯一候选视为最强命中，归一化为 1.0"""
    assert HybridRetriever._normalize([7.5]) == [1.0]


def test_retrieve_empty_no_hits():
    """用例 20（异常）：向量无候选且 BM25 全零分时返回空列表"""
    retriever = HybridRetriever(FakeFaissStore([]), make_chunks(), make_bm25())
    assert retriever.retrieve("天氣晴朗無關詞") == []


def test_bm25_zero_scores_filtered():
    """用例 21（边界）：BM25 得分为零的候选被过滤，不进入融合"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    bm_hits = retriever._bm25_hits("天氣晴朗無關詞", CANDIDATE_N)
    assert bm_hits == []


def test_bm25_real_corpus_keyword():
    """用例 22（正常）：真实 BM25 对关键词查询命中含该词的片段"""
    retriever = HybridRetriever(make_faiss_all(), make_chunks(), make_bm25())
    bm_hits = retriever._bm25_hits("止嗽散 咳嗽", CANDIDATE_N)
    assert bm_hits[0][0] == TEXTS[1]


def test_vector_k_capped_by_chunks():
    """用例 23（边界）：候选数大于总块数时，k 被压缩为块数"""
    faiss_store = make_faiss_all()
    retriever = HybridRetriever(faiss_store, make_chunks(), make_bm25())
    retriever.retrieve("任意查询")
    assert faiss_store.last_k == min(CANDIDATE_N, len(TEXTS))
