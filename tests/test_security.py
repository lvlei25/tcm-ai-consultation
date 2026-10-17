# -*- coding: utf-8 -*-
"""安全规范测试：防止真实 API Key 进入被 Git 跟踪的文件"""
import re
import subprocess
from pathlib import Path

# 阿里云百炼 Key 形如 sk- 后接 30 位以上字母数字
KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9]{30,}")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_SUFFIXES = {".py", ".md", ".txt", ".ini", ".json", ".cfg", ".toml"}


def test_no_real_api_key_in_tracked_files():
    """用例 41（安全）：被 Git 跟踪的文件中不含真实 Key

    命中即失败，需立即轮换 Key 并清理历史后方可恢复
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked, "git ls-files 返回为空，无法完成泄露扫描"
    offenders = []
    for relative in tracked:
        path = PROJECT_ROOT / relative
        if path.suffix.lower() not in SCAN_SUFFIXES or not path.is_file():
            continue
        if KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(relative)
    assert not offenders, f"疑似真实 API Key 出现在被跟踪文件中：{offenders}"
