"""
共识/分歧分析测试
==================
测试 analyze_consensus 的共识/分歧分析功能。
"""

from src.processors.consensus import (
    analyze_consensus,
    compute_sentiment,
    build_consensus_keywords,
    extract_unique_perspectives,
)


class TestComputeSentiment:
    """情感计算测试"""

    def test_positive_sentiment(self):
        """测试正面情感"""
        label, score = compute_sentiment("AI breakthrough innovation milestone")
        assert label == "positive"
        assert score > 0

    def test_negative_sentiment(self):
        """测试负面情感"""
        label, score = compute_sentiment("AI safety concerns warning risk")
        assert label == "negative"
        assert score < 0

    def test_neutral_sentiment(self):
        """测试中性情感"""
        label, score = compute_sentiment("AI chip news update")
        assert label == "neutral"
        assert score == 0.0

    def test_mixed_sentiment(self):
        """测试混合情感（中性）"""
        label, score = compute_sentiment("AI breakthrough but safety concerns")
        assert label in ("positive", "negative", "neutral")

    def test_empty_title(self):
        """测试空标题"""
        label, score = compute_sentiment("")
        assert label == "neutral"
        assert score == 0.0

    def test_chinese_positive(self):
        """测试中文正面"""
        label, score = compute_sentiment("重大突破 创新 里程碑")
        assert label == "positive"

    def test_chinese_negative(self):
        """测试中文负面"""
        label, score = compute_sentiment("风险 警告 危机 裁员")
        assert label == "negative"


class TestBuildConsensusKeywords:
    """共识关键词测试"""

    def test_single_source_no_consensus(self):
        """测试单来源无共识"""
        items = [
            {"title": "NVIDIA AI chip", "source": "exa"},
        ]
        result = build_consensus_keywords(items)
        assert result == []

    def test_consensus_detected(self):
        """测试共识检测"""
        items = [
            {"title": "NVIDIA releases AI chip", "source": "exa"},
            {"title": "NVIDIA AI chip breakthrough", "source": "github"},
        ]
        result = build_consensus_keywords(items)
        # "nvidia", "ai", "chip" 应该出现在两个来源中
        assert "nvidia" in result
        assert "chip" in result

    def test_no_consensus_different_topics(self):
        """测试不同话题无共识"""
        items = [
            {"title": "NVIDIA chip GPU release", "source": "exa"},
            {"title": "Tesla robot humanoid update", "source": "github"},
        ]
        result = build_consensus_keywords(items)
        # 没有共同关键词: nvidia/chip/gpu/release vs tesla/robot/humanoid/update
        assert len(result) == 0

    def test_multiple_sources_consensus(self):
        """测试多来源共识"""
        items = [
            {"title": "OpenAI GPT-5 release AGI", "source": "exa"},
            {"title": "OpenAI GPT-5 model AGI", "source": "github"},
            {"title": "OpenAI launches GPT-5", "source": "hackernews"},
        ]
        result = build_consensus_keywords(items)
        # "openai" 和 "gpt" 应该出现在所有来源中（需要超过 50%）
        assert "openai" in result


class TestExtractUniquePerspectives:
    """独特视角测试"""

    def test_unique_perspectives(self):
        """测试独特视角提取"""
        items = [
            {"title": "NVIDIA AI chip GPU breakthrough", "source": "exa"},
            {"title": "NVIDIA chip launches", "source": "github"},
        ]
        perspectives = extract_unique_perspectives(items)
        assert len(perspectives) >= 2
        # "gpu" 和 "breakthrough" 只在 exa 中出现
        # "launches" 只在 github 中出现
        assert "exa" in perspectives
        assert "github" in perspectives

    def test_single_source(self):
        """测试单来源"""
        items = [
            {"title": "NVIDIA AI chip", "source": "exa"},
        ]
        perspectives = extract_unique_perspectives(items)
        assert "exa" in perspectives

    def test_shared_keywords_not_unique(self):
        """测试共享关键词不是独特视角"""
        items = [
            {"title": "NVIDIA AI chip", "source": "exa"},
            {"title": "NVIDIA AI GPU", "source": "github"},
        ]
        perspectives = extract_unique_perspectives(items)
        # "nvidia" 和 "ai" 是共享词，不应出现在独特视角中
        for source_kws in perspectives.values():
            assert "nvidia" not in source_kws


class TestAnalyzeConsensus:
    """共识分析主函数测试"""

    def test_empty_clusters(self):
        """测试空聚类列表"""
        result = analyze_consensus([])
        assert result == []

    def test_single_item_cluster_skipped(self):
        """测试单条目聚类跳过"""
        result = analyze_consensus([
            [{"title": "AI news", "source": "exa"}],
        ])
        assert result == []

    def test_consensus_analysis(self):
        """测试共识分析"""
        clusters = [
            [
                {"title": "NVIDIA AI chip breakthrough GPU", "source": "exa"},
                {"title": "NVIDIA chip AI release", "source": "github"},
                {"title": "NVIDIA launches AI chip", "source": "hackernews"},
            ],
        ]
        result = analyze_consensus(clusters)
        assert len(result) == 1
        assert result[0]["item_count"] == 3
        assert len(result[0]["sources"]) == 3
        assert result[0]["consensus_level"] in ("高", "中", "低")
        assert "nvidia" in result[0]["consensus_keywords"]

    def test_multiple_clusters(self):
        """测试多聚类分析"""
        clusters = [
            [
                {"title": "NVIDIA AI chip", "source": "exa"},
                {"title": "NVIDIA chip GPU", "source": "github"},
            ],
            [
                {"title": "Tesla robot humanoid", "source": "exa"},
                {"title": "Tesla bot update", "source": "github"},
            ],
        ]
        result = analyze_consensus(clusters)
        assert len(result) == 2

    def test_sentiment_distribution(self):
        """测试情感分布"""
        clusters = [
            [
                {"title": "AI breakthrough innovation success", "source": "exa"},
                {"title": "AI safe concerns warning", "source": "github"},
                {"title": "AI chip news update", "source": "hackernews"},
            ],
        ]
        result = analyze_consensus(clusters)
        assert len(result) == 1
        assert "sentiment_distribution" in result[0]
        assert result[0]["dominant_sentiment"] in ("positive", "negative", "neutral")

    def test_divergence_count(self):
        """测试分歧计数"""
        clusters = [
            [
                {"title": "AI news", "source": "exa"},
                {"title": "AI update", "source": "github"},
                {"title": "AI breakthrough", "source": "hackernews"},
            ],
        ]
        result = analyze_consensus(clusters)
        assert result[0]["divergence_count"] == 2  # 3 个来源，2 个分歧

    def test_overall_assessment(self):
        """测试总体评价"""
        clusters = [
            [
                {"title": "NVIDIA AI chip", "source": "exa"},
                {"title": "NVIDIA chip", "source": "github"},
            ],
        ]
        result = analyze_consensus(clusters)
        assert "overall_assessment" in result[0]
        assert "来源" in result[0]["overall_assessment"]
