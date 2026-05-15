"""
去重器模块
===========
基于标题关键词 Jaccard 相似度的语义去重，以及 URL/日期/噪声过滤。

用法::

    from src.processors.dedup import dedup_and_filter

    filtered = dedup_and_filter(all_data, url_history)
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from src.utils.config import get_dedup_config, get_noise_patterns

# ============================================================
# 停用词表
# ============================================================
STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "and", "but", "or",
    "nor", "not", "so", "very", "just", "than", "too", "also", "about",
    "up", "it", "its", "this", "that", "these", "those", "new", "how",
    "what", "which", "who", "when", "where", "why", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "only", "own", "same", "如果", "的", "了", "在", "是", "我",
    "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很",
    "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己",
    "这", "他", "她", "它", "们", "那", "被", "从", "对", "把", "与",
    "以", "但", "中", "等", "又", "而", "或", "及",
}


def extract_keywords(title: str) -> Set[str]:
    """从标题中提取关键词（去停用词，小写化）

    使用正则提取英文单词（至少 2 个字母数字）和中文汉字片段，过滤停用词
    和单字符词。

    Args:
        title: 新闻标题字符串。

    Returns:
        关键词集合。
    """
    title = title.lower()
    # 分词：匹配英文单词（字母打头）或连续中文字符
    words = re.findall(r"[a-z][a-z0-9]+|[\u4e00-\u9fff]+", title)
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """计算两个集合的 Jaccard 相似度。

    定义为交集大小 / 并集大小。任一集合为空时返回 0.0。

    Args:
        set1: 第一个关键词集合。
        set2: 第二个关键词集合。

    Returns:
        0.0 ~ 1.0 的相似度值。
    """
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)


def semantic_dedup(items: List[Dict[str, Any]], threshold: float = 0.55) -> List[Dict[str, Any]]:
    """基于标题关键词的语义去重。

    逐条处理，对每条提取关键词后与已保留的条目比较 Jaccard 相似度，
    若存在超过 *threshold* 的匹配则跳过，否则保留。

    Args:
        items: 待去重的条目列表，每项需包含 ``title`` 字段。
        threshold: Jaccard 相似度阈值，高于此值视为重复（默认 0.55）。

    Returns:
        去重后的条目列表。
    """
    kept: List[Dict[str, Any]] = []
    kept_keywords: List[Set[str]] = []

    for item in items:
        title = item.get("title", "")
        kw = extract_keywords(title)

        # 与已保留的每条比较
        is_dup = False
        for existing_kw in kept_keywords:
            if jaccard_similarity(kw, existing_kw) > threshold:
                is_dup = True
                break

        if not is_dup:
            kept.append(item)
            kept_keywords.append(kw)

    return kept


def dedup_and_filter(
    all_data: List[Dict[str, Any]],
    url_history: Dict[str, str],
) -> List[Dict[str, Any]]:
    """综合去重与过滤管道。

    依次执行：
    1. 噪声过滤 —— 通过 URL 模式匹配丢弃低质量来源条目。
    2. 日期门控 —— 丢弃 ``published`` 为空、未知或超过 2 天的条目。
    3. URL 精确去重 —— 按 URL 去重，同时参考跨日历史（保留今日首次见到的 URL）。
    4. 语义去重 —— 基于标题关键词 Jaccard 相似度去重。

    Args:
        all_data: 全量采集数据列表，每项需含 ``url``、``title``、``published`` 字段。
        url_history: 历史 URL 字典，格式为 ``{url: "YYYY-MM-DD"}``。

    Returns:
        过滤并去重后的条目列表。
    """
    dedup_config = get_dedup_config()
    noise_patterns = get_noise_patterns()

    # ----------------------------------------------------------
    # 1. 噪声过滤
    # ----------------------------------------------------------
    filtered: List[Dict[str, Any]] = []
    for item in all_data:
        url = item.get("url", "")
        if any(pat in url for pat in noise_patterns):
            continue
        filtered.append(item)

    # ----------------------------------------------------------
    # 2. 日期门控 —— 丢弃 published 为空/unknown/过旧（>2 天）
    # ----------------------------------------------------------
    cutoff = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    date_filtered: List[Dict[str, Any]] = [
        item
        for item in filtered
        if item.get("published", "unknown") not in ("unknown", "")
        and item.get("published", "") >= cutoff
    ]

    # ----------------------------------------------------------
    # 3. URL 精确去重 + 跨日历史去重
    #    - 只过滤昨天及之前见过的 URL，今天的 URL 保留
    # ----------------------------------------------------------
    today = datetime.now().strftime("%Y-%m-%d")
    seen_urls: Set[str] = set()
    url_deduped: List[Dict[str, Any]] = []
    for item in date_filtered:
        url = item.get("url", "")
        if url and url in seen_urls:
            continue
        if url and url in url_history and url_history[url] < today:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(item)

    # ----------------------------------------------------------
    # 4. 语义去重
    # ----------------------------------------------------------
    threshold = dedup_config.get("semantic_threshold", 0.45)
    sem_deduped = semantic_dedup(url_deduped, threshold=threshold)

    return sem_deduped
