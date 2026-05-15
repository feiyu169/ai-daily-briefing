"""
API 配额监控
============
监控 Exa API 使用量，提供降级机制
"""

from datetime import datetime
from typing import Dict

from .logger import logger
from .file_utils import load_json_file, save_json_file


# 配额配置
QUOTA_CONFIG = {
    "exa": {
        "daily_limit": 100,  # 每日限额
        "monthly_limit": 1000,  # 每月限额
        "warning_threshold": 0.8,  # 80% 时告警
        "critical_threshold": 0.95,  # 95% 时降级
    }
}

# 配额使用记录文件
QUOTA_FILE = ".cache/api_quota.json"


def load_quota() -> Dict:
    """加载配额使用记录"""
    return load_json_file(QUOTA_FILE, {
        "exa": {
            "daily_usage": 0,
            "monthly_usage": 0,
            "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
            "last_reset_month": datetime.now().strftime("%Y-%m"),
        }
    })


def save_quota(quota: Dict) -> bool:
    """保存配额使用记录"""
    return save_json_file(QUOTA_FILE, quota)


def record_api_call(api_name: str, count: int = 1) -> None:
    """记录 API 调用
    
    Args:
        api_name: API 名称（如 "exa"）
        count: 调用次数
    """
    quota = load_quota()
    today = datetime.now().strftime("%Y-%m-%d")
    this_month = datetime.now().strftime("%Y-%m")
    
    if api_name not in quota:
        quota[api_name] = {
            "daily_usage": 0,
            "monthly_usage": 0,
            "last_reset_date": today,
            "last_reset_month": this_month,
        }
    
    api_quota = quota[api_name]
    
    # 重置每日计数
    if api_quota.get("last_reset_date") != today:
        api_quota["daily_usage"] = 0
        api_quota["last_reset_date"] = today
    
    # 重置每月计数
    if api_quota.get("last_reset_month") != this_month:
        api_quota["monthly_usage"] = 0
        api_quota["last_reset_month"] = this_month
    
    api_quota["daily_usage"] += count
    api_quota["monthly_usage"] += count
    
    save_quota(quota)


def check_quota(api_name: str) -> Dict:
    """检查 API 配额状态
    
    Args:
        api_name: API 名称（如 "exa"）
        
    Returns:
        配额状态字典
    """
    quota = load_quota()
    config = QUOTA_CONFIG.get(api_name, {})
    
    if api_name not in quota:
        return {
            "status": "ok",
            "daily_usage": 0,
            "daily_limit": config.get("daily_limit", 100),
            "monthly_usage": 0,
            "monthly_limit": config.get("monthly_limit", 1000),
            "daily_ratio": 0.0,
            "monthly_ratio": 0.0,
        }
    
    api_quota = quota[api_name]
    daily_usage = api_quota.get("daily_usage", 0)
    monthly_usage = api_quota.get("monthly_usage", 0)
    daily_limit = config.get("daily_limit", 100)
    monthly_limit = config.get("monthly_limit", 1000)
    warning_threshold = config.get("warning_threshold", 0.8)
    critical_threshold = config.get("critical_threshold", 0.95)
    
    daily_ratio = daily_usage / daily_limit if daily_limit > 0 else 0
    monthly_ratio = monthly_usage / monthly_limit if monthly_limit > 0 else 0
    
    # 确定状态
    if daily_ratio >= critical_threshold or monthly_ratio >= critical_threshold:
        status = "critical"
    elif daily_ratio >= warning_threshold or monthly_ratio >= warning_threshold:
        status = "warning"
    else:
        status = "ok"
    
    return {
        "status": status,
        "daily_usage": daily_usage,
        "daily_limit": daily_limit,
        "monthly_usage": monthly_usage,
        "monthly_limit": monthly_limit,
        "daily_ratio": daily_ratio,
        "monthly_ratio": monthly_ratio,
    }


def get_degradation_strategy(api_name: str) -> Dict:
    """获取降级策略
    
    Args:
        api_name: API 名称（如 "exa"）
        
    Returns:
        降级策略字典
    """
    quota_status = check_quota(api_name)
    status = quota_status["status"]
    
    if status == "critical":
        return {
            "should_degrade": True,
            "strategy": "reduce_queries",
            "reduction_ratio": 0.5,  # 减少 50% 查询
            "message": f"API 配额接近上限（{quota_status['daily_ratio']:.0%}），减少查询数量",
        }
    elif status == "warning":
        return {
            "should_degrade": False,
            "strategy": "monitor",
            "reduction_ratio": 0.0,
            "message": f"API 配额使用较高（{quota_status['daily_ratio']:.0%}），建议监控",
        }
    else:
        return {
            "should_degrade": False,
            "strategy": "normal",
            "reduction_ratio": 0.0,
            "message": "API 配额正常",
        }


def log_quota_status(api_name: str) -> None:
    """记录配额状态到日志"""
    quota_status = check_quota(api_name)
    status = quota_status["status"]
    daily_ratio = quota_status["daily_ratio"]
    monthly_ratio = quota_status["monthly_ratio"]
    
    if status == "critical":
        logger.warning(
            f"API 配额告警: {api_name} 日用量 {daily_ratio:.0%}, 月用量 {monthly_ratio:.0%}"
        )
    elif status == "warning":
        logger.info(
            f"API 配额提醒: {api_name} 日用量 {daily_ratio:.0%}, 月用量 {monthly_ratio:.0%}"
        )
