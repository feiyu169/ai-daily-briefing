"""
文件工具函数
============
JSON 文件读写、历史管理
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from .logger import logger


def load_json_file(path: str, default: Any = None) -> Any:
    """加载 JSON 文件
    
    Args:
        path: 文件路径
        default: 默认值
        
    Returns:
        解析后的数据
    """
    if default is None:
        default = {}
    
    if not os.path.exists(path):
        return default
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 {path} 失败: {e}")
        return default


def save_json_file(path: str, data: Any) -> bool:
    """保存 JSON 文件
    
    Args:
        path: 文件路径
        data: 要保存的数据
        
    Returns:
        是否成功
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning(f"保存 {path} 失败: {e}")
        return False


def load_url_history(history_file: str, history_days: int = 7) -> Dict[str, str]:
    """加载 URL 历史
    
    Args:
        history_file: 历史文件路径
        history_days: 保留天数
        
    Returns:
        URL 历史字典
    """
    history = load_json_file(history_file, {})
    cutoff = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d")
    return {k: v for k, v in history.items() if v >= cutoff}


def save_url_history(history_file: str, history: Dict[str, str]) -> bool:
    """保存 URL 历史
    
    Args:
        history_file: 历史文件路径
        history: URL 历史字典
        
    Returns:
        是否成功
    """
    return save_json_file(history_file, history)


def load_trends_history(trends_file: str, trends_days: int = 3) -> Dict[str, str]:
    """加载趋势历史
    
    Args:
        trends_file: 趋势文件路径
        trends_days: 保留天数
        
    Returns:
        趋势历史字典
    """
    history = load_json_file(trends_file, {})
    cutoff = (datetime.now() - timedelta(days=trends_days)).strftime("%Y-%m-%d")
    return {k: v for k, v in history.items() if v >= cutoff}


def save_trends_history(
    trends_file: str,
    history: Dict[str, str],
    today_keywords: set,
    trends_days: int = 3,
) -> bool:
    """保存趋势历史
    
    Args:
        trends_file: 趋势文件路径
        history: 趋势历史字典
        today_keywords: 今天的关键词
        trends_days: 保留天数
        
    Returns:
        是否成功
    """
    today = datetime.now().strftime("%Y-%m-%d")
    for kw in today_keywords:
        if kw in history:
            if history[kw] < today:
                history[kw] = today
        else:
            history[kw] = today
    
    # 清理过期
    cutoff = (datetime.now() - timedelta(days=trends_days)).strftime("%Y-%m-%d")
    history = {k: v for k, v in history.items() if v >= cutoff}
    
    return save_json_file(trends_file, history)
