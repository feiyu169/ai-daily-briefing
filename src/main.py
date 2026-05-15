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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .collectors.exa_collector import collect_exa
from .collectors.github_collector import collect_github
from .collectors.trending_collector import collect_github_trending
from .processors.classifier import classify_item
from .processors.dedup import dedup_and_filter
from .processors.trends import detect_trend_keywords, get_trend_momentum
from .processors.cross_source import cross_source_cluster
from .utils.config import get_config, get_collector_config, get_output_config
from .utils.file_utils import (
    load_url_history,
    save_url_history,
    load_trends_history,
    save_trends_history,
)
from .utils.logger import logger


def main() -> None:
    """主入口函数"""
    # 校验必需环境变量
    exa_api_key = os.environ.get("EXA_API_KEY", "")
    if not exa_api_key:
        logger.error("EXA_API_KEY 未设置，请 export EXA_API_KEY=xxx")
        sys.exit(1)

    # 获取配置
    config = get_config()
    collector_config = get_collector_config()
    output_config = get_output_config()
    
    cache_file = output_config.get("cache_file", "/tmp/collector_output.json")
    history_file = output_config.get("history_file", "/tmp/collector_url_history.json")
    trends_file = output_config.get("trends_file", "/tmp/collector_trends_history.json")
    cache_ttl = collector_config.get("cache_ttl", 1800)
    history_days = collector_config.get("history_days", 7)
    trends_days = collector_config.get("trends_days", 3)
    query_timeout = collector_config.get("query_timeout", 60)

    # 快速路径: 缓存复用
    if os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < cache_ttl:
            logger.info(f"使用缓存数据 ({age:.0f}s 前)")
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            print(json.dumps(cached, ensure_ascii=False))
            sys.exit(0)

    ts = datetime.now().isoformat()
    logger.info(f"v6 开始采集 {ts}")

    # 加载历史
    url_history = load_url_history(history_file, history_days)
    trends_history = load_trends_history(trends_file, trends_days)
    logger.info(f"历史URL: {len(url_history)}, 历史趋势词: {len(trends_history)}")

    all_data: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}

    # 采集所有源
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

    # 输出
    output = {
        "collected_at": ts,
        "date": today,
        "total_items": len(merged),
        "source_counts": source_counts,
        "category_counts": dict(category_counts),
        "trend_momentum": {
            "continuing": list(continuing_trends)[:15],
            "new": list(new_trends)[:15],
        },
        "cross_platform_signals": cross_signals,
        "items": merged,
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
