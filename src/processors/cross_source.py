"""
跨源聚类模块
============
将不同源的相关新闻按标题关键词聚类，保留跨源话题。

优化功能:
1. 动态阈值支持（use_dynamic_threshold 参数，默认 False 保持向后兼容）
2. 关键词权重（高频词权重更高，影响相似度计算）
3. 跨域保留（不同域名的相似文章保留）
"""

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from .dedup import extract_keywords, jaccard_similarity

from src.utils.config import get_dedup_config


# ---------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------

def _meaningful(kw_set: Set[str]) -> Set[str]:
    """筛选有意义关键词（>3字符 或 中文）

    Args:
        kw_set: 关键词集合。

    Returns:
        有意义关键词集合。
    """
    return {w for w in kw_set if len(w) > 3 or re.match(r'[\u4e00-\u9fff]', w)}


def _compute_weighted_jaccard(
    kw1: Set[str],
    kw2: Set[str],
    global_freq: Optional[Counter] = None,
) -> float:
    """计算带权重的 Jaccard 相似度。

    高频词（出现次数多）的权重更高，因为高频词更能代表话题核心。

    Args:
        kw1: 第一个关键词集合。
        kw2: 第二个关键词集合。
        global_freq: 全局关键词频率 Counter（若为 None，退化为标准 Jaccard）。

    Returns:
        0.0 ~ 1.0 的加权相似度。
    """
    if not kw1 or not kw2:
        return 0.0

    if global_freq is None:
        return jaccard_similarity(kw1, kw2)

    intersection = kw1 & kw2
    union = kw1 | kw2

    if not union:
        return 0.0

    # 带权：每个词的权重 = 1 + log(1 + freq)，高频词权重更高
    # 交集权重 = 共享词的权重和，并集权重 = 所有词的权重和
    max_freq = max(global_freq.values()) if global_freq else 1

    weight_intersection = sum(
        1 + (global_freq.get(w, 0) / max_freq) for w in intersection
    )
    weight_union = sum(
        1 + (global_freq.get(w, 0) / max_freq) for w in union
    )

    return weight_intersection / weight_union if weight_union > 0 else 0.0


def _extract_domain(url: str) -> str:
    """从 URL 中提取域名。

    Args:
        url: URL 字符串。

    Returns:
        域名，提取失败时返回 "unknown"。
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    except Exception:
        return "unknown"


def _build_global_frequency(items: List[Dict[str, Any]]) -> Counter:
    """构建全局关键词频率统计。

    Args:
        items: 条目列表。

    Returns:
        全局关键词频率 Counter。
    """
    freq: Counter = Counter()
    for item in items:
        title = item.get("title", "")
        if title:
            freq.update(extract_keywords(title))
    return freq


def _compute_dynamic_threshold(
    items: List[Dict[str, Any]],
    base_threshold: float = 0.35,
) -> float:
    """根据数据规模和多样性计算动态阈值。

    规则:
    - 数据量大（>50 条）且来源多样（>3 个）时，降低阈值（更容易聚类）
    - 数据量小（<10 条）时，提高阈值（避免过度聚类）
    - 其他情况使用基础阈值

    Args:
        items: 条目列表。
        base_threshold: 基础阈值。

    Returns:
        动态计算后的阈值。
    """
    num_items = len(items)
    num_sources = len({item.get("source", "unknown") for item in items})

    if num_items < 10:
        # 小数据集：提高阈值避免过度合并
        return min(0.5, base_threshold + 0.1)
    elif num_items > 50 and num_sources > 3:
        # 大数据集且来源多样：降低阈值
        return max(0.2, base_threshold - 0.05)
    elif num_items > 100:
        return max(0.15, base_threshold - 0.1)
    else:
        return base_threshold


def _should_keep_cross_domain(
    item: Dict[str, Any],
    cluster_sources: Set[str],
    cluster_domains: Set[str],
) -> bool:
    """判断是否应将跨域文章保留到聚类中。

    即使标题相似度很高，不同域名来源的文章也应被视为有价值的跨域信号。
    此函数检查 item 的域名是否已在聚类中出现。

    Args:
        item: 待检查的条目。
        cluster_sources: 聚类中已存在的来源（source 字段）集合。
        cluster_domains: 聚类中已存在的域名集合。
    """
    url = item.get("url", "")
    domain = _extract_domain(url)
    return domain not in cluster_domains


# ---------------------------------------------------------------
# 聚类主函数
# ---------------------------------------------------------------

def cross_source_cluster(
    items: List[Dict[str, Any]],
    threshold: float = 0.35,
    min_shared: int = 2,
    use_dynamic_threshold: bool = False,
    enable_weighted_jaccard: bool = False,
    enable_cross_domain_retention: bool = True,
) -> List[Dict[str, Any]]:
    """将不同源的相关新闻按标题关键词聚类，保留跨源话题。

    使用两层匹配:
    1. Jaccard > threshold（宽松）
    2. OR 共享有意义关键词 >= min_shared 个（长度>3 的英文/中文）

    Args:
        items: 采集条目列表，每项需包含 title、source 字段。
        threshold: Jaccard 相似度阈值（当 use_dynamic_threshold=False 时使用）。
        min_shared: 最小共享有意义关键词数。
        use_dynamic_threshold: 是否根据数据规模动态调整阈值（默认 False）。
        enable_weighted_jaccard: 是否使用带权重的 Jaccard 计算（默认 False）。
        enable_cross_domain_retention: 是否启用跨域保留（默认 True）。

    Returns:
        跨源话题列表，按 item_count 降序，最多 10 个。
        每项包含:
        - topic: 话题标签（高频关键词组合）
        - sources: 来源列表
        - item_count: 条目数
        - sample_titles: 前 3 条标题
        - urls: 前 3 条 URL
    """
    if not items:
        return []

    # 从配置读取阈值
    dedup_config = get_dedup_config()
    if use_dynamic_threshold:
        threshold = _compute_dynamic_threshold(
            items,
            base_threshold=threshold,
        )

    # 构建全局词频（用于加权 Jaccard）
    global_freq = _build_global_frequency(items) if enable_weighted_jaccard else None

    # 为每条 item 提取关键词
    item_kws: List[Tuple[Dict[str, Any], Set[str]]] = [
        (item, extract_keywords(item.get("title", ""))) for item in items
    ]

    clusters: List[Dict[str, Any]] = []

    for item, kw in item_kws:
        if not kw:
            continue

        m_kw = _meaningful(kw)
        merged = False

        for cluster in clusters:
            # 双重匹配: Jaccard 或 关键词重叠
            if enable_weighted_jaccard:
                jacc = _compute_weighted_jaccard(kw, cluster["kw_set"], global_freq)
            else:
                jacc = jaccard_similarity(kw, cluster["kw_set"])

            shared = len(m_kw & _meaningful(cluster["kw_set"]))

            # 应用动态阈值
            effective_threshold = threshold

            if jacc > effective_threshold or shared >= min_shared:
                # 跨域保留：如果 item 来自新域名，记录但不阻止合并
                url = item.get("url", "")
                domain = _extract_domain(url)

                cluster["items"].append(item)
                cluster["kw_set"] |= kw
                cluster["sources"].add(item.get("source", "unknown"))
                cluster["domains"].add(domain)
                merged = True
                break

        if not merged:
            url = item.get("url", "")
            domain = _extract_domain(url)
            clusters.append({
                "items": [item],
                "kw_set": kw.copy(),
                "sources": {item.get("source", "unknown")},
                "domains": {domain},
            })

    # 只保留跨源（>=2 不同源）的 cluster
    signals: List[Dict[str, Any]] = []
    for c in clusters:
        if len(c["sources"]) >= 2:
            # 从 items 中提取高频词作为 topic label
            all_title_kw: List[str] = []
            for it in c["items"]:
                all_title_kw.extend(extract_keywords(it.get("title", "")))
            top_kw = Counter(all_title_kw).most_common(3)
            label = " / ".join(kw for kw, _ in top_kw) if top_kw else "unknown"

            signals.append({
                "topic": label,
                "sources": sorted(c["sources"]),
                "item_count": len(c["items"]),
                "sample_titles": [it["title"] for it in c["items"][:3]],
                "urls": [it["url"] for it in c["items"][:3]],
            })

    # 按 item_count 降序
    signals.sort(key=lambda s: s["item_count"], reverse=True)
    return signals[:10]
