"""
GitHub 采集器模块
=================
从 GitHub Search API 采集 AI 相关热门仓库，支持查询模板和 token 认证。

Usage:
    from src.collectors.github_collector import collect_github

    results = collect_github()
    # -> [{"title": "...", "url": "...", "source": "github", ...}, ...]
"""

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.utils.config import get_queries
from src.processors.classifier import classify_item

logger = logging.getLogger(__name__)

# 默认查询（无配置时兜底）
DEFAULT_GITHUB_QUERIES: List[str] = [
    "created:{since} topic:artificial-intelligence stars:>20",
    "created:{since} topic:machine-learning stars:>20",
    "created:{since} topic:llm stars:>10",
    "created:{since} topic:deep-learning stars:>20",
    "pushed:{since} topic:ai-agent stars:>100",
]

GITHUB_API_BASE = "https://api.github.com/search/repositories"


def _build_headers() -> Dict[str, str]:
    """构建 GitHub API 请求头。

    如果环境变量 GITHUB_TOKEN 存在则附加 Bearer token 以提高速率限制。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.github.v3+json",
    }
    token: str = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _load_queries(since: str) -> List[str]:
    """从 config.yaml 加载 GitHub 查询列表。

    Args:
        since: ISO 日期字符串，替换查询模板中的 {since} 占位符。

    Returns:
        查询字符串列表。如果配置加载失败则返回默认查询列表。
    """
    try:
        queries_config: Dict[str, Any] = get_queries()
        github_queries_raw: List[Dict[str, Any]] = queries_config.get("github_queries", [])
        if github_queries_raw:
            return [q["query"].replace("{since}", since) for q in github_queries_raw]
    except Exception as exc:
        logger.warning("加载 github_queries 配置失败: %s, 使用默认查询", exc)

    return [q.replace("{since}", since) for q in DEFAULT_GITHUB_QUERIES]


def _build_repo_item(repo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将单个 GitHub API 仓库响应组装为统一新闻条目。

    Args:
        repo: GitHub Search API 返回的单个仓库对象。

    Returns:
        统一格式的新闻条目字典，若缺少 html_url 则返回 None。
    """
    html_url: Optional[str] = repo.get("html_url")
    if not html_url:
        return None

    desc: str = repo.get("description") or ""
    topics: List[str] = repo.get("topics", [])
    title: str = f"{repo['full_name']} — {desc[:100]}"

    snippet: str = (
        f"Stars: {repo.get('stargazers_count', 0)} | "
        f"Forks: {repo.get('forks_count', 0)} | "
        f"Lang: {repo.get('language', 'N/A')} | "
        f"Topics: {', '.join(topics[:5])} | "
        f"Updated: {repo.get('updated_at', '')[:10]} | "
        f"{desc[:200]}"
    )

    return {
        "title": title,
        "url": html_url,
        "source": "github",
        "published": (repo.get("created_at") or "")[:10],
        "snippet": snippet,
        "query_group": "github_trending",
        "category": classify_item(title, desc),
    }


def _fetch_repos(
    query: str,
    headers: Dict[str, str],
    seen: set,
    results: List[Dict[str, Any]],
    timeout: int = 10,
) -> None:
    """执行单条 GitHub 搜索查询并收集结果。

    Args:
        query:   GitHub 搜索查询字符串（已包含 since 占位符替换）。
        headers: API 请求头。
        seen:    已见 URL 集合，用于去重。
        results: 结果列表（原地追加新条目）。
        timeout: 请求超时秒数。
    """
    try:
        params: str = urllib.parse.urlencode({
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        })
        url: str = f"{GITHUB_API_BASE}?{params}"
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: Dict[str, Any] = json.loads(resp.read())

        for repo in data.get("items", []):
            html_url: Optional[str] = repo.get("html_url")
            if not html_url or html_url in seen:
                continue
            seen.add(html_url)

            item: Optional[Dict[str, Any]] = _build_repo_item(repo)
            if item:
                results.append(item)

    except urllib.error.HTTPError as exc:
        logger.warning("GitHub API HTTP 错误 (%s): %s — %s", exc.code, query[:40], exc.reason)
    except urllib.error.URLError as exc:
        logger.warning("GitHub API 网络错误: %s — %s", query[:40], exc.reason)
    except json.JSONDecodeError as exc:
        logger.warning("GitHub API 响应解析失败: %s — %s", query[:40], exc)
    except Exception as exc:
        logger.warning("GitHub 查询失败: %s... -> %s", query[:40], exc)


def collect_github(max_results: int = 20) -> List[Dict[str, Any]]:
    """采集 GitHub AI 相关热门仓库。

    从 config.yaml 加载 ``github_queries`` 查询列表（支持 {since} 模板变量），
    依次请求 GitHub Search API，去重后返回统一格式的新闻条目。

    Args:
        max_results: 最大返回结果数（默认 20）。

    Returns:
        新闻条目列表，每条包含 title / url / source / published / snippet
        / query_group / category 字段。
    """
    since: str = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    headers: Dict[str, str] = _build_headers()
    queries: List[str] = _load_queries(since)

    results: List[Dict[str, Any]] = []
    seen: set = set()

    logger.info("GitHub 采集开始，共 %d 条查询, since=%s", len(queries), since)

    for query in queries:
        _fetch_repos(query, headers, seen, results)

    logger.info("GitHub 采集完成，去重前/后共 %d 条", len(results))

    return results[:max_results]
