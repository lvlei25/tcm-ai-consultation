# -*- coding: utf-8 -*-
"""MCP 知识库检索器：经 Streamable HTTP 调用远程 MCP 检索工具，解析并归一化结果"""
import asyncio
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from config import MCP_MAX_TERMS, MCP_SEARCH_TOOL, MCP_SERVER_URL, MCP_TIMEOUT_SECONDS, TOP_K
from kb.loader import tokenize

# 命中块标题形如：### source/医学衷中参西录（命中 38 次）
_BLOCK_PATTERN = re.compile(r"^### (.+?)/(.+?)（命中 (\d+) 次）$", re.MULTILINE)
# 无命中时服务端返回的中文说明特征
_NO_HIT_MARKERS = ("命中 0 条", "没有同时包含", "没有找到", "无命中")
# 连接类错误特征，命中时附加启动提示
_CONNECT_MARKERS = ("ConnectionRefusedError", "ConnectError", "ConnectTimeout", "refused")


def _describe_error(exc: BaseException) -> str:
    """展开 ExceptionGroup 等嵌套异常，拼出完整可读的错误链"""
    parts: list[str] = []
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        nested = getattr(current, "exceptions", None)
        if nested:
            stack.extend(reversed(list(nested)))
        else:
            parts.append(f"{type(current).__name__}: {current}")
    detail = "；".join(parts) or str(exc)
    if any(marker in detail for marker in _CONNECT_MARKERS):
        detail += "（请确认 MCP 服务端已启动并监听该地址）"
    return detail


class McpRetriever:
    """MCP 知识库检索器：作为唯一检索源，结果结构与本地 HybridRetriever 一致

    服务端 search 工具：入参 {"query": str, "limit": int}，
    返回分块纯文本（### 类型/名称（命中 N 次）+ 片段）；
    无法识别的格式抛出明确中文异常，不做兜底
    """

    def __init__(
        self,
        server_url: str = MCP_SERVER_URL,
        tool_name: str = MCP_SEARCH_TOOL,
        timeout_seconds: int = MCP_TIMEOUT_SECONDS,
    ):
        if not server_url:
            raise RuntimeError(
                "已启用 MCP 知识库（MCP_ENABLED=true），但未配置 MCP_SERVER_URL，"
                "请在 config.py 或 .env 中填写 MCP 服务端地址"
            )
        self.server_url = server_url
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """调用 MCP 检索工具并返回统一结构的证据列表

        服务端为 AND 语义：先按全词查询，0 命中时按词数递减重试
        （前 MCP_MAX_TERMS → 前 3 → 前 2 → 前 1 词），首个非空结果即用；
        无空格长语句先用 jieba 分词再走同一降级序列；
        全部为空返回空列表（诊断按无证据处理，非异常）。

        返回 [{"text","metadata","score","vec_score","bm25_score"}]，
        score 为归一化相关度（0~1），vec_score / bm25_score 恒为 0.0
        """
        terms = query.split()
        if len(terms) == 1 and len(terms[0]) > 6:
            # 无空格长语句（生成端偶发未按关键词输出）：jieba 分词后再降级
            terms = [token for token in tokenize(terms[0]) if token.strip()]
        candidates = [terms]
        if len(terms) > 1:
            candidates.extend(terms[:size] for size in range(MCP_MAX_TERMS, 0, -1))
        seen: set[int] = set()
        for candidate in candidates:
            key = len(candidate)
            if key in seen:
                continue
            seen.add(key)
            raw = self._call_search(" ".join(candidate), top_k)
            items = self._parse_blocks(raw)
            if items:
                return self._normalize_and_rank(items, top_k)
        return []

    def _call_search(self, query: str, top_k: int) -> str:
        """建立临时 Streamable HTTP 会话调用检索工具，返回工具原始文本输出

        连接、握手、调用中的任何异常统一在此包装为中文 RuntimeError，
        ExceptionGroup 等嵌套异常经 _describe_error 展开，不做静默兜底
        """
        try:
            return asyncio.run(self._call_search_async(query, top_k))
        except Exception as exc:
            raise RuntimeError(
                f"调用 MCP 检索工具失败（{self.server_url} / {self.tool_name}）：{_describe_error(exc)}"
            ) from exc

    async def _call_search_async(self, query: str, top_k: int) -> str:
        """异步建立会话并调用工具"""
        async with streamable_http_client(self.server_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(
                read_stream, write_stream, read_timeout_seconds=self.timeout_seconds
            ) as session:
                await session.initialize()
                result = await session.call_tool(
                    self.tool_name, {"query": query, "limit": top_k}
                )
        texts = [
            block.text for block in result.content if getattr(block, "text", None)
        ]
        if not texts:
            raise RuntimeError(
                f"MCP 检索工具 {self.tool_name} 未返回任何文本内容，请检查服务端实现"
            )
        return texts[0]

    @staticmethod
    def _parse_blocks(raw: str) -> list[dict]:
        """解析命中块文本为证据列表，无命中说明返回空列表，无法识别的格式抛中文异常"""
        matches = list(_BLOCK_PATTERN.finditer(raw))
        if not matches:
            if any(marker in raw for marker in _NO_HIT_MARKERS):
                return []
            raise RuntimeError(
                f"无法识别 MCP 检索工具的返回格式：{raw[:100]}..."
            )
        items: list[dict] = []
        for index, match in enumerate(matches):
            kind, name, hits = match.group(1), match.group(2), int(match.group(3))
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
            text = raw[start:end].strip()
            if not text:
                raise RuntimeError(
                    f"MCP 检索工具返回的第 {index + 1} 个命中块没有内容：{name}"
                )
            items.append(
                {
                    "text": text,
                    "metadata": {"source": name, "类型": kind, "命中次数": hits},
                    "score": float(hits),
                }
            )
        return items

    @staticmethod
    def _normalize_and_rank(items: list[dict], top_k: int) -> list[dict]:
        """按文本去重，分数 min-max 归一化（唯一候选视为 1.0），按分数降序取前 top_k"""
        unique: dict[str, dict] = {}
        for item in items:
            unique.setdefault(item["text"], item)
        results = list(unique.values())
        if results:
            scores = [item["score"] for item in results]
            lo, hi = min(scores), max(scores)
            span = hi - lo
            for item in results:
                item["score"] = 1.0 if span == 0 else (item["score"] - lo) / span
                item["vec_score"] = 0.0
                item["bm25_score"] = 0.0
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]
