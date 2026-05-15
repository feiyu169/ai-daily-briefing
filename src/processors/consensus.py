"""
共识/分歧分析模块
=================
分析不同来源对同一话题的报道角度，识别共识和分歧点。

使用规则:
1. 同一话题下，不同来源的标题关键词重叠部分 => 共识
2. 同一话题下，各来源独有的关键词 => 分歧/独特视角
3. 语义极性判断（基于正向/负向词）=> 情感倾向
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple

from src.utils.text import extract_keywords


# 正面情感词
POSITIVE_WORDS: Set[str] = {
    "breakthrough", "innovation", "achievement", "milestone", "success",
    "growth", "surge", "soar", "record", "leap", "advance", "improve",
    "launch", "release", "win", "winning", "leading",
    "突破", "创新", "成就", "里程碑", "成功", "增长", "飞跃",
    "发布", "推出", "领先", "首次", "重大",
}

# 负面情感词
NEGATIVE_WORDS: Set[str] = {
    "concern", "warning", "risk", "threat", "danger", "crisis", "decline",
    "drop", "fall", "loss", "fail", "failure", "ban", "block", "restrict",
    "cut", "slash", "layoff", "investigation", "lawsuit", "violation",
    "担忧", "警告", "风险", "威胁", "危险", "危机", "下跌", "失败",
    "禁止", "限制", "裁员", "调查", "诉讼", "违规", "暴跌", "受损",
}


def _compute_sentiment(title: str) -> Tuple[str, float]:
    """计算标题的情感倾向。

    Args:
        title: 标题文本。

    Returns:
        (sentiment_label, score) 元组。
        sentiment_label: "positive"、"negative" 或 "neutral"。
        score: -1.0 (极负面) ~ 1.0 (极正面)。
    """
    title_lower = title.lower()
    pos_count = sum(1 for w in POSITIVE_WORDS if w in title_lower)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in title_lower)

    total = pos_count + neg_count
    if total == 0:
        return ("neutral", 0.0)

    score = (pos_count - neg_count) / total
    if score > 0.2:
        return ("positive", round(score, 2))
    elif score < -0.2:
        return ("negative", round(score, 2))
    else:
        return ("neutral", round(score, 2))


def _extract_unique_perspectives(
    items: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """从同一话题的多个报道中提取各来源的独特视角关键词。

    Args:
        items: 同一话题下的条目列表。

    Returns:
        字典: {source_name: [独特关键词列表]}。
    """
    # 按来源分组
    source_kws: Dict[str, Set[str]] = defaultdict(set)
    for item in items:
        source = item.get("source", "unknown")
        kw = extract_keywords(item.get("title", ""))
        source_kws[source] |= kw

    # 计算全局高频词
    all_kws: List[str] = []
    for kw_set in source_kws.values():
        all_kws.extend(kw_set)
    global_freq = Counter(all_kws)

    # 低频词（出现在少于 30% 来源中）= 独特视角候选
    num_sources = len(source_kws)
    threshold = max(1, int(num_sources * 0.3))

    result: Dict[str, List[str]] = {}
    for source, kws in source_kws.items():
        unique = [
            kw for kw in kws
            if global_freq[kw] <= threshold
        ]
        result[source] = sorted(unique)[:5]  # 最多 5 个

    return result


def _build_consensus_keywords(
    items: List[Dict[str, Any]],
) -> List[str]:
    """从同一话题的多个报道中提取共识关键词。

    Args:
        items: 同一话题下的条目列表。

    Returns:
        出现在多个来源中的共识关键词列表（按频率降序）。
    """
    source_kws: Dict[str, Set[str]] = defaultdict(set)
    for item in items:
        source = item.get("source", "unknown")
        kw = extract_keywords(item.get("title", ""))
        source_kws[source] |= kw

    # 统计每个关键词出现在多少个来源中
    kw_source_count: Dict[str, int] = Counter()
    for kws in source_kws.values():
        for kw in kws:
            kw_source_count[kw] += 1

    num_sources = len(source_kws)
    if num_sources <= 1:
        return []

    # 共识：出现在超过 50% 来源中的关键词
    threshold = max(2, num_sources // 2 + 1)
    consensus = sorted(
        [kw for kw, count in kw_source_count.items() if count >= threshold],
        key=lambda kw: kw_source_count[kw],
        reverse=True,
    )
    return consensus[:10]


def analyze_consensus(
    cluster_items: List[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """对多个跨源话题聚类进行共识/分歧分析。

    Args:
        cluster_items: 聚类列表，每个元素是该话题下的所有条目。

    Returns:
        分析结果列表，每个话题一项:
        - topic_items: 该话题条目
        - consensus_keywords: 跨源共识关键词
        - unique_perspectives: 各来源独特视角
        - sentiment_distribution: 情感分布 {positive/negative/neutral: count}
        - divergence_count: 分歧来源数
        - overall_assessment: 总体评价
    """
    results: List[Dict[str, Any]] = []

    for items in cluster_items:
        if len(items) < 2:
            continue

        # 共识关键词
        consensus_kw = _build_consensus_keywords(items)

        # 各来源独特视角
        perspectives = _extract_unique_perspectives(items)

        # 情感分析
        sentiments: Dict[str, int] = Counter()
        for item in items:
            label, _ = _compute_sentiment(item.get("title", ""))
            sentiments[label] += 1

        # 分歧计数
        source_count = len({item.get("source", "unknown") for item in items})
        divergence_count = max(0, source_count - 1)

        # 总体评价
        total_items = len(items)
        if len(consensus_kw) >= 3:
            consensus_level = "高"
        elif len(consensus_kw) >= 1:
            consensus_level = "中"
        else:
            consensus_level = "低"

        dominant_sentiment = sentiments.most_common(1)[0][0] if sentiments else "neutral"

        results.append({
            "topic_items": items,
            "item_count": total_items,
            "sources": sorted({item.get("source", "unknown") for item in items}),
            "consensus_keywords": consensus_kw,
            "unique_perspectives": perspectives,
            "sentiment_distribution": dict(sentiments),
            "dominant_sentiment": dominant_sentiment,
            "divergence_count": divergence_count,
            "consensus_level": consensus_level,
            "overall_assessment": (
                f"跨{len(perspectives)}个来源报道，共识度{consensus_level}，"
                f"主要情感偏向{dominant_sentiment}"
            ),
        })

    # 按 item_count 降序
    results.sort(key=lambda r: r["item_count"], reverse=True)
    return results


def compute_sentiment(title: str) -> Tuple[str, float]:
    """计算标题的情感倾向（公开接口）。

    Args:
        title: 标题文本。

    Returns:
        (sentiment_label, score) 元组。
    """
    return _compute_sentiment(title)


def extract_unique_perspectives(
    items: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """提取各来源的独特视角（公开接口）。

    Args:
        items: 条目列表。

    Returns:
        字典: {source_name: [独特关键词]}。
    """
    return _extract_unique_perspectives(items)


def build_consensus_keywords(
    items: List[Dict[str, Any]],
) -> List[str]:
    """提取共识关键词（公开接口）。

    Args:
        items: 条目列表。

    Returns:
        共识关键词列表。
    """
    return _build_consensus_keywords(items)
