"""
文本工具函数
============
统一的关键词提取和文本处理函数
"""

import re
from typing import Set


# 统一的停用词表
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


def extract_keywords(title: str) -> Set[str]:
    """从标题中提取关键词（去停用词，小写化）
    
    Args:
        title: 标题文本
        
    Returns:
        关键词集合
    """
    title = title.lower()
    # 分词: 按空格和标点分割
    words = re.findall(r'[a-z][a-z0-9]+|[\u4e00-\u9fff]+', title)
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def meaningful_keywords(kw_set: Set[str]) -> Set[str]:
    """筛选有意义关键词（>3字符 或 中文）
    
    Args:
        kw_set: 关键词集合
        
    Returns:
        有意义的关键词集合
    """
    return {w for w in kw_set if len(w) > 3 or re.match(r'[\u4e00-\u9fff]', w)}
