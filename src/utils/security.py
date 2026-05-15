"""
安全工具
========
统一的 API Key 管理和安全函数
"""

import os
from typing import Optional

from .logger import logger


def get_api_key(key_name: str, required: bool = True) -> Optional[str]:
    """获取 API Key（仅从环境变量）
    
    统一的 API Key 获取函数，确保 key 只存在于运行时环境变量中，
    不从配置文件或字典中读取。
    
    Args:
        key_name: 环境变量名称（如 "EXA_API_KEY"）
        required: 是否必需
        
    Returns:
        API Key 值，如果不存在且非必需则返回 None
        
    Raises:
        SystemExit: 如果必需的 key 不存在
    """
    value = os.environ.get(key_name)
    
    if not value:
        if required:
            logger.error(f"{key_name} 未设置，请 export {key_name}=xxx")
            raise SystemExit(1)
        else:
            logger.warning(f"{key_name} 未设置，相关功能可能不可用")
            return None
    
    return value


def sanitize_error_message(message: str) -> str:
    """清理错误消息中的敏感信息
    
    Args:
        message: 原始错误消息
        
    Returns:
        清理后的错误消息
    """
    # 移除可能包含 API key 的 URL 参数
    import re
    # 匹配 ?key=xxx 或 &key=xxx 模式
    sanitized = re.sub(r'([?&])(key|token|api_key|apikey)=[^&]*', r'\1\2=***', message)
    return sanitized
