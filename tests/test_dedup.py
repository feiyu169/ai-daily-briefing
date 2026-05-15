"""
去重器测试
==========
"""

from src.processors.dedup import (
    extract_keywords,
    jaccard_similarity,
    semantic_dedup,
    dedup_and_filter,
)


class TestExtractKeywords:
    """关键词提取测试"""
    
    def test_english_keywords(self):
        """测试英文关键词提取"""
        kw = extract_keywords("AI chip GPU NVIDIA semiconductor")
        assert "chip" in kw
        assert "gpu" in kw
        assert "nvidia" in kw
        assert "semiconductor" in kw
    
    def test_chinese_keywords(self):
        """测试中文关键词提取"""
        kw = extract_keywords("人工智能 芯片 半导体")
        assert "人工智能" in kw
        assert "芯片" in kw
        assert "半导体" in kw
    
    def test_stop_words_filtered(self):
        """测试停用词过滤"""
        kw = extract_keywords("The AI is a new breakthrough")
        assert "the" not in kw
        assert "is" not in kw
        assert "a" not in kw
        assert "new" not in kw  # "new" is in stop words
        assert "breakthrough" in kw
    
    def test_single_char_filtered(self):
        """测试单字符过滤"""
        kw = extract_keywords("A I chip")
        # 单字符应该被过滤
        assert "a" not in kw
        assert "i" not in kw
    
    def test_empty_title(self):
        """测试空标题"""
        kw = extract_keywords("")
        assert len(kw) == 0


class TestJaccardSimilarity:
    """Jaccard 相似度测试"""
    
    def test_identical_sets(self):
        """测试相同集合"""
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0
    
    def test_disjoint_sets(self):
        """测试不相交集合"""
        s1 = {"a", "b"}
        s2 = {"c", "d"}
        assert jaccard_similarity(s1, s2) == 0.0
    
    def test_partial_overlap(self):
        """测试部分重叠"""
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        # intersection = {b, c}, union = {a, b, c, d}
        assert jaccard_similarity(s1, s2) == 0.5
    
    def test_empty_sets(self):
        """测试空集合"""
        assert jaccard_similarity(set(), {"a"}) == 0.0
        assert jaccard_similarity({"a"}, set()) == 0.0
        assert jaccard_similarity(set(), set()) == 0.0


class TestSemanticDedup:
    """语义去重测试"""
    
    def test_no_duplicates(self):
        """测试无重复"""
        items = [
            {"title": "AI chip NVIDIA"},
            {"title": "Robot humanoid Tesla"},
            {"title": "LLM GPT Claude"},
        ]
        result = semantic_dedup(items, threshold=0.5)
        assert len(result) == 3
    
    def test_exact_duplicates(self):
        """测试完全重复"""
        items = [
            {"title": "AI chip NVIDIA GPU"},
            {"title": "AI chip NVIDIA GPU"},
        ]
        result = semantic_dedup(items, threshold=0.5)
        assert len(result) == 1
    
    def test_similar_duplicates(self):
        """测试相似重复"""
        items = [
            {"title": "NVIDIA releases new AI chip"},
            {"title": "NVIDIA launches new AI chip"},
        ]
        result = semantic_dedup(items, threshold=0.5)
        assert len(result) == 1
    
    def test_different_topics_kept(self):
        """测试不同话题保留"""
        items = [
            {"title": "NVIDIA AI chip GPU"},
            {"title": "Tesla robot humanoid"},
            {"title": "OpenAI GPT model"},
        ]
        result = semantic_dedup(items, threshold=0.5)
        assert len(result) == 3


class TestDedupAndFilter:
    """综合去重测试"""
    
    def test_noise_filtering(self):
        """测试噪声过滤"""
        items = [
            {"title": "AI news", "url": "https://example.com/1", "published": "2026-05-15"},
            {"title": "Dataset", "url": "https://huggingface.co/datasets/123", "published": "2026-05-15"},
            {"title": "Kaggle", "url": "https://kaggle.com/competition", "published": "2026-05-15"},
        ]
        result = dedup_and_filter(items, {})
        assert len(result) == 1
        assert result[0]["title"] == "AI news"
    
    def test_date_filtering(self):
        """测试日期过滤"""
        items = [
            {"title": "Recent", "url": "https://example.com/1", "published": "2026-05-15"},
            {"title": "Old", "url": "https://example.com/2", "published": "2026-05-01"},
            {"title": "Unknown", "url": "https://example.com/3", "published": "unknown"},
        ]
        result = dedup_and_filter(items, {})
        assert len(result) == 1
        assert result[0]["title"] == "Recent"
    
    def test_url_history_dedup(self):
        """测试 URL 历史去重"""
        items = [
            {"title": "New", "url": "https://example.com/1", "published": "2026-05-15"},
            {"title": "Seen yesterday", "url": "https://example.com/2", "published": "2026-05-15"},
        ]
        url_history = {"https://example.com/2": "2026-05-14"}
        result = dedup_and_filter(items, url_history)
        assert len(result) == 1
        assert result[0]["title"] == "New"
