"""
分类器测试
==========
"""

import pytest
from src.processors.classifier import classify_item


class TestClassifyItem:
    """分类器测试"""
    
    def test_funding_category(self):
        """测试融资/并购分类"""
        assert classify_item("AI startup raises $100M funding") == "融资/并购"
        assert classify_item("人工智能公司完成A轮融资") == "融资/并购"
    
    def test_product_release_category(self):
        """测试产品发布分类"""
        assert classify_item("OpenAI launches GPT-5") == "产品发布"
        assert classify_item("新版大模型正式上线") == "产品发布"
    
    def test_breakthrough_category(self):
        """测试技术突破分类"""
        assert classify_item("New research paper achieves SOTA") == "技术突破"
        assert classify_item("深度学习算法取得重大突破") == "技术突破"
    
    def test_policy_category(self):
        """测试政策/监管分类"""
        assert classify_item("AI regulation policy compliance") == "政策/监管"
        assert classify_item("政府人工智能监管法规") == "政策/监管"
        assert classify_item("Government AI safety alignment") == "政策/监管"
    
    def test_chip_category(self):
        """测试芯片/半导体分类"""
        assert classify_item("NVIDIA new AI chip GPU") == "芯片/半导体"
        assert classify_item("国产GPU芯片半导体") == "芯片/半导体"
        assert classify_item("TSMC new process node") == "芯片/半导体"
    
    def test_robot_category(self):
        """测试机器人/具身智能分类"""
        assert classify_item("Tesla Bot humanoid robot demo") == "机器人/具身智能"
        assert classify_item("人形机器人实现自主操作") == "机器人/具身智能"
        assert classify_item("Figure AI robot humanoid") == "机器人/具身智能"
    
    def test_default_category(self):
        """测试默认分类（行业动态）"""
        assert classify_item("Some random AI news") == "行业动态"
        assert classify_item("普通新闻") == "行业动态"
    
    def test_priority_order(self):
        """测试优先级顺序（融资 > 产品发布 > 技术突破）"""
        # 同时命中融资和产品发布
        assert classify_item("AI startup launches new product, raises $50M") == "融资/并购"
    
    def test_snippet_included(self):
        """测试 snippet 也被用于分类"""
        assert classify_item("New AI product", "This is a breakthrough in research") == "技术突破"
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert classify_item("NVIDIA AI CHIP GPU") == "芯片/半导体"
        assert classify_item("FUNDING ROUND VALUATION") == "融资/并购"
