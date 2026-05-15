"""
GitHub Trending 采集器
======================
通过 Exa API 搜索 GitHub 上今日 star 暴涨的 AI 相关仓库，
从 config.yaml 加载查询配置，支持类型注解与结构化日志。

Usage:
    from src.collectors.trending_collector import collect_github_trending

    results = collect_github_trending()
    # -> [{"title", "url", "source", "published", "snippet", "query_group", "category"}, ...]
"""

import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List

from exa_py import Exa

from src.processors.classifier import classify_item
from src.utils.config import get_queries
from src.utils.security import sanitize_error_message

logger = logging.getLogger("ai_daily_briefing.collectors.trending")


def collect_github_trending() -> List[Dict[str, Any]]:
    """采集 GitHub Trending 仓库。

    通过 Exa Neural Search 搜索 GitHub 上今日 star 暴涨或热门的 AI 相关仓库。
    查询语句从 ``config.yaml`` 的 ``queries.trending_queries`` 字段加载，
    过滤条件包括：

    - URL 必须包含 ``github.com``
    - URL path 必须恰好有两段（即仓库级链接，过滤 commit/PR/release/wiki）
    - 发布日期必须为昨天或今天（在 Exa 的 ``start_published_date`` 基础上二次校验）

    Returns:
        采集结果列表，每项包含::

            {
                "title":        str,   # 仓库标题
                "url":          str,   # GitHub 仓库 URL
                "source":       str,   # 固定为 "github_trending"
                "published":    str,   # 发布日期 "YYYY-MM-DD"
                "snippet":      str,   # 摘要（前 400 字符）
                "query_group":  str,   # 固定为 "github_trending_exa"
                "category":     str,   # 自动分类结果
            }

        无结果时返回空列表。
    """
    # --- 加载配置 ---
    queries_config: Dict[str, Any] = get_queries()
    trending_queries: List[Dict[str, Any]] = queries_config.get("trending_queries", [])

    if not trending_queries:
        # 兜底：若 config.yaml 中无 trending_queries，使用硬编码默认值
        trending_queries = [
            {"query": "site:github.com trending AI machine learning stars today", "num": 8},
            {"query": "site:github.com trending LLM agent framework popular", "num": 6},
        ]
        logger.warning("config.yaml 中未找到 queries.trending_queries，使用默认查询")

    # --- 初始化 Exa ---
    from src.utils.security import get_api_key
    exa_api_key = get_api_key("EXA_API_KEY", required=False)
    if not exa_api_key:
        logger.warning("EXA_API_KEY 未配置，跳过 GitHub Trending 采集")
        return []

    exa = Exa(api_key=exa_api_key)
    yesterday: str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    results: List[Dict[str, Any]] = []

    # --- 执行查询 ---
    for entry in trending_queries:
        query: str = entry.get("query", "")
        num: int = entry.get("num", 5)

        if not query:
            continue

        try:
            r = exa.search(
                query,
                num_results=num,
                type="neural",
                start_published_date=yesterday,
            )

            for item in r.results:
                url: str = item.url or ""

                # 过滤：必须为 github.com 链接
                if "github.com" not in url:
                    continue

                # 过滤：只保留仓库级 URL（owner/repo），排除 commit/PR/release/wiki
                path_parts = urllib.parse.urlparse(url).path.strip("/").split("/")
                if len(path_parts) != 2:
                    continue

                snippet: str = (item.text or "")[:400]
                title: str = item.title or ""

                # 日期二次校验
                published_str: str = (
                    str(item.published_date)[:10]
                    if item.published_date
                    else "unknown"
                )
                if published_str in ("unknown", "") or published_str < yesterday:
                    continue

                results.append({
                    "title": title,
                    "url": url,
                    "source": "github_trending",
                    "published": published_str,
                    "snippet": snippet,
                    "query_group": "github_trending_exa",
                    "category": classify_item(title, snippet),
                })

        except Exception as e:
            logger.warning("GitHub Trending Exa 查询失败: %s ... -> %s", query[:30], sanitize_error_message(str(e)))

    logger.info("GitHub Trending 采集完成，共 %d 条结果", len(results))
    return results
