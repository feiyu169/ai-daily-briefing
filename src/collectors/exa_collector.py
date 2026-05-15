"""
Exa 采集器模块
==============
通过 Exa API 采集 AI 相关新闻，查询配置从 config.yaml 动态加载。

支持以下查询分组（需在 config.yaml queries 字段中定义）：
  - en_queries       : 英文 AI 新闻
  - cn_queries       : 中文 AI 生态新闻
  - official_queries : 大厂官方动态
  - arxiv_queries    : 学术前沿论文
  - discussion_queries: HN / Reddit 讨论
  - chip_queries     : 芯片 / 半导体专项
  - robot_queries    : 机器人 / 具身智能专项

Usage:
    from src.collectors.exa_collector import collect_exa

    results = collect_exa()
    # results: List[Dict] 每条含 title/url/source/published/snippet/query_group/category
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from exa_py import Exa

from src.utils.config import get_queries, get_collector_config
from src.utils.security import sanitize_error_message
from src.processors.classifier import classify_item

logger = logging.getLogger(__name__)


def _flatten_queries(queries_cfg: Dict[str, Any]) -> List[Tuple[str, int]]:
    """将 config.yaml 中的 queries 分组展平为 (query_str, num) 列表。

    Args:
        queries_cfg: get_queries() 返回的完整查询配置字典。

    Returns:
        所有分组的查询列表，每项为 (查询关键词, 结果数量)。
    """
    # 动态发现所有查询分组（排除非查询配置项）
    exclude_keys = {"github_queries", "trending_queries"}  # 这些由其他采集器处理
    
    flat: List[Tuple[str, int]] = []
    for group_name, entries in queries_cfg.items():
        if group_name in exclude_keys:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            query = entry.get("query", "").strip()
            num = int(entry.get("num", 5))
            if query:
                flat.append((query, num))
    return flat


def _infer_source_tag(query: str) -> str:
    """根据查询字符串推断文章来源标签。

    Args:
        query: 查询关键词。

    Returns:
        来源标签: discussion / official / research / news 之一。
    """
    q_lower = query.lower()
    if "ycombinator" in q_lower or "reddit" in q_lower or "hacker news" in q_lower:
        return "discussion"
    if "openai.com" in q_lower or "anthropic.com" in q_lower or "deepmind" in q_lower:
        return "official"
    if "arxiv" in q_lower or "\u8bba\u6587" in q_lower:  # 论文
        return "research"
    return "news"


def _execute_exa_search(
    exa: Exa,
    query: str,
    num: int,
    yesterday: str,
    query_label: str,
    seen_urls: Set[str],
    seen_urls_lock: threading.Lock = None,
) -> List[Dict[str, Any]]:
    """执行单个 Exa 查询并处理结果。

    共享函数，被 collect_exa() 和 collect_exa_from_group() 共用。

    Args:
        exa: Exa 客户端实例。
        query: 查询关键词。
        num: 结果数量。
        yesterday: 日期锚点 (YYYY-MM-DD)。
        query_label: 查询分组标签（用于结果标注）。
        seen_urls: 已见 URL 集合（线程共享时由调用方控制锁）。
        seen_urls_lock: 可选的线程锁，保护 seen_urls 的并发安全。

    Returns:
        本查询的采集结果列表。
    """
    try:
        results = exa.search(
            query,
            num_results=num,
            type="neural",
            start_published_date=yesterday,
        )
    except Exception as e:
        logger.warning(
            "Exa 查询失败: %s... -> %s", query[:30], sanitize_error_message(str(e))
        )
        return []

    query_results: List[Dict[str, Any]] = []
    for r in results.results:
        url: str = r.url or ""

        # 线程安全地检查和添加 URL
        if seen_urls_lock:
            with seen_urls_lock:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
        else:
            if url in seen_urls:
                continue
            seen_urls.add(url)

        # 基础字段
        title: str = r.title or ""
        snippet: str = (r.text or "")[:400]

        # 日期校验
        raw_date = r.published_date
        published_str: str = str(raw_date)[:10] if raw_date else "unknown"
        if published_str in ("unknown", "") or published_str < yesterday:
            continue

        # 来源标签 + 分类
        source_tag: str = _infer_source_tag(query)
        category: str = classify_item(title, snippet)

        query_results.append({
            "title": title,
            "url": url,
            "source": source_tag,
            "published": published_str,
            "snippet": snippet,
            "query_group": query_label,
            "category": category,
        })

    return query_results


def collect_exa() -> List[Dict[str, Any]]:
    """执行 Exa 采集，返回去重后的结果列表。

    从 config.yaml 加载所有查询分组（含 chip_queries / robot_queries），
    调用 Exa neural search 获取昨日发布的文章，跳过已见 URL 和无效日期条目，
    并对每条结果标注 source / query_group / category。

    Returns:
        采集结果列表。每项格式::

            {
                "title":       str,
                "url":         str,
                "source":      str,       # discussion / official / research / news
                "published":   str,       # "YYYY-MM-DD" 或 "unknown"
                "snippet":     str,       # 前 400 字符摘要
                "query_group": str,       # 来源查询前 30 字符
                "category":    str,       # classify_item 分类结果
            }

    Raises:
        Exception: Exa 客户端初始化失败或 API 调用异常，由调用方处理。
    """
    # --- 配置加载 ---
    queries_cfg = get_queries()
    get_collector_config()

    # --- API 配额检查 ---
    from src.utils.quota import get_degradation_strategy, record_api_call, log_quota_status
    log_quota_status("exa")
    degradation = get_degradation_strategy("exa")
    if degradation["should_degrade"]:
        logger.warning(degradation["message"])

    # --- 初始化 Exa 客户端 ---
    from src.utils.security import get_api_key
    api_key = get_api_key("EXA_API_KEY", required=True)
    if not api_key:
        return []

    exa = Exa(api_key=api_key)

    yesterday: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # --- 展平所有查询 ---
    all_queries: List[Tuple[str, int]] = _flatten_queries(queries_cfg)
    if not all_queries:
        logger.warning("config.yaml 中未找到有效的 Exa 查询配置")
        return []

    # --- 降级处理：减少查询数量 ---
    if degradation["should_degrade"]:
        reduction_ratio = degradation["reduction_ratio"]
        original_count = len(all_queries)
        keep_count = max(1, int(original_count * (1 - reduction_ratio)))
        all_queries = all_queries[:keep_count]
        logger.warning(f"降级模式: 查询从 {original_count} 条减少到 {keep_count} 条")

    logger.info("Exa 采集启动: %d 条查询, 日期锚点 %s", len(all_queries), yesterday)

    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()
    seen_urls_lock = threading.Lock()  # 保护 seen_urls 的线程安全

    # --- 并行执行查询 ---
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def _execute_query(query_num: tuple) -> List[Dict[str, Any]]:
        """执行单个查询（线程池内部使用）"""
        query, num = query_num
        query_results = _execute_exa_search(
            exa, query, num, yesterday, query[:30], seen_urls, seen_urls_lock,
        )
        if query_results:
            # --- 记录 API 调用 ---
            record_api_call("exa", 1)
        return query_results
    
    # 使用线程池并行执行
    max_workers = min(5, len(all_queries))  # 最多 5 个并发
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_execute_query, q): q for q in all_queries}
        for future in as_completed(futures):
            try:
                query_results = future.result(timeout=30)
                all_results.extend(query_results)
            except Exception as e:
                query = futures[future]
                logger.warning("Exa 查询超时或失败: %s... -> %s", query[0][:30], sanitize_error_message(str(e)))

    logger.info(
        "Exa 采集完成: 共收集 %d 条结果 (来自 %d 条查询)",
        len(all_results),
        len(all_queries),
    )
    return all_results


def collect_exa_from_group(group_name: str) -> List[Dict[str, Any]]:
    """仅采集指定分组的数据。

    Args:
        group_name: 分组名，如 ``chip_queries``、``robot_queries``。

    Returns:
        采集结果列表，格式与 collect_exa() 一致。
    """
    queries_cfg = get_queries()
    entries = queries_cfg.get(group_name, [])
    if not entries:
        logger.warning("查询分组 %s 未找到或为空", group_name)
        return []

    from src.utils.security import get_api_key
    api_key = get_api_key("EXA_API_KEY", required=True)
    if not api_key:
        return []

    exa = Exa(api_key=api_key)
    yesterday: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for entry in entries:
        query: str = entry.get("query", "").strip()
        num: int = int(entry.get("num", 5))
        if not query:
            continue

        query_results = _execute_exa_search(
            exa, query, num, yesterday, query[:30], seen_urls,
        )
        results.extend(query_results)

    return results
