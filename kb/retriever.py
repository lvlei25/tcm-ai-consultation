# -*- coding: utf-8 -*-
"""混合检索器：FAISS 向量检索 + BM25 关键词检索，加权融合去重后 MMR 去冗余"""
from config import BM25_WEIGHT, CANDIDATE_N, MMR_LAMBDA, TOP_K, VECTOR_WEIGHT
from kb.loader import tokenize


class HybridRetriever:
    """混合检索器：向量路与关键词路各自召回候选，归一化后加权融合"""

    def __init__(self, faiss_store, chunks: list[dict], bm25):
        """faiss_store: FAISS 实例；chunks: [{"text","metadata"}] 列表；bm25: BM25Okapi 实例"""
        self.faiss_store = faiss_store
        self.chunks = chunks
        self.bm25 = bm25

    def _vector_hits(self, query: str, n: int) -> list[tuple]:
        """向量检索，返回 (文本, 元数据, 相似度) 列表，L2 距离转相似度"""
        k = min(n, len(self.chunks))
        hits = self.faiss_store.similarity_search_with_score(query, k=k)
        return [
            (doc.page_content, doc.metadata, 1.0 / (1.0 + float(distance)))
            for doc, distance in hits
        ]

    def _bm25_hits(self, query: str, n: int) -> list[tuple]:
        """BM25 关键词检索，返回 (文本, 元数据, 得分) 列表，过滤零分项"""
        tokens = tokenize(query)
        scores = self.bm25.get_scores(tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [
            (self.chunks[i]["text"], self.chunks[i]["metadata"], float(scores[i]))
            for i in order
            if scores[i] > 0
        ]

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        """min-max 归一化到 [0,1]；唯一候选视为最强命中返回 1.0，多个相同取值统一为 0.5"""
        if len(values) == 1:
            return [1.0]
        lo, hi = min(values), max(values)
        if hi - lo == 0:
            return [0.5] * len(values)
        return [(v - lo) / (hi - lo) for v in values]

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        """两个分词集合的 Jaccard 相似度，用于 MMR 冗余度量"""
        if not left or not right:
            return 0.0
        union = left | right
        return len(left & right) / len(union)

    @classmethod
    def _mmr_select(cls, ranked: list[dict], top_k: int, lambda_: float = MMR_LAMBDA):
        """按 MMR 从融合排序结果中选取 top_k，抑制内容高度重复的相邻块

        得分 = lambda_ * 融合分 - (1 - lambda_) * 与已选块的最大相似度
        """
        if len(ranked) <= top_k:
            return ranked
        token_sets = [set(tokenize(item["text"])) for item in ranked]
        picked: list[int] = []
        rest = list(range(len(ranked)))
        while rest and len(picked) < top_k:
            best_index, best_value = None, None
            for i in rest:
                redundancy = max(
                    (cls._jaccard(token_sets[i], token_sets[j]) for j in picked),
                    default=0.0,
                )
                value = lambda_ * ranked[i]["score"] - (1 - lambda_) * redundancy
                if best_value is None or value > best_value:
                    best_index, best_value = i, value
            picked.append(best_index)
            rest.remove(best_index)
        return [ranked[i] for i in picked]

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """混合检索：两路候选归一化加权融合，按文本去重取前 top_k

        返回 [{"text","metadata","score","vec_score","bm25_score"}] 列表，
        score 为融合相关度（0~1），vec_score / bm25_score 为两路归一化得分明细
        """
        vec_hits = self._vector_hits(query, CANDIDATE_N)
        bm_hits = self._bm25_hits(query, CANDIDATE_N)
        if not vec_hits and not bm_hits:
            return []
        fused: dict[str, dict] = {}
        if vec_hits:
            vec_scores = self._normalize([h[2] for h in vec_hits])
            for (text, meta, _), s in zip(vec_hits, vec_scores):
                fused[text] = {
                    "text": text,
                    "metadata": meta,
                    "score": VECTOR_WEIGHT * s,
                    "vec_score": s,
                    "bm25_score": 0.0,
                }
        if bm_hits:
            bm_scores = self._normalize([h[2] for h in bm_hits])
            for (text, meta, _), s in zip(bm_hits, bm_scores):
                item = fused.setdefault(
                    text,
                    {
                        "text": text,
                        "metadata": meta,
                        "score": 0.0,
                        "vec_score": 0.0,
                        "bm25_score": 0.0,
                    },
                )
                item["score"] += BM25_WEIGHT * s
                item["bm25_score"] += s
        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return self._mmr_select(ranked, top_k)
