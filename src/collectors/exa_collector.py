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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from exa_py import Exa

from src.utils.config import get_queries, get_collector_config
from src.processors.classifier import classify_item

logger = logging.getLogger(__name__)


def _flatten_queries(queries_cfg: Dict[str, Any]) -> List[Tuple[str, int]]:
    """将 config.yaml 中的 queries 分组展平为 (query_str, num) 列表。

    Args:
        queries_cfg: get_queries() 返回的完整查询配置字典。

    Returns:
        所有分组的查询列表，每项为 (查询关键词, 结果数量)。
    """
    # 定义参与 Exa 采集的分组名（按期望顺序排列）
    groups = [
        "en_queries",
        "cn_queries",
        "official_queries",
        "arxiv_queries",
        "discussion_queries",
        "chip_queries",
        "robot_queries",
    ]

    flat: List[Tuple[str, int]] = []
    for group in groups:
        entries = queries_cfg.get(group, [])
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
    if "arxiv" in q_lower or "论文" in q_lower:
        return "research"
    return "news"


def _init_exa_client(api_key: str) -> Optional[Exa]:
    """初始化 Exa 客户端。

    Args:
        api_key: Exa API 密钥。

    Returns:
        初始化成功的 Exa 客户端实例，如果密钥为空则返回 None。
    """
    if not api_key:
        return None
    return Exa(api_key=api_key)


def _execute_single_query(
    exa: Exa,
    query: str,
    num: int,
    yesterday: str,
    seen_urls: set,
) -> List[Dict[str, Any]]:
    """执行单个 Exa neural search 查询并返回有效结果。

    对返回结果执行以下处理：
      - 根据 seen_urls 进行 URL 去重
      - 校验发布日期（仅保留昨日及之后的条目）
      - 推断 source_tag
      - 调用 classify_item 获取 category

    Args:
        exa: 已初始化的 Exa 客户端。
        query: 查询关键词。
        num: 期望结果数量。
        yesterday: 发布日期过滤锚点 (YYYY-MM-DD)。
        seen_urls: 已见 URL 集合（函数内会直接修改）。

    Returns:
        符合条件的结果列表，每项格式与 collect_exa() 一致。
    """
    response = exa.search(
        query,
        num_results=num,
        type="neural",
        start_published_date=yesterday,
    )

    items: List[Dict[str, Any]] = []
    source_tag: str = _infer_source_tag(query)
    group_label: str = query[:30]

    for r in response.results:
        url: str = r.url or ""
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title: str = r.title or ""
        snippet: str = (r.text or "")[:400]

        raw_date = r.published_date
        published_str: str = str(raw_date)[:10] if raw_date else "unknown"
        if published_str in ("unknown", "") or published_str < yesterday:
            continue

        category: str = classify_item(title, snippet)

        items.append({
            "title": title,
            "url": url,
            "source": source_tag,
            "published": published_str,
            "snippet": snippet,
            "query_group": group_label,
            "category": category,
        })

    return items


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

    # --- 初始化 Exa 客户端 ---
    from src.utils.security import get_api_key
    api_key = get_api_key("EXA_API_KEY", required=True)
    exa = _init_exa_client(api_key)
    if exa is None:
        return []

    yesterday: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # --- 展平所有查询 ---
    all_queries: List[Tuple[str, int]] = _flatten_queries(queries_cfg)
    if not all_queries:
        logger.warning("config.yaml 中未找到有效的 Exa 查询配置")
        return []

    logger.info("Exa 采集启动: %d 条查询, 日期锚点 %s", len(all_queries), yesterday)

    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for query, num in all_queries:
        try:
            items = _execute_single_query(exa, query, num, yesterday, seen_urls)
            all_results.extend(items)
        except Exception as e:
            logger.warning("Exa 查询失败: %s... -> %s", query[:30], e)

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

    from src.utils.config import get_config
    cfg = get_config()
    api_key: str = cfg.get("exa_api_key", "")

    exa = _init_exa_client(api_key)
    if exa is None:
        logger.error("EXA_API_KEY 未配置")
        return []

    yesterday: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for entry in entries:
        query: str = entry.get("query", "").strip()
        num: int = int(entry.get("num", 5))
        if not query:
            continue

        try:
            items = _execute_single_query(exa, query, num, yesterday, seen_urls)
            results.extend(items)
        except Exception as e:
            logger.warning("Exa 查询失败 [%s]: %s... -> %s", group_name, query[:30], e)

    return results
