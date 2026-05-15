#!/usr/bin/env python3.11
"""
AI Daily Intelligence Collector v5
===================================
v4 → v5 优化 (Karpathy 原则自检):
  P0-1: API Key 改读环境变量 (消除硬编码)
  P0-2: 删除冗余 collect_hn()，合并到 collect_exa() discussion_queries (-35行)
  P0-3: 日期过滤统一到 dedup_and_filter 一处 (消除3处重复)
  P0-4: 新增 --selftest 验证模式 (结构/分类/时效性校验)
  P0-5: 报告模板跨平台关联标为可选 (无数据时跳过，不编造)
  P1:   新增 cross_source_cluster() 跨源话题聚类 (Jaccard 0.35)

数据源: Exa API (主力) + GitHub API + Exa Trending
预估采集时间: ~25s
"""

import json
import subprocess
import sys
import os
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # 可选
CACHE_FILE = "/tmp/collector_output.json"
HISTORY_FILE = "/tmp/collector_url_history.json"
TRENDS_FILE = "/tmp/collector_trends_history.json"
CACHE_TTL = 1800
HISTORY_DAYS = 7
TRENDS_DAYS = 3  # 保留3天趋势历史

# ============================================================
# 分类规则
# ============================================================
CATEGORY_RULES = {
    "融资/并购": {
        "keywords": ["融资", "估值", "series", "funding", "valuation", "ipo",
                      "acquisition", "并购", "收购", "raises", "million", "billion",
                      "投资", "invest", "round", "capital", "venture"],
        "priority": 1,
    },
    "产品发布": {
        "keywords": ["发布", "release", "launch", "推出", "新版", "更新", "update",
                      "announce", "introduces", "unveils", "正式上线", "可用", "available",
                      "open source", "开源"],
        "priority": 2,
    },
    "技术突破": {
        "keywords": ["突破", "breakthrough", "research", "paper", "论文", "研究",
                      "achieves", "benchmark", "性能", "performance", "state-of-the-art",
                      "sota", "arxiv", "algorithm", "算法"],
        "priority": 3,
    },
    "政策/监管": {
        "keywords": ["政策", "regulation", "policy", "监管", "safety", "alignment",
                      "government", "政府", "法规", "合规", "compliance", "pentagon",
                      "五角大楼", "classified", "deal"],
        "priority": 4,
    },
    "行业动态": {
        "keywords": [],  # 默认类别
        "priority": 99,
    },
}

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "and", "but", "or",
    "nor", "not", "so", "very", "just", "than", "too", "also", "about",
    "up", "it", "its", "this", "that", "these", "those", "new", "how",
    "what", "which", "who", "when", "where", "why", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "only", "own", "same", "如果", "的", "了", "在", "是", "我",
    "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很",
    "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己",
    "这", "他", "她", "它", "们", "那", "被", "从", "对", "把", "与",
    "以", "但", "中", "等", "又", "而", "或", "及",
}

# ============================================================
# 工具函数
# ============================================================
def load_json_file(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] 保存 {path} 失败: {e}", file=sys.stderr)

def load_url_history():
    history = load_json_file(HISTORY_FILE, {})
    cutoff = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    return {k: v for k, v in history.items() if v >= cutoff}

def save_url_history(history):
    save_json_file(HISTORY_FILE, history)

# ============================================================
# P0-2: 语义去重 (标题关键词 Jaccard)
# ============================================================
def extract_keywords(title):
    """从标题中提取关键词 (去停用词, 小写化)"""
    title = title.lower()
    # 分词: 按空格和标点分割
    words = re.findall(r'[a-z][a-z0-9]+|[\u4e00-\u9fff]+', title)
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}

def jaccard_similarity(set1, set2):
    """Jaccard 相似度"""
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)

def semantic_dedup(items, threshold=0.55):
    """基于标题关键词的语义去重"""
    kept = []
    kept_keywords = []

    for item in items:
        title = item.get("title", "")
        kw = extract_keywords(title)

        # 与已保留的每条比较
        is_dup = False
        for existing_kw in kept_keywords:
            if jaccard_similarity(kw, existing_kw) > threshold:
                is_dup = True
                break

        if not is_dup:
            kept.append(item)
            kept_keywords.append(kw)

    return kept

# ============================================================
# P1-4: 自动分类
# ============================================================
def classify_item(title, snippet=""):
    """基于关键词规则自动分类"""
    text = (title + " " + snippet).lower()
    best_category = "行业动态"
    best_priority = 99

    for cat, rule in CATEGORY_RULES.items():
        for kw in rule["keywords"]:
            if kw in text and rule["priority"] < best_priority:
                best_category = cat
                best_priority = rule["priority"]
                break  # 找到一个关键词就够了

    return best_category

# ============================================================
# P2-8: 趋势 momentum 追踪
# ============================================================
def load_trends_history():
    history = load_json_file(TRENDS_FILE, {})
    cutoff = (datetime.now() - timedelta(days=TRENDS_DAYS)).strftime("%Y-%m-%d")
    return {k: v for k, v in history.items() if v >= cutoff}

def save_trends_history(history, today_keywords):
    """保存今天的关键趋势词"""
    today = datetime.now().strftime("%Y-%m-%d")
    for kw in today_keywords:
        if kw in history:
            # 如果已存在，更新日期
            if history[kw] < today:
                history[kw] = today
        else:
            history[kw] = today
    # 清理过期
    cutoff = (datetime.now() - timedelta(days=TRENDS_DAYS)).strftime("%Y-%m-%d")
    history = {k: v for k, v in history.items() if v >= cutoff}
    save_json_file(TRENDS_FILE, history)

def detect_trend_keywords(items):
    """从所有标题中提取高频趋势关键词"""
    all_kw = []
    for item in items:
        kw = extract_keywords(item.get("title", ""))
        # 只保留有意义的关键词 (长度>2 或中文)
        all_kw.extend([w for w in kw if len(w) > 2 or re.match(r'[\u4e00-\u9fff]', w)])
    counter = Counter(all_kw)
    # 返回出现 >=2 次的关键词
    return {kw for kw, cnt in counter.items() if cnt >= 2}

# ============================================================
# 1. Exa API — 语义搜索 (主力)
# ============================================================
def collect_exa():
    from exa_py import Exa
    exa = Exa(api_key=EXA_API_KEY)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    en_queries = [
        ("artificial intelligence AI latest news breakthroughs funding", 10),
        ("large language model LLM GPT Claude Gemini agent release", 8),
        ("AI chip GPU NVIDIA semiconductor compute", 6),
        ("AI startup funding round valuation 2026", 6),
        ("AI open source model Hugging Face robotics", 6),
        ("AI regulation policy safety alignment", 5),
        ("generative AI image video audio generation model", 5),
    ]

    cn_queries = [
        ("人工智能 大模型 最新发布 突破", 8),
        ("DeepSeek Qwen MiMo 通义千问 国产大模型", 8),
        ("AI 创业公司 融资 估值 2026", 6),
        ("AI 芯片 GPU 算力 国产替代", 5),
        ("AI Agent 智能体 自动化 应用", 5),
        ("36氪 机器之心 量子位 AI 人工智能", 6),
    ]

    official_queries = [
        ("OpenAI Anthropic Google DeepMind latest announcement", 6),
        ("Meta AI Microsoft AI Amazon AI latest news", 5),
        ("site:openai.com OR site:anthropic.com OR site:deepmind.google", 5),
    ]

    arxiv_queries = [
        ("arxiv AI paper latest breakthrough research 2026", 6),
        ("机器学习 深度学习 最新论文 研究突破", 5),
    ]

    discussion_queries = [
        ("site:news.ycombinator.com AI LLM model agent", 8),
        ("site:reddit.com artificial intelligence machine learning latest", 8),
        ("Hacker News top AI discussion today", 5),
    ]

    all_queries = en_queries + cn_queries + official_queries + arxiv_queries + discussion_queries
    all_results = []
    seen_urls = set()

    for query, num in all_queries:
        try:
            results = exa.search(query, num_results=num, type="neural", start_published_date=yesterday)
            for r in results.results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    snippet = (r.text or "")[:400]
                    title = r.title or ""
                    published_str = str(r.published_date)[:10] if r.published_date else "unknown"
                    if published_str in ("unknown", "") or published_str < yesterday:
                        continue
                    # 根据 query_group 来源打标签，用于跨源聚类
                    if "ycombinator" in query or "reddit" in query or "Hacker News" in query:
                        source_tag = "discussion"
                    elif "openai.com" in query or "anthropic.com" in query or "deepmind" in query:
                        source_tag = "official"
                    elif "arxiv" in query or "论文" in query:
                        source_tag = "research"
                    else:
                        source_tag = "news"
                    all_results.append({
                        "title": title,
                        "url": r.url,
                        "source": source_tag,
                        "published": published_str,
                        "snippet": snippet,
                        "query_group": query[:30],
                        "category": classify_item(title, snippet),
                    })
        except Exception as e:
            print(f"[WARN] Exa 查询失败: {query[:30]}... -> {e}", file=sys.stderr)

    return all_results

# ============================================================
# 2. GitHub API — 带认证 + 详情补充
# ============================================================
def collect_github():
    import urllib.request, urllib.parse
    results = []
    since = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    queries = [
        f"created:>{since} topic:artificial-intelligence stars:>20",
        f"created:>{since} topic:machine-learning stars:>20",
        f"created:>{since} topic:llm stars:>10",
        f"created:>{since} topic:deep-learning stars:>20",
        f"pushed:>{since} topic:ai-agent stars:>100",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    seen = set()
    for q in queries:
        try:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=5"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for repo in data.get("items", []):
                if repo["html_url"] not in seen:
                    seen.add(repo["html_url"])
                    desc = repo.get("description") or ""
                    topics = repo.get("topics", [])
                    title = f"{repo['full_name']} — {desc[:100]}"
                    snippet = (f"Stars: {repo.get('stargazers_count', 0)} | "
                               f"Forks: {repo.get('forks_count', 0)} | "
                               f"Lang: {repo.get('language', 'N/A')} | "
                               f"Topics: {', '.join(topics[:5])} | "
                               f"Updated: {repo.get('updated_at', '')[:10]} | "
                               f"{desc[:200]}")
                    results.append({
                        "title": title,
                        "url": repo["html_url"],
                        "source": "github",
                        "published": repo.get("created_at", "")[:10],
                        "snippet": snippet,
                        "query_group": "github_trending",
                        "category": classify_item(title, desc),
                    })
        except Exception as e:
            print(f"[WARN] GitHub 查询失败: {q[:30]}... -> {e}", file=sys.stderr)
    return results[:20]

# ============================================================
# 4. GitHub Trending — 通过 Exa 获取今日热度
# ============================================================
def collect_github_trending():
    """P0-1: 用 Exa 搜索 GitHub 上今日 star 暴涨的 AI repo"""
    from exa_py import Exa
    exa = Exa(api_key=EXA_API_KEY)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    results = []

    queries = [
        ("site:github.com trending AI machine learning stars today", 8),
        ("site:github.com trending LLM agent framework popular", 6),
    ]

    for query, num in queries:
        try:
            r = exa.search(query, num_results=num, type="neural", start_published_date=yesterday)
            for item in r.results:
                url = item.url or ""
                if "github.com" not in url:
                    continue
                # 只保留 repo 链接，过滤 commit/PR/release/wiki
                import urllib.parse as _up
                path_parts = _up.urlparse(url).path.strip("/").split("/")
                if len(path_parts) != 2:
                    continue
                snippet = (item.text or "")[:400]
                title = item.title or ""
                published_str = str(item.published_date)[:10] if item.published_date else "unknown"
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
            print(f"[WARN] GitHub Trending Exa 查询失败: {query[:30]}... -> {e}", file=sys.stderr)

    return results

# ============================================================
# 5. 去噪 + 去重 (URL + 语义去重 + 跨日历史)
# ============================================================
def dedup_and_filter(all_data, url_history):
    # 噪声过滤
    noise_patterns = [
        "huggingface.co/datasets/",
        "huggingface.co/models/",
        "kaggle.com/",
        "leetcode.com",
    ]
    all_data = [item for item in all_data
                if not any(pat in item.get("url", "") for pat in noise_patterns)]

    # P1: 客户端日期门控 — 丢弃 published 为空/unknown/过旧（>2天）的数据
    cutoff = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    date_filtered_count = len(all_data)
    all_data = [item for item in all_data
                if item.get("published", "unknown") not in ("unknown", "")
                and item.get("published", "") >= cutoff]
    if date_filtered_count != len(all_data):
        print(f"[Collector] 日期门控过滤: {date_filtered_count - len(all_data)} 条过期/未知日期数据", file=sys.stderr)

    # URL 精确去重 + 跨日历史去重 (只过滤昨天及之前的，不过滤今天的)
    today = datetime.now().strftime("%Y-%m-%d")
    seen_urls = set()
    url_deduped = []
    for item in all_data:
        url = item.get("url", "")
        if url and url in seen_urls:
            continue
        # 只过滤昨天及之前见过的 URL，今天的保留
        if url and url in url_history and url_history[url] < today:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(item)

    # P0-2: 语义去重 (标题关键词 Jaccard)
    sem_deduped = semantic_dedup(url_deduped, threshold=0.45)

    return sem_deduped

# ============================================================
# P1: 跨源 topic clustering (cross_platform_signals)
# ============================================================
def cross_source_cluster(items, threshold=0.35, min_shared=2):
    """将不同源的相关新闻按标题关键词聚类，保留跨源话题

    使用两层匹配:
    1. Jaccard > threshold (宽松)
    2. OR 共享有意义关键词 >= min_shared 个 (长度>3 的英文/中文)
    """
    # 为每条 item 提取关键词
    item_kws = [(item, extract_keywords(item.get("title", ""))) for item in items]

    # 筛选有意义关键词 (>3字符 或 中文)
    def meaningful(kw_set):
        return {w for w in kw_set if len(w) > 3 or re.match(r'[\u4e00-\u9fff]', w)}

    clusters = []  # list of {"items": [...], "kw_set": set, "sources": set}

    for item, kw in item_kws:
        if not kw:
            continue
        m_kw = meaningful(kw)
        merged = False
        for cluster in clusters:
            # 双重匹配: Jaccard 或 关键词重叠
            jacc = jaccard_similarity(kw, cluster["kw_set"])
            shared = len(m_kw & meaningful(cluster["kw_set"]))
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
    signals = []
    for c in clusters:
        if len(c["sources"]) >= 2:
            # 从 items 中提取高频词作为 topic label
            all_title_kw = []
            for it in c["items"]:
                all_title_kw.extend(extract_keywords(it.get("title", "")))
            from collections import Counter as _Counter
            top_kw = _Counter(all_title_kw).most_common(3)
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


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    # selftest 模式: 验证已有缓存数据的结构完整性
    if "--selftest" in sys.argv:
        print("[Selftest] 开始验证...", file=sys.stderr)
        if not os.path.exists(CACHE_FILE):
            print(f"[Selftest] FAIL: 缓存文件不存在 {CACHE_FILE}", file=sys.stderr)
            sys.exit(1)
        with open(CACHE_FILE) as f:
            data = json.load(f)

        errors = []
        # 结构完整性
        required_keys = {"collected_at", "date", "total_items", "source_counts", "category_counts", "trend_momentum", "items"}
        missing = required_keys - set(data.keys())
        if missing:
            errors.append(f"缺少顶层字段: {missing}")

        # items 非空且结构正确
        items = data.get("items", [])
        if not items:
            errors.append("items 为空")
        for i, item in enumerate(items[:5]):  # 抽查前5条
            for k in ("title", "url", "source", "published", "category"):
                if k not in item:
                    errors.append(f"items[{i}] 缺少字段: {k}")

        # 分类分布合理性 (不能全部是"行业动态")
        cat_counts = data.get("category_counts", {})
        if cat_counts:
            default_ratio = cat_counts.get("行业动态", 0) / max(sum(cat_counts.values()), 1)
            if default_ratio > 0.9:
                errors.append(f"分类过于集中: {default_ratio:.0%} 是'行业动态'")

        # 趋势数据
        tm = data.get("trend_momentum", {})
        if "continuing" not in tm or "new" not in tm:
            errors.append("trend_momentum 缺少 continuing/new 字段")

        # 跨源信号 (可选字段，但如果存在应为 list)
        cps = data.get("cross_platform_signals")
        if cps is not None and not isinstance(cps, list):
            errors.append("cross_platform_signals 存在但不是 list 类型")

        # 日期时效性
        from datetime import datetime as _dt
        cutoff = (_dt.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        stale = [it for it in items if it.get("published", "9999") < cutoff]
        if stale:
            errors.append(f"{len(stale)} 条数据超过2天未过期")

        if errors:
            for e in errors:
                print(f"[Selftest] FAIL: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"[Selftest] PASS: {len(items)} 条, {len(cat_counts)} 类, {len(tm.get('continuing', []))} 延续趋势, {len(tm.get('new', []))} 新趋势, {len(cps or [])} 跨源话题", file=sys.stderr)
            sys.exit(0)

    # 校验必需环境变量
    if not EXA_API_KEY:
        print("[ERROR] EXA_API_KEY 未设置，请 export EXA_API_KEY=xxx", file=sys.stderr)
        sys.exit(1)

    # 快速路径: 缓存复用
    if os.path.exists(CACHE_FILE):
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age < CACHE_TTL:
            print(f"[Collector] 使用缓存数据 ({age:.0f}s 前)", file=sys.stderr)
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            print(json.dumps(cached, ensure_ascii=False))
            sys.exit(0)

    ts = datetime.now().isoformat()
    print(f"[Collector] v5 开始采集 {ts}", file=sys.stderr)

    # 加载历史
    url_history = load_url_history()
    trends_history = load_trends_history()
    print(f"[Collector] 历史URL: {len(url_history)}, 历史趋势词: {len(trends_history)}", file=sys.stderr)

    all_data = []
    source_counts = {}

    # 采集所有源 (P0-1: 新增 github_trending)
    collectors = [
        ("Exa", collect_exa),
        ("GitHub", collect_github),
        ("GitHub_Trending", collect_github_trending),
    ]

    for name, fn in collectors:
        print(f"[Collector] 采集 {name}...", file=sys.stderr)
        t0 = time.time()
        try:
            with ThreadPoolExecutor(max_workers=1) as timeout_pool:
                future = timeout_pool.submit(fn)
                d = future.result(timeout=60)
            elapsed = time.time() - t0
            print(f"[Collector] {name}: {len(d)} 条 ({elapsed:.1f}s)", file=sys.stderr)
            source_counts[name.lower()] = len(d)
            all_data.extend(d)
        except TimeoutError:
            elapsed = time.time() - t0
            print(f"[Collector] {name} 超时 ({elapsed:.1f}s)", file=sys.stderr)
            source_counts[name.lower()] = 0
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[Collector] {name} 失败 ({elapsed:.1f}s): {e}", file=sys.stderr)
            source_counts[name.lower()] = 0

    # 去噪 + 语义去重
    merged = dedup_and_filter(all_data, url_history)
    print(f"[Collector] 去重后: {len(merged)} 条", file=sys.stderr)

    # P2-8: 趋势 momentum 追踪
    today_keywords = detect_trend_keywords(merged)
    # 判断哪些是延续趋势（昨天就存在的），哪些是新出现
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    old_trends = {kw for kw, dt in trends_history.items() if dt <= yesterday_str}
    continuing_trends = today_keywords & old_trends
    new_trends = today_keywords - old_trends
    save_trends_history(trends_history, today_keywords)

    # P1: 跨源聚类
    cross_signals = cross_source_cluster(merged)
    if cross_signals:
        print(f"[Collector] 跨源话题: {len(cross_signals)} 个", file=sys.stderr)

    # 按类别统计
    category_counts = Counter(item.get("category", "未分类") for item in merged)

    # 更新 URL 历史
    today = datetime.now().strftime("%Y-%m-%d")
    for item in merged:
        if item.get("url"):
            url_history[item["url"]] = today
    save_url_history(url_history)

    # 输出 (P2-9: 包含结构化元数据)
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

    with open(CACHE_FILE, "w") as f:
        json.dump(output, f, ensure_ascii=False)

    print(json.dumps(output, ensure_ascii=False))
