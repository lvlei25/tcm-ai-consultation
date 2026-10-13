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
KB_DIR = PROJECT_ROOT / "storage" / "kb"                     # 知识库产物目录
FAISS_INDEX_DIR = KB_DIR / "faiss_index"                     # FAISS 索引目录
CHUNKS_FILE = KB_DIR / "chunks.json"                         # 分块语料文件
BM25_FILE = KB_DIR / "bm25.pkl"                              # BM25 索引文件

# ===== 检索参数 =====
TOP_K = 6             # 混合检索最终返回的医案片段数
CANDIDATE_N = 20      # 向量/BM25 各自召回的候选片段数
VECTOR_WEIGHT = 0.6   # 向量检索融合权重（BM25 权重 = 1 - VECTOR_WEIGHT）

# ===== 分块参数 =====
CHUNK_SIZE = 500      # 单块最大字符数
CHUNK_OVERLAP = 80    # 相邻块重叠字符数
