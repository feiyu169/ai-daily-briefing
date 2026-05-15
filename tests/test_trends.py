"""
趋势追踪测试
============
"""

import pytest
from src.processors.trends import detect_trend_keywords, extract_keywords


class TestDetectTrendKeywords:
    """趋势关键词检测测试"""
    
    def test_high_frequency_keywords(self):
        """测试高频关键词"""
        items = [
            {"title": "NVIDIA AI chip GPU"},
            {"title": "NVIDIA releases new chip"},
            {"title": "AI chip market grows"},
        ]
        trends = detect_trend_keywords(items, min_freq=2)
        assert "nvidia" in trends
        assert "chip" in trends
    
    def test_low_frequency_filtered(self):
        """测试低频关键词过滤"""
        items = [
            {"title": "NVIDIA AI chip"},
            {"title": "Tesla robot humanoid"},
            {"title": "OpenAI GPT model"},
        ]
        trends = detect_trend_keywords(items, min_freq=2)
        # 每个关键词只出现一次，应该为空
        assert len(trends) == 0
    
    def test_chinese_keywords(self):
        """测试中文关键词"""
        items = [
            {"title": "人工智能 芯片 突破"},
            {"title": "人工智能 大模型 发布"},
            {"title": "芯片 半导体 市场"},
        ]
        trends = detect_trend_keywords(items, min_freq=2)
        assert "人工智能" in trends
        assert "芯片" in trends
    
    def test_short_words_filtered(self):
        """测试短词过滤（长度<=2）"""
        items = [
            {"title": "AI is new"},
            {"title": "AI is great"},
        ]
        trends = detect_trend_keywords(items, min_freq=2)
        # "ai" 长度为2，应该被过滤
        assert "ai" not in trends
        # "is" 长度为2，应该被过滤
        assert "is" not in trends


class TestExtractKeywords:
    """关键词提取测试（与 dedup 模块一致）"""
    
    def test_basic_extraction(self):
        """测试基本提取"""
        kw = extract_keywords("AI chip GPU NVIDIA")
        assert "chip" in kw
        assert "gpu" in kw
        assert "nvidia" in kw
    
    def test_chinese_extraction(self):
        """测试中文提取"""
        kw = extract_keywords("人工智能 芯片")
        assert "人工智能" in kw
        assert "芯片" in kw
