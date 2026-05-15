"""
配置加载器
==========
加载 .env 和 config.yaml，优先级：环境变量 > YAML > 默认值
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict

# 加载 .env
load_dotenv()

# 默认配置
DEFAULT_CONFIG = {
    "collector": {
        "cache_ttl": 1800,
        "history_days": 7,
        "trends_days": 3,
        "max_concurrent_queries": 5,
        "query_timeout": 60,
    },
    "dedup": {
        "semantic_threshold": 0.45,
        "cross_source_threshold": 0.35,
        "min_shared_keywords": 2,
    },
    "output": {
        "cache_file": "/tmp/collector_output.json",
        "history_file": "/tmp/collector_url_history.json",
        "trends_file": "/tmp/collector_trends_history.json",
    },
}


def load_config(config_path: str = None) -> Dict[str, Any]:
    """加载配置
    
    优先级：环境变量 > YAML > 默认值
    
    Args:
        config_path: 配置文件路径，默认为项目根目录下的 config.yaml
        
    Returns:
        配置字典
    """
    # 确定配置文件路径
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    # 加载 YAML 配置
    yaml_config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
    
    # 合并配置（YAML 覆盖默认值）
    config = _deep_merge(DEFAULT_CONFIG, yaml_config)
    
    # 环境变量覆盖
    config = _apply_env_overrides(config)
    
    return config


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict) -> Dict:
    """应用环境变量覆盖"""
    # API Key 等敏感信息从环境变量读取
    env_mappings = {
        "EXA_API_KEY": ("exa_api_key",),
        "GITHUB_TOKEN": ("github_token",),
        "FEISHU_APP_ID": ("feishu", "app_id"),
        "FEISHU_APP_SECRET": ("feishu", "app_secret"),
        "FEISHU_HOME_CHANNEL": ("feishu", "home_channel"),
    }
    
    for env_var, config_path in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            # 设置到配置字典
            current = config
            for key in config_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[config_path[-1]] = value
    
    return config


# 全局配置实例
_config = None


def get_config() -> Dict[str, Any]:
    """获取全局配置（单例）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# 便捷访问
def get_collector_config() -> Dict[str, Any]:
    """获取采集器配置"""
    return get_config().get("collector", {})


def get_categories() -> Dict[str, Any]:
    """获取分类规则"""
    return get_config().get("categories", {})


def get_queries() -> Dict[str, Any]:
    """获取采集查询"""
    return get_config().get("queries", {})


def get_dedup_config() -> Dict[str, Any]:
    """获取去重配置"""
    return get_config().get("dedup", {})


def get_noise_patterns() -> list:
    """获取噪声过滤模式"""
    return get_config().get("noise_patterns", [])


def get_output_config() -> Dict[str, Any]:
    """获取输出配置"""
    return get_config().get("output", {})
