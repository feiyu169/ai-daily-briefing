"""
因果链分析模块
==============
从跨源聚类结果中识别因果链条（事件 A → 事件 B → 事件 C）。

因果链检测逻辑:
1. 按时间排序的事件中，存在关键词递进（前序事件的结论词出现在后序事件标题中）
2. 同一个"主题链"上的事件，关键词存在渐进式变化
3. 来源之间的相互引用线索（如 "according to"、"reports"）
"""

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from .dedup import extract_keywords


# 因果指示词 — 表示前序事件可能触发后序事件
CAUSAL_INDICATORS: Set[str] = {
    "because", "due to", "as a result", "leads to", "leading to",
    "triggers", "triggered", "sparks", "sparked", "prompts", "prompted",
    "fuels", "fueled", "drives", "driven", "causes", "caused",
    "results in", "resulting in", "follows", "followed", "following",
    "responding to", "in response", "after", "subsequently",
    "因此", "导致", "引发", "推动", "促使", "随之", "后续",
    "回应", "响应", "继", "随后", "受此影响",
}


def _extract_causal_pairs(
    items: List[Dict[str, Any]],
    time_window_hours: int = 48,
) -> List[Dict[str, Any]]:
    """从条目列表中提取可能的因果对。

    检测逻辑：
    1. 对 item 按时间排序
    2. 对每对 (earlier, later)，检查：
       a. 时间差 <= time_window_hours
       b. later 的标题包含 earlier 的关键实体词
       c. later 的标题包含因果指示词

    Args:
        items: 条目列表，每项需包含 title 和 published（YYYY-MM-DD 或 ISO 格式）字段。
        time_window_hours: 因果对的最大时间窗口（小时）。

    Returns:
        因果对列表，每项包含 ``earlier``、``later``、``confidence``、``reason``。
    """
    # 排除无日期的条目
    dated_items: List[Tuple[datetime, Dict[str, Any]]] = []
    for item in items:
        pub = item.get("published", "")
        if not pub or pub == "unknown":
            continue
        try:
            dt = datetime.fromisoformat(pub) if "T" in pub else datetime.strptime(pub, "%Y-%m-%d")
            dated_items.append((dt, item))
        except (ValueError, TypeError):
            continue

    dated_items.sort(key=lambda x: x[0])  # 按时间升序

    pairs: List[Dict[str, Any]] = []

    for i in range(len(dated_items)):
        dt_i, item_i = dated_items[i]
        kw_i = extract_keywords(item_i.get("title", ""))
        # 取关键词中较长（更具实体性）的部分
        entities_i = {w for w in kw_i if len(w) > 4 or re.match(r'[\u4e00-\u9fff]', w)}

        for j in range(i + 1, len(dated_items)):
            dt_j, item_j = dated_items[j]
            delta = (dt_j - dt_i).total_seconds()
            if delta > time_window_hours * 3600:
                continue  # 超过时间窗口，因为有序所以可以 break

            title_j = item_j.get("title", "").lower()
            kw_j = extract_keywords(title_j)

            # 检查实体延续: later 标题包含 earlier 的实体词
            shared_entities = entities_i & kw_j

            # 检查因果指示词
            has_indicator = any(ind in title_j for ind in CAUSAL_INDICATORS)

            if shared_entities and has_indicator:
                # 计算置信度
                confidence = 0.5 + 0.1 * min(len(shared_entities), 3)
                # 时间越近置信度越高
                hours_diff = delta / 3600
                confidence -= 0.05 * (hours_diff / time_window_hours)
                confidence = max(0.3, min(1.0, confidence))

                pairs.append({
                    "earlier": item_i,
                    "later": item_j,
                    "confidence": round(confidence, 2),
                    "reason": f"实体共享: {', '.join(sorted(shared_entities)[:3])}; "
                              f"后序标题含因果指示词",
                    "shared_entities": sorted(shared_entities),
                    "time_gap_hours": round(hours_diff, 1),
                })

    # 按置信度降序
    pairs.sort(key=lambda p: p["confidence"], reverse=True)
    return pairs


def _build_chain(pairs: List[Dict], min_chain_length: int = 3) -> List[Dict]:
    """从因果对构建因果链。

    Args:
        pairs: 因果对列表。
        min_chain_length: 链的最小长度（事件数）。

    Returns:
        因果链列表，每项包含 ``events``、``confidence``、``summary``。
    """
    # 构建邻接表: earlier -> [(later, pair)]
    graph: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)
    for pair in pairs:
        earlier_id = id(pair["earlier"])
        later_id = id(pair["later"])
        graph[earlier_id].append((later_id, pair))

    # DFS 找路径
    chains: List[Dict] = []

    def dfs(current: int, path: List[Dict], visited: Set[int]) -> None:
        # 深度限制：防止指数级爆炸
        if len(path) >= 10:
            return
        
        # path 中的每个 pair 增加一个事件，加上起始事件 = len(path) + 1 个事件
        if len(path) + 1 >= min_chain_length:
            chains.append({
                "events": [p["earlier" if i == 0 else "later"] for i, p in enumerate(path)]
                       + [path[-1]["later"]],
                "pairs": path.copy(),
                "confidence": round(sum(p["confidence"] for p in path) / len(path), 2),
                "length": len(path) + 1,
            })

        for neighbor, pair in graph.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(pair)
                dfs(neighbor, path, visited)
                path.pop()
                visited.remove(neighbor)

    for start in graph:
        dfs(start, [], {start})

    # 合并没有重叠的链，按置信度排序
    # 去重：如果两条链共享 70%+ 的事件，保留置信度更高的
    deduped: List[Dict] = []
    for chain in sorted(chains, key=lambda c: c["confidence"], reverse=True):
        events_set = {id(e) for e in chain["events"]}
        is_dup = False
        for existing in deduped:
            existing_set = {id(e) for e in existing["events"]}
            overlap = len(events_set & existing_set)
            min_len = min(len(events_set), len(existing_set))
            if min_len > 0 and overlap / min_len >= 0.7:
                is_dup = True
                break
        if not is_dup:
            # 生成摘要
            titles = [e.get("title", "")[:60] for e in chain["events"]]
            chain["summary"] = " → ".join(titles)
            deduped.append(chain)

    return deduped[:5]  # 最多返回 5 条链


def detect_causal_chains(
    items: List[Dict[str, Any]],
    time_window_hours: int = 48,
    min_chain_length: int = 3,
    max_chains: int = 5,
) -> List[Dict[str, Any]]:
    """检测跨源事件的因果链。

    从条目列表中找出时间上递进、实体延续且包含因果指示词的事件链。

    Args:
        items: 条目列表，每项需包含 title、published、source 字段。
        time_window_hours: 因果对的时间窗口（小时，默认 48）。
        min_chain_length: 链的最少事件数（默认 3）。
        max_chains: 返回的最大链条数（默认 5）。

    Returns:
        因果链列表，按置信度降序。每条链包含:
        - events: 事件列表（按时间排序）
        - pairs: 因果对列表
        - confidence: 链的平均置信度 (0.0 ~ 1.0)
        - summary: 链摘要（标题用 → 连接）
        - length: 事件数量
    """
    if len(items) < min_chain_length:
        return []

    pairs = _extract_causal_pairs(items, time_window_hours=time_window_hours)
    if not pairs:
        return []

    chains = _build_chain(pairs, min_chain_length=min_chain_length)
    return chains[:max_chains]
