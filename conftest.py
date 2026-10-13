# -*- coding: utf-8 -*-
"""pytest 根配置：将项目根目录加入 sys.path，保证测试可直接导入项目模块"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
