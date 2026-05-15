"""
AI Daily Briefing v6 — 主入口
==============================
协调采集器、处理器和输出
"""

import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .collectors.exa_collector import collect_exa
from .collectors.github_collector import collect_github
from .collectors.trending_collector import collect_github_trending
from .processors.dedup import dedup_and_filter
from .processors.trends import detect_trend_keywords
from .processors.cross_source import cross_source_cluster
from .utils.config import get_collector_config, get_output_config
from .utils.file_utils import (
    load_url_history,
    save_url_history,
    load_trends_history,
    save_trends_history,
)
from .utils.logger import logger


def _load_cache(cache_file: str, cache_ttl: int) -> Optional[Dict[str, Any]]:
    """加载缓存，如果有效则返回缓存数据，否则返回 None。

    Args:
        cache_file: 缓存文件路径。
        cache_ttl: 缓存有效期（秒）。

    Returns:
        如果缓存存在且未过期，返回缓存字典；否则返回 None。
    """
    if not os.path.exists(cache_file):
        return None

    age = time.time() - os.path.getmtime(cache_file)
    if age >= cache_ttl:
        return None

    logger.info(f"使用缓存数据 ({age:.0f}s 前)")
    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_all(query_timeout: int) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """执行所有采集器，收集多源数据。

    对每个采集器使用独立的 ThreadPoolExecutor 进行超时控制。

    Args:
        query_timeout: 每个采集器的超时秒数。

    Returns:
        (all_data, source_counts) 二元组：
        - all_data: 所有采集器返回的数据条目列表。
        - source_counts: 每个采集器的名称到条目数的映射。
    """
    all_data: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}

    collectors = [
        ("Exa", collect_exa),
        ("GitHub", collect_github),
        ("GitHub_Trending", collect_github_trending),
    ]

    for name, fn in collectors:
        logger.info(f"采集 {name}...")
        t0 = time.time()
        try:
            with ThreadPoolExecutor(max_workers=1) as timeout_pool:
                future = timeout_pool.submit(fn)
                d = future.result(timeout=query_timeout)
            elapsed = time.time() - t0
            logger.info(f"{name}: {len(d)} 条 ({elapsed:.1f}s)")
            source_counts[name.lower()] = len(d)
            all_data.extend(d)
        except TimeoutError:
            elapsed = time.time() - t0
            logger.warning(f"{name} 超时 ({elapsed:.1f}s)")
            source_counts[name.lower()] = 0
        except Exception as e:
            elapsed = time.time() - t0
            logger.warning(f"{name} 失败 ({elapsed:.1f}s): {e}")
            source_counts[name.lower()] = 0

    return all_data, source_counts


def _process_data(
    all_data: List[Dict[str, Any]],
    url_history: Dict[str, str],
    trends_history: Dict[str, str],
    history_file: str,
    trends_file: str,
    history_days: int,
    trends_days: int,
) -> Dict[str, Any]:
    """处理数据：去重、趋势检测、跨源聚类、分类统计。

    副作用：更新 url_history 和 trends_history 并持久化到磁盘。

    Args:
        all_data: 原始采集数据条目列表。
        url_history: URL 历史字典（url -> 日期）。
        trends_history: 趋势词历史字典（关键词 -> 首次出现日期）。
        history_file: URL 历史持久化文件路径。
        trends_file: 趋势历史持久化文件路径。
        history_days: URL 历史保留天数。
        trends_days: 趋势历史保留天数。

    Returns:
        包含所有处理结果的输出字典。
    """
    ts = datetime.now().isoformat()

    # 去噪 + 语义去重
    merged = dedup_and_filter(all_data, url_history)
    logger.info(f"去重后: {len(merged)} 条")

    # 趋势 momentum 追踪
    today_keywords = detect_trend_keywords(merged)
    # 判断哪些是延续趋势（昨天就存在的），哪些是新出现
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    old_trends = {kw for kw, dt in trends_history.items() if dt <= yesterday_str}
    continuing_trends = today_keywords & old_trends
    new_trends = today_keywords - old_trends
    save_trends_history(trends_file, trends_history, today_keywords, trends_days)

    # 跨源聚类
    cross_signals = cross_source_cluster(merged)
    if cross_signals:
        logger.info(f"跨源话题: {len(cross_signals)} 个")

    # 按类别统计
    category_counts = Counter(item.get("category", "未分类") for item in merged)

    # 更新 URL 历史
    today = datetime.now().strftime("%Y-%m-%d")
    for item in merged:
        if item.get("url"):
            url_history[item["url"]] = today
    save_url_history(history_file, url_history)

    return {
        "collected_at": ts,
        "date": today,
        "total_items": len(merged),
        "source_counts": {},
        "category_counts": dict(category_counts),
        "trend_momentum": {
            "continuing": list(continuing_trends)[:15],
            "new": list(new_trends)[:15],
        },
        "cross_platform_signals": cross_signals,
        "items": merged,
    }


def _save_output(output: Dict[str, Any], cache_file: str) -> None:
    """保存输出到缓存文件和 stdout。

    Args:
        output: 要保存的输出字典。
        cache_file: 缓存文件路径。
    """
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    """主入口函数 — 协调子流程。

    流程：
    1. 校验必需的环境变量
    2. 加载配置
    3. 确保缓存目录存在
    4. 尝试加载缓存（快速路径）
    5. 加载历史数据
    6. 采集多源数据
    7. 处理数据（去重、趋势、聚类）
    8. 保存输出
    """
    # 校验必需环境变量
    from src.utils.security import get_api_key

    get_api_key("EXA_API_KEY", required=True)

    # 获取配置
    collector_config = get_collector_config()
    output_config = get_output_config()

    cache_file = output_config.get("cache_file", ".cache/collector_output.json")
    history_file = output_config.get("history_file", ".cache/collector_url_history.json")
    trends_file = output_config.get("trends_file", ".cache/collector_trends_history.json")
    cache_ttl = collector_config.get("cache_ttl", 1800)
    history_days = collector_config.get("history_days", 7)
    trends_days = collector_config.get("trends_days", 3)
    query_timeout = collector_config.get("query_timeout", 60)

    # 确保缓存目录存在
    cache_dir = os.path.dirname(cache_file)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)

    # 快速路径: 缓存复用
    cached = _load_cache(cache_file, cache_ttl)
    if cached is not None:
        print(json.dumps(cached, ensure_ascii=False))
        sys.exit(0)

    ts = datetime.now().isoformat()
    logger.info(f"v6 开始采集 {ts}")

    # 加载历史
    url_history = load_url_history(history_file, history_days)
    trends_history = load_trends_history(trends_file, trends_days)
    logger.info(f"历史URL: {len(url_history)}, 历史趋势词: {len(trends_history)}")

    # 采集所有源
    all_data, source_counts = _collect_all(query_timeout)

    # 处理数据
    output = _process_data(
        all_data,
        url_history,
        trends_history,
        history_file,
        trends_file,
        history_days,
        trends_days,
    )
    # 注入 source_counts（_process_data 无法访问）
    output["source_counts"] = source_counts

    # 保存输出
    _save_output(output, cache_file)


if __name__ == "__main__":
    main()
