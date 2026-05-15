"""
趋势追踪模块
============
从采集的 items 中检测高频趋势关键词，并结合历史记录计算趋势 momentum。

Functions:
    detect_trend_keywords — 从 items 标题中提取高频关键词
    get_trend_momentum   — 结合历史数据计算每个趋势关键词的热度动量
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from src.utils.config import get_collector_config
from src.utils.file_utils import load_trends_history, save_trends_history

# 默认停用词（与 v5 extract_keywords 对齐）
STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would",
    "can", "could", "shall", "should", "may", "might", "must",
    "to", "of", "in", "for", "on", "and", "or", "but", "not",
    "with", "at", "from", "by", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off",
    "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "only", "own", "same", "so", "than", "too", "very",
    "just", "about", "up", "it", "its", "that", "this", "these",
    "those", "what", "which", "who", "whom", "this", "new",
}


def extract_keywords(title: str) -> Set[str]:
    """从标题中提取关键词（去停用词、小写化）

    与 v5 中的 extract_keywords 逻辑保持一致。

    Args:
        title: 标题文本

    Returns:
        提取出的关键词集合
    """
    title = title.lower()
    # 英文词（至少两个字母/数字）或中文字符
    words = re.findall(r"[a-z][a-z0-9]+|[\u4e00-\u9fff]+", title)
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def detect_trend_keywords(
    items: List[Dict[str, Any]],
    min_freq: int = 2,
) -> Set[str]:
    """从所有 items 标题中提取高频趋势关键词

    遍历每个 item 的 title，提取关键词后统计频次，
    返回出现次数 >= min_freq 的关键词集合。

    Args:
        items: 采集结果列表，每个 item 应包含 "title" 字段
        min_freq: 最低出现频次阈值（默认 2）

    Returns:
        出现频次 >= min_freq 的关键词集合
    """
    all_kw: List[str] = []
    for item in items:
        title = item.get("title", "") or ""
        kw = extract_keywords(title)
        # 只保留有意义的关键词（长度 > 2 或中文）
        all_kw.extend(
            w for w in kw if len(w) > 2 or re.match(r"[\u4e00-\u9fff]", w)
        )

    counter: Counter[str] = Counter(all_kw)
    return {kw for kw, cnt in counter.items() if cnt >= min_freq}


def get_trend_momentum(
    items: List[Dict[str, Any]],
    trends_file: str | None = None,
    min_freq: int = 2,
) -> Tuple[Set[str], Dict[str, Any]]:
    """检测趋势关键词并计算 momentum

    1. 用 detect_trend_keywords 提取当日高频关键词
    2. 从历史记录中加载以往趋势
    3. 合并记录并保存
    4. 返回关键词集合及各自 momentum 信息

    Momentum 评分规则：
        - first_seen: 关键词首次出现的日期
        - last_seen:  关键词最近出现的日期
        - streak:     连续出现天数
        - heat:       热度等级（new / rising / steady / fading）
        - score:      综合评分（0.0 ~ 1.0）

    Args:
        items: 采集结果列表
        trends_file: 趋势历史文件路径（默认从配置加载）
        min_freq: 关键词最低出现频次

    Returns:
        (trend_keywords, momentum_data) 元组
        - trend_keywords: 当日趋势关键词集合
        - momentum_data:  以关键词为 key 的动量详情字典
    """
    # 加载配置
    collector_cfg = get_collector_config()
    output_cfg = collector_cfg.get("output", {})
    trends_days: int = collector_cfg.get("trends_days", 3)

    if trends_file is None:
        trends_file = output_cfg.get("trends_file", "/tmp/collector_trends_history.json")

    # 加载历史
    history: Dict[str, str] = load_trends_history(trends_file, trends_days)

    # 检测今日关键词
    today_keywords: Set[str] = detect_trend_keywords(items, min_freq)

    # 合并历史：为每个关键词记录最早出现日期
    today_str: str = datetime.now().strftime("%Y-%m-%d")
    merged_history: Dict[str, str] = dict(history)  # 复制
    for kw in today_keywords:
        if kw in merged_history:
            # last_seen 已是最新日期（load 时已做 cutoff）
            pass
        else:
            merged_history[kw] = today_str

    # 保存更新后的历史
    save_trends_history(trends_file, merged_history, today_keywords, trends_days)

    # 计算 momentum
    momentum_data: Dict[str, Dict[str, Any]] = {}
    yesterday_str: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for kw in today_keywords:
        last_seen: str = history.get(kw, today_str)
        first_seen: str = merged_history.get(kw, today_str)

        # 连续出现天数（从第一次到今天）
        try:
            first_dt = datetime.strptime(first_seen, "%Y-%m-%d")
            last_dt = datetime.strptime(today_str, "%Y-%m-%d")
            streak: int = (last_dt - first_dt).days + 1
        except ValueError:
            streak = 1

        # 热度等级
        if kw not in history:
            heat: str = "new"
        elif last_seen == yesterday_str or last_seen == today_str:
            heat = "rising" if streak >= 2 else "steady"
        else:
            heat = "fading"

        # 综合评分 (0~1)
        # 新词: 0.5, rising: 0.5 + streak * 0.1 (上限 1.0)
        # steady: 0.4, fading: 0.2
        if heat == "new":
            score: float = 0.5
        elif heat == "rising":
            score = min(0.5 + streak * 0.1, 1.0)
        elif heat == "steady":
            score = 0.4
        else:  # fading
            score = 0.2

        momentum_data[kw] = {
            "first_seen": first_seen,
            "last_seen": today_str,
            "streak": streak,
            "heat": heat,
            "score": round(score, 2),
        }

    return today_keywords, momentum_data
