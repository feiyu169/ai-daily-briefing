"""
日志工具
========
统一的日志配置
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "ai_daily_briefing",
    level: int = logging.INFO,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """设置日志器
    
    Args:
        name: 日志器名称
        level: 日志级别
        format_string: 日志格式
        
    Returns:
        配置好的日志器
    """
    if format_string is None:
        format_string = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(format_string))
        logger.addHandler(handler)
    
    logger.setLevel(level)
    return logger


# 默认日志器
logger = setup_logger()
