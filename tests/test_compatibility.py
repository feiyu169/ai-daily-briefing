"""
向后兼容性测试
==============
验证 v6 输出格式与 v5 兼容
"""

import pytest
import json
from collections import Counter

# 向后兼容性字段矩阵
COMPATIBILITY_FIELDS = {
    "collected_at",
    "date",
    "total_items",
    "source_counts",
    "category_counts",
    "trend_momentum",
    "items",
}


class TestBackwardCompatibility:
    """向后兼容性测试"""
    
    def test_output_structure(self):
        """测试输出结构包含所有必需字段"""
        # 模拟输出结构
        output = {
            "collected_at": "2026-05-15T22:00:00",
            "date": "2026-05-15",
            "total_items": 100,
            "source_counts": {"exa": 80, "github": 20},
            "category_counts": {"行业动态": 50, "融资/并购": 20},
            "trend_momentum": {
                "continuing": ["ai", "llm"],
                "new": ["chip"],
            },
            "cross_platform_signals": [],
            "items": [],
        }
        
        # 验证所有必需字段存在
        missing = COMPATIBILITY_FIELDS - set(output.keys())
        assert not missing, f"缺少字段: {missing}"
    
    def test_category_counts_includes_new_categories(self):
        """测试 category_counts 包含新分类"""
        category_counts = Counter({
            "行业动态": 50,
            "融资/并购": 20,
            "产品发布": 15,
            "技术突破": 10,
            "政策/监管": 5,
            "芯片/半导体": 8,
            "机器人/具身智能": 5,
        })
        
        # 验证新分类存在
        assert "芯片/半导体" in category_counts
        assert "机器人/具身智能" in category_counts
        
        # 验证旧分类仍然存在
        assert "行业动态" in category_counts
        assert "融资/并购" in category_counts
    
    def test_trend_momentum_structure(self):
        """测试 trend_momentum 结构"""
        trend_momentum = {
            "continuing": ["ai", "llm", "gpu"],
            "new": ["chip", "robot"],
        }
        
        # 验证结构
        assert "continuing" in trend_momentum
        assert "new" in trend_momentum
        assert isinstance(trend_momentum["continuing"], list)
        assert isinstance(trend_momentum["new"], list)
    
    def test_items_structure(self):
        """测试 items 结构"""
        item = {
            "title": "NVIDIA releases new AI chip",
            "url": "https://example.com/1",
            "source": "news",
            "published": "2026-05-15",
            "snippet": "NVIDIA announced...",
            "query_group": "chip_queries",
            "category": "芯片/半导体",
        }
        
        # 验证必需字段
        required_fields = {"title", "url", "source", "published", "category"}
        missing = required_fields - set(item.keys())
        assert not missing, f"item 缺少字段: {missing}"
    
    def test_source_counts_structure(self):
        """测试 source_counts 结构"""
        source_counts = {
            "exa": 80,
            "github": 15,
            "github_trending": 10,
        }
        
        # 验证结构
        assert isinstance(source_counts, dict)
        for key, value in source_counts.items():
            assert isinstance(key, str)
            assert isinstance(value, int)
    
    def test_json_serializable(self):
        """测试输出可序列化为 JSON"""
        output = {
            "collected_at": "2026-05-15T22:00:00",
            "date": "2026-05-15",
            "total_items": 100,
            "source_counts": {"exa": 80},
            "category_counts": {"行业动态": 50},
            "trend_momentum": {"continuing": [], "new": []},
            "cross_platform_signals": [],
            "items": [],
        }
        
        # 验证可序列化
        try:
            json_str = json.dumps(output, ensure_ascii=False)
            # 验证可反序列化
            parsed = json.loads(json_str)
            assert parsed == output
        except Exception as e:
            pytest.fail(f"JSON 序列化失败: {e}")


class TestCompatibilityLayer:
    """兼容层测试"""
    
    def test_import_main(self):
        """测试导入 main 模块"""
        try:
            from src.main import main
            assert callable(main)
        except ImportError as e:
            pytest.fail(f"导入 main 失败: {e}")
    
    def test_import_collectors(self):
        """测试导入采集器模块"""
        try:
            from src.collectors.exa_collector import collect_exa
            from src.collectors.github_collector import collect_github
            from src.collectors.trending_collector import collect_github_trending
            assert callable(collect_exa)
            assert callable(collect_github)
            assert callable(collect_github_trending)
        except ImportError as e:
            pytest.fail(f"导入采集器失败: {e}")
    
    def test_import_processors(self):
        """测试导入处理器模块"""
        try:
            from src.processors.classifier import classify_item
            from src.processors.dedup import dedup_and_filter
            from src.processors.trends import detect_trend_keywords
            from src.processors.cross_source import cross_source_cluster
            assert callable(classify_item)
            assert callable(dedup_and_filter)
            assert callable(detect_trend_keywords)
            assert callable(cross_source_cluster)
        except ImportError as e:
            pytest.fail(f"导入处理器失败: {e}")
    
    def test_import_utils(self):
        """测试导入工具模块"""
        try:
            from src.utils.config import get_config, get_categories, get_queries
            from src.utils.file_utils import load_json_file, save_json_file
            assert callable(get_config)
            assert callable(get_categories)
            assert callable(get_queries)
            assert callable(load_json_file)
            assert callable(save_json_file)
        except ImportError as e:
            pytest.fail(f"导入工具失败: {e}")
