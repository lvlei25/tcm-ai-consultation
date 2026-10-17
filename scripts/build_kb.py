# -*- coding: utf-8 -*-
"""知识库构建命令行入口：python scripts/build_kb.py [--no-cache]"""
import sys
from pathlib import Path

# 保证从任意工作目录运行都能导入项目根目录下的模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MEDICAL_CASES_DIR  # noqa: E402
from kb.builder import build_knowledge_base  # noqa: E402


def main() -> None:
    """扫描医案目录并重建知识库，打印统计信息

    --no-cache：忽略向量缓存，强制全量重新向量化
    """
    use_cache = "--no-cache" not in sys.argv
    print("开始构建中医医案知识库 ...")
    try:
        stats = build_knowledge_base(MEDICAL_CASES_DIR, use_cache=use_cache)
    except FileNotFoundError as exc:
        print(f"构建失败：{exc}")
        sys.exit(1)
    except ValueError as exc:
        print(f"构建失败：{exc}")
        sys.exit(1)
    print(
        f"构建完成：共 {stats['块数']} 个知识块"
        f"（新向量化 {stats['向量化块数']} 块，耗时 {stats['耗时秒']} 秒），"
        "产物已保存至 storage/kb/"
    )


if __name__ == "__main__":
    main()
