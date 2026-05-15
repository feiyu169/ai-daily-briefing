"""
跨源聚类测试
============
测试 cross_source_cluster 函数的聚类准确性、动态阈值、关键词权重和跨域保留。
"""

from typing import Any, Dict, List

from src.processors.cross_source import (
    cross_source_cluster,
    _meaningful,
    _compute_weighted_jaccard,
    _compute_dynamic_threshold,
    _extract_domain,
)


class TestMeaningful:
    """有意义关键词筛选测试"""

    def test_english_short_words(self):
        """测试英文短词被过滤"""
        result = _meaningful({"ai", "is", "the", "chip"})
        assert "ai" not in result
        assert "is" not in result
        assert "the" not in result
        assert "chip" in result

    def test_chinese_chars_kept(self):
        """测试中文字符保留"""
        result = _meaningful({"人工智能", "芯片"})
        assert "人工智能" in result
        assert "芯片" in result

    def test_mixed_languages(self):
        """测试混合语言"""
        result = _meaningful({"ai", "breakthrough", "创新", "gpu"})
        assert "ai" not in result  # 2 字符 < 3 且非中文
        assert "breakthrough" in result  # 11 字符 > 3
        assert "创新" in result  # 中文
        # "gpu" 是 3 字符，<=3 且非中文，所以被过滤
        assert "gpu" not in result

    def test_empty_set(self):
        """测试空集合"""
        result = _meaningful(set())
        assert len(result) == 0


class TestComputeWeightedJaccard:
    """加权 Jaccard 相似度测试"""

    def test_identical_sets(self):
        """测试相同集合"""
        s = {"chip", "nvidia", "gpu"}
        assert _compute_weighted_jaccard(s, s) == 1.0

    def test_disjoint_sets(self):
        """测试不相交集合"""
        s1 = {"chip", "nvidia"}
        s2 = {"robot", "tesla"}
        assert _compute_weighted_jaccard(s1, s2) == 0.0

    def test_partial_overlap_weighted(self):
        """测试部分重叠（带权重）"""
        s1 = {"chip", "nvidia", "gpu"}
        s2 = {"nvidia", "gpu", "tesla"}
        # 带权重: intersection={nvidia,gpu} weight=2+2=4, union={chip,nvidia,gpu,tesla} weight=2+2+2+1=7
        freq = {"nvidia": 2, "gpu": 2, "chip": 2, "tesla": 1}
        result = _compute_weighted_jaccard(s1, s2, freq)
        # 计算: 交集权重 2*(1+2/2)=4, 并集权重 (1+2/2)+(1+2/2)+(1+2/2)+(1+1/2)=2+2+2+1.5=7.5
        # 4/7.5 ≈ 0.533
        assert result > 0.5
        assert result < 0.6

    def test_no_global_freq_fallback(self):
        """测试无全局频率时退化为标准 Jaccard"""
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        # 标准 Jaccard = 2/4 = 0.5
        result = _compute_weighted_jaccard(s1, s2, None)
        assert result == 0.5

    def test_empty_sets(self):
        """测试空集合"""
        assert _compute_weighted_jaccard(set(), {"a"}) == 0.0
        assert _compute_weighted_jaccard({"a"}, set()) == 0.0
        assert _compute_weighted_jaccard(set(), set()) == 0.0


class TestComputeDynamicThreshold:
    """动态阈值计算测试"""

    def test_large_dataset_lowers_threshold(self):
        """测试大数据集降低阈值"""
        items = [
            {"title": f"AI news {i}", "source": f"source{i%5}"}
            for i in range(60)
        ]
        threshold = _compute_dynamic_threshold(items, base_threshold=0.35)
        assert threshold < 0.35
        assert threshold >= 0.25

    def test_small_dataset_raises_threshold(self):
        """测试小数据集提高阈值"""
        items = [
            {"title": "AI news", "source": "source1"},
            {"title": "Chip news", "source": "source2"},
            {"title": "Robot news", "source": "source3"},
        ]
        threshold = _compute_dynamic_threshold(items, base_threshold=0.35)
        assert threshold > 0.35
        assert threshold <= 0.5

    def test_medium_dataset_uses_base(self):
        """测试中等数据集使用基础阈值"""
        items = [
            {"title": f"AI news {i}", "source": f"source{i%3}"}
            for i in range(20)
        ]
        threshold = _compute_dynamic_threshold(items, base_threshold=0.35)
        assert threshold == 0.35

    def test_empty_items(self):
        """测试空列表视为小数据集，阈值提高"""
        threshold = _compute_dynamic_threshold([])
        # 空列表 < 10 条，阈值提高
        assert threshold > 0.35
        assert threshold <= 0.5


class TestExtractDomain:
    """域名提取测试"""

    def test_normal_url(self):
        """测试普通 URL"""
        assert _extract_domain("https://example.com/news") == "example.com"

    def test_url_with_subdomain(self):
        """测试带子域名的 URL"""
        assert _extract_domain("https://blog.example.com/article") == "blog.example.com"

    def test_url_with_port(self):
        """测试带端口的 URL"""
        assert _extract_domain("https://example.com:8080/path") == "example.com:8080"

    def test_empty_url(self):
        """测试空 URL"""
        assert _extract_domain("") == "unknown"

    def test_invalid_url(self):
        """测试无效 URL"""
        assert _extract_domain("not-a-url") == "unknown"


class TestCrossSourceCluster:
    """跨源聚类主函数测试"""

    def test_empty_items(self):
        """测试空条目列表"""
        result = cross_source_cluster([])
        assert result == []

    def test_single_item(self):
        """测试单一条目"""
        items = [
            {"title": "NVIDIA releases new AI chip", "source": "exa", "url": "https://exa.com/1"},
        ]
        result = cross_source_cluster(items)
        assert result == []

    def test_same_source_clusters(self):
        """测试同源不返回（至少需 2 个不同来源）"""
        items = [
            {"title": "NVIDIA AI chip", "source": "exa", "url": "https://exa.com/1"},
            {"title": "NVIDIA AI chip GPU", "source": "exa", "url": "https://exa.com/2"},
        ]
        result = cross_source_cluster(items)
        assert result == []

    def test_cross_source_clustering(self):
        """测试跨源聚类成功"""
        items = [
            {"title": "NVIDIA releases new AI chip GPU", "source": "exa", "url": "https://exa.com/1"},
            {"title": "NVIDIA launches powerful AI chip", "source": "github", "url": "https://github.com/1"},
        ]
        result = cross_source_cluster(items)
        assert len(result) >= 1
        assert result[0]["item_count"] == 2
        assert "nvidia" in result[0]["topic"]
        assert "chip" in result[0]["topic"]

    def test_different_topics_separated(self):
        """测试不同话题不合并"""
        items = [
            {"title": "NVIDIA AI chip GPU", "source": "exa", "url": "https://exa.com/1"},
            {"title": "Tesla robot humanoid", "source": "github", "url": "https://github.com/1"},
            {"title": "OpenAI GPT model", "source": "hackernews", "url": "https://hn.com/1"},
        ]
        result = cross_source_cluster(items)
        assert len(result) == 0  # 每个来源不同且话题不重叠

    def test_min_shared_keywords(self):
        """测试最小共享关键词匹配"""
        items = [
            {"title": "OpenAI ChatGPT breakthrough AGI", "source": "exa", "url": "https://exa.com/1"},
            {"title": "OpenAI ChatGPT model capabilities", "source": "github", "url": "https://github.com/1"},
        ]
        # meaningful keywords: "openai", "chatgpt", "breakthrough"/"model", "capabilities"
        # shared meaningful: {"openai", "chatgpt"} >= 2
        result = cross_source_cluster(items, min_shared=2)
        assert len(result) >= 1
        assert result[0]["item_count"] == 2

    def test_dynamic_threshold_large(self):
        """测试大数据集的动态阈值"""
        items = [
            {"title": f"AI machine learning breakthrough {i}", "source": f"source{i%6}", "url": f"https://s{i%6}.com/{i}"}
            for i in range(75)
        ]
        result = cross_source_cluster(items, use_dynamic_threshold=True)
        # 应该返回一些聚类
        assert isinstance(result, list)

    def test_weighted_jaccard(self):
        """测试加权 Jaccard"""
        items = [
            {"title": "NVIDIA chip GPU breakthrough", "source": "exa", "url": "https://exa.com/1"},
            {"title": "NVIDIA GPU AI training chip", "source": "github", "url": "https://github.com/1"},
        ]
        result = cross_source_cluster(items, enable_weighted_jaccard=True)
        assert len(result) >= 1

    def test_cross_domain_retention(self):
        """测试跨域保留，不同域名的相似文章仍能聚类"""
        items = [
            {"title": "AI chip breakthrough", "source": "exa", "url": "https://exa.com/news/1"},
            {"title": "AI chip breakthrough", "source": "hackernews", "url": "https://news.ycombinator.com/item?id=1"},
        ]
        result = cross_source_cluster(items, enable_cross_domain_retention=True)
        assert len(result) >= 1

    def test_limit_10_signals(self):
        """测试最多返回 10 个信号"""
        items = []
        for i in range(15):
            # 每组 2 条，来源不同
            items.append(
                {"title": f"Topic {i} news AI", "source": "exa", "url": f"https://exa.com/{i}"}
            )
            items.append(
                {"title": f"Topic {i} news update", "source": "github", "url": f"https://github.com/{i}"}
            )
        result = cross_source_cluster(items)
        assert len(result) <= 10

    def test_backward_compatible_defaults(self):
        """测试向后兼容性（默认参数应与旧版本一致）"""
        items = [
            {"title": "AI news", "source": "exa", "url": "https://exa.com/1"},
            {"title": "AI update", "source": "github", "url": "https://github.com/1"},
        ]
        # 使用默认参数（不应报错）
        result = cross_source_cluster(items)
        assert isinstance(result, list)

    def test_non_overlapping_cross_source(self):
        """测试非重叠的跨源话题（不同话题，相同来源不聚类）"""
        items = [
            {"title": "AI news", "source": "exa", "url": "https://exa.com/1"},
            {"title": "Chip news", "source": "exa", "url": "https://exa.com/2"},
        ]
        result = cross_source_cluster(items)
        assert result == []

    def test_multi_source_cluster(self):
        """测试三个不同来源的聚类"""
        items = [
            {"title": "OpenAI ChatGPT release AI", "source": "exa", "url": "https://exa.com/1"},
            {"title": "OpenAI ChatGPT model launch", "source": "github", "url": "https://github.com/1"},
            {"title": "OpenAI ChatGPT platform debut", "source": "hackernews", "url": "https://hn.com/1"},
        ]
        # All 3 share "openai" and "chatgpt" as meaningful keywords (7+ chars)
        result = cross_source_cluster(items)
        assert len(result) == 1
        assert len(result[0]["sources"]) == 3
        assert result[0]["item_count"] == 3
