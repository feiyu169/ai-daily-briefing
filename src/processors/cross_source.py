"""
跨源聚类模块
============
将不同源的相关新闻按标题关键词聚类，保留跨源话题
"""

import re
from collections import Counter
from typing import Any, Dict, List, Set, Tuple

from .dedup import extract_keywords, jaccard_similarity


def _meaningful(kw_set: Set[str]) -> Set[str]:
    """筛选有意义关键词（>3字符 或 中文）"""
    return {w for w in kw_set if len(w) > 3 or re.match(r'[\u4e00-\u9fff]', w)}


def cross_source_cluster(
    items: List[Dict[str, Any]],
    threshold: float = 0.35,
    min_shared: int = 2,
    use_dynamic_threshold: bool = False,
) -> List[Dict[str, Any]]:
    """将不同源的相关新闻按标题关键词聚类，保留跨源话题
    
    使用两层匹配:
    1. Jaccard > threshold (宽松)
    2. OR 共享有意义关键词 >= min_shared 个 (长度>3 的英文/中文)
    
    Args:
        items: 采集条目列表
        threshold: Jaccard 相似度阈值（当 use_dynamic_threshold=False 时使用）
        min_shared: 最小共享关键词数
        use_dynamic_threshold: 是否使用动态阈值（默认 False，保持向后兼容）
        
    Returns:
        跨源话题列表，按 item_count 降序
    """
    # 为每条 item 提取关键词
    item_kws: List[Tuple[Dict[str, Any], Set[str]]] = [
        (item, extract_keywords(item.get("title", ""))) for item in items
    ]

    clusters: List[Dict[str, Any]] = []  # list of {"items": [...], "kw_set": set, "sources": set}

    for item, kw in item_kws:
        if not kw:
            continue
        m_kw = _meaningful(kw)
        merged = False
        for cluster in clusters:
            # 双重匹配: Jaccard 或 关键词重叠
            jacc = jaccard_similarity(kw, cluster["kw_set"])
            shared = len(m_kw & _meaningful(cluster["kw_set"]))
            if jacc > threshold or shared >= min_shared:
                cluster["items"].append(item)
                cluster["kw_set"] |= kw
                cluster["sources"].add(item.get("source", "unknown"))
                merged = True
                break
        if not merged:
            clusters.append({
                "items": [item],
                "kw_set": kw.copy(),
                "sources": {item.get("source", "unknown")},
            })

    # 只保留跨源 (>=2 不同源) 的 cluster
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
