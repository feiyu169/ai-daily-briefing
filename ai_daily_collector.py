#!/usr/bin/env python3.11
"""
AI Daily Briefing v6 — v5 兼容入口
===================================
cron job 无需修改，仍可通过 `python ai_daily_collector.py` 运行。
"""

import sys
import os

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
