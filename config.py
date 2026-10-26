# -*- coding: utf-8 -*-
"""全局配置：加载 .env 环境变量，定义模型与路径常量"""
import os
from pathlib import Path

# 项目根目录（config.py 所在目录）
PROJECT_ROOT = Path(__file__).resolve().parent

# .env 文件路径
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    """解析 .env 文件并写入 os.environ，忽略空行与 # 注释行"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


# 启动时立即加载 .env，供后续模块读取
load_env()


def get_api_key() -> str:
    """获取 DashScope API Key，缺失时抛出明确的中文异常"""
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "缺少 DASHSCOPE_API_KEY，请在项目根目录 .env 中填写：DASHSCOPE_API_KEY=你的Key"
        )
    return key


# ===== 模型常量 =====
LLM_MODEL = "qwen3.8-27b"              # 问诊推理与检索词生成模型
EMBEDDING_MODEL = "text-embedding-v3"  # 向量化模型
# DashScope OpenAI 兼容模式端点（qwen3.8 系列新模型经此端点调用）
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ===== 路径常量 =====
MEDICAL_CASES_DIR = PROJECT_ROOT / "data" / "medical_cases"  # MD 医案目录
MEDICAL_DICT_FILE = PROJECT_ROOT / "data" / "medical_dict.txt"  # 中医术语自定义词典（可选）
KB_DIR = PROJECT_ROOT / "storage" / "kb"                     # 知识库产物目录
FAISS_INDEX_DIR = KB_DIR / "faiss_index"                     # FAISS 索引目录
CHUNKS_FILE = KB_DIR / "chunks.json"                         # 分块语料文件
BM25_FILE = KB_DIR / "bm25.pkl"                              # BM25 索引文件
KB_TMP_DIR = PROJECT_ROOT / "storage" / "kb_tmp"             # 构建临时目录（成功后替换 KB_DIR）
EMB_CACHE_FILE = PROJECT_ROOT / "storage" / "emb_cache.pkl"  # 向量缓存（块文本哈希 → 向量）

# ===== 检索参数 =====
TOP_K = 6             # 混合检索最终返回的医案片段数
CANDIDATE_N = 20      # 向量/BM25 各自召回的候选片段数
VECTOR_WEIGHT = 0.6   # 向量检索融合权重
BM25_WEIGHT = 0.4     # BM25 关键词检索融合权重（与 VECTOR_WEIGHT 之和为 1）
MMR_LAMBDA = 0.7      # MMR 去冗余系数：越大越偏相关度，越小越偏多样性

# ===== 构建参数 =====
EMBED_BATCH_SIZE = 25  # 单次向量化请求的文本块数

# ===== 诊断提示词参数 =====
EVIDENCE_SNIPPET_LEN = 300  # 每条医案证据进入诊断提示词的最大字符数

# ===== MCP 知识库 =====
# 是否启用 MCP 知识库作为唯一检索源（false = 本地 FAISS + BM25 混合检索）
MCP_ENABLED = os.environ.get("MCP_ENABLED", "false").strip().lower() == "true"
# MCP 服务端 Streamable HTTP 端点，例：http://127.0.0.1:8000/mcp
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp").strip()
# MCP 检索工具名，入参 {"query": ..., "top_k": ...}，返回 JSON 数组 [{text, metadata, score}]
MCP_SEARCH_TOOL = os.environ.get("MCP_SEARCH_TOOL", "search").strip()
# MCP 调用超时秒数
MCP_TIMEOUT_SECONDS = int(os.environ.get("MCP_TIMEOUT_SECONDS", "60"))
# 服务端为 AND 语义，全词 0 命中时降级重试的最大词数
MCP_MAX_TERMS = 4

# ===== 分块参数 =====
CHUNK_SIZE = 500      # 单块最大字符数
CHUNK_OVERLAP = 80    # 相邻块重叠字符数
