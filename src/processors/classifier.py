"""
分类器模块
===========
从 config.yaml 加载分类规则，实现 classify_item 函数用于自动归类新闻条目。

Usage:
    from src.processors.classifier import classify_item

    category = classify_item("OpenAI 完成 400 亿美元融资", "估值达 3000 亿")
    # -> "融资/并购"
"""

from typing import Dict, List

from src.utils.config import get_categories


def classify_item(title: str, snippet: str = "") -> str:
    """基于关键词规则自动分类新闻条目。

    遍历 config.yaml 中定义的 categories 规则，将 title 和 snippet 拼接后
    进行大小写不敏感的关键词匹配。优先匹配 priority 值最小（优先级最高）的类别。

    Args:
        title:   新闻标题。
        snippet: 新闻摘要（可选），默认为空字符串。

    Returns:
        匹配到的分类名称。若无任何关键词命中，返回默认类别 ``行业动态``。
    """
    text: str = (title + " " + snippet).lower()
    categories: Dict[str, Dict] = get_categories()

    # 找出有效类别（有 keywords 且不是空列表的），按 priority 升序排列
    valid_rules: List[tuple] = []
    for cat, rule in categories.items():
        keywords: List[str] = rule.get("keywords", [])
        priority: int = rule.get("priority", 99)
        if keywords:  # 跳过 keywords=[] 的类别（默认兜底项）
            valid_rules.append((cat, keywords, priority))

    # 按 priority 升序排列，保证高优先级类别优先匹配
    valid_rules.sort(key=lambda x: x[2])

    for cat, keywords, _priority in valid_rules:
        for kw in keywords:
            if kw in text:
                return cat

    return "行业动态"


def get_category_rules() -> Dict[str, Dict]:
    """获取所有分类规则（原始字典）。

    Returns:
        分类规则字典，结构与 config.yaml 的 categories 字段一致。
    """
    return get_categories()
