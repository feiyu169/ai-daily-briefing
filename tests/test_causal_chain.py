"""
因果链分析测试
==============
测试 detect_causal_chains 的因果链检测功能。
"""

from src.processors.causal_chain import (
    detect_causal_chains,
    _extract_causal_pairs,
    _build_chain,
)


class TestExtractCausalPairs:
    """因果对提取测试"""

    def test_no_items(self):
        """测试空列表"""
        pairs = _extract_causal_pairs([])
        assert pairs == []

    def test_causal_pair_detection(self):
        """测试因果对检测"""
        items = [
            {
                "title": "Company A raises $100M funding",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Following funding, Company A plans expansion",
                "published": "2026-05-16",
                "source": "github",
                "url": "https://github.com/1",
            },
        ]
        pairs = _extract_causal_pairs(items, time_window_hours=48)
        # "funding" 是共享实体，"following" 是因果指示词
        assert len(pairs) >= 1

    def test_no_indicator_no_pair(self):
        """测试无因果指示词时不应匹配"""
        items = [
            {
                "title": "Company A raises $100M",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Company A product update",
                "published": "2026-05-16",
                "source": "github",
                "url": "https://github.com/1",
            },
        ]
        pairs = _extract_causal_pairs(items, time_window_hours=48)
        # "funding" 不是实体（5字符），"product" 也不是因果词
        # 共享实体可能是 "company" 但无指示词
        # 实际上 company 是 7 字符 > 4，算实体；但无因果指示词
        assert len(pairs) == 0

    def test_time_window_respected(self):
        """测试时间窗口限制"""
        items = [
            {
                "title": "Company A raises $100M funding",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Because of funding, Company A expands",
                "published": "2026-05-20",
                "source": "github",
                "url": "https://github.com/1",
            },
        ]
        pairs = _extract_causal_pairs(items, time_window_hours=48)
        # 5 天 > 48 小时，所以不应匹配
        assert len(pairs) == 0

    def test_chinese_causal_indicators(self):
        """测试中文因果指示词"""
        items = [
            {
                "title": "公司A完成100亿融资",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "受此影响，公司A股价大涨",
                "published": "2026-05-15",
                "source": "github",
                "url": "https://github.com/1",
            },
        ]
        pairs = _extract_causal_pairs(items, time_window_hours=48)
        assert len(pairs) >= 1

    def test_no_dates_skipped(self):
        """测试无日期条目被跳过"""
        items = [
            {
                "title": "Company A raises funding",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Following funding, Company A expands",
                "published": "unknown",
                "source": "github",
                "url": "https://github.com/1",
            },
        ]
        pairs = _extract_causal_pairs(items)
        assert len(pairs) == 0


class TestBuildChain:
    """因果链构建测试"""

    def test_min_chain_length(self):
        """测试最小链长度"""
        # 构建 2 个因果对，形成 3 事件链
        item_a = {"title": "Event A funding", "published": "2026-05-15", "source": "s1"}
        item_b = {"title": "After funding, Event B triggered", "published": "2026-05-16", "source": "s2"}
        item_c = {"title": "Because of B, Event C happens", "published": "2026-05-17", "source": "s3"}

        pairs = [
            {"earlier": item_a, "later": item_b, "confidence": 0.7, "reason": "test"},
            {"earlier": item_b, "later": item_c, "confidence": 0.6, "reason": "test"},
        ]
        chains = _build_chain(pairs, min_chain_length=3)
        assert len(chains) >= 1
        assert chains[0]["length"] >= 3

    def test_short_chain_filtered(self):
        """测试短链被过滤"""
        item_a = {"title": "Event A", "published": "2026-05-15", "source": "s1"}
        item_b = {"title": "After A, Event B", "published": "2026-05-16", "source": "s2"}

        pairs = [
            {"earlier": item_a, "later": item_b, "confidence": 0.7, "reason": "test"},
        ]
        chains = _build_chain(pairs, min_chain_length=3)
        # 只有 2 个事件，小于最小长度 3
        assert len(chains) == 0

    def test_deduplication(self):
        """测试链去重"""
        item_a = {"title": "Event A", "published": "2026-05-15", "source": "s1"}
        item_b = {"title": "After A, Event B", "published": "2026-05-16", "source": "s2"}
        item_c = {"title": "Because of B, Event C", "published": "2026-05-17", "source": "s3"}

        pairs = [
            {"earlier": item_a, "later": item_b, "confidence": 0.7, "reason": "test"},
            {"earlier": item_b, "later": item_c, "confidence": 0.6, "reason": "test"},
        ]
        chains = _build_chain(pairs, min_chain_length=3)
        # 只有一条链（A→B→C），没有被重复添加
        assert len(chains) == 1
        assert chains[0]["length"] == 3


class TestDetectCausalChains:
    """因果链检测主函数测试"""

    def test_empty_items(self):
        """测试空列表"""
        chains = detect_causal_chains([])
        assert chains == []

    def test_too_few_items(self):
        """测试条目太少"""
        items = [
            {"title": "Event A", "published": "2026-05-15", "source": "s1"},
        ]
        chains = detect_causal_chains(items, min_chain_length=3)
        assert chains == []

    def test_causal_chain_detection(self):
        """测试完整因果链检测"""
        items = [
            {
                "title": "OpenAI releases GPT-5 breakthrough",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Following GPT-5 release, AI stocks surge",
                "published": "2026-05-15",
                "source": "github",
                "url": "https://github.com/1",
            },
            {
                "title": "Because of AI stock surge, investors pour capital",
                "published": "2026-05-16",
                "source": "hackernews",
                "url": "https://hn.com/1",
            },
        ]
        chains = detect_causal_chains(items, time_window_hours=48, min_chain_length=2)
        assert len(chains) >= 1

    def test_disjoint_events_no_chain(self):
        """测试不相关事件不构成链"""
        items = [
            {
                "title": "NVIDIA chip release",
                "published": "2026-05-15",
                "source": "exa",
                "url": "https://exa.com/1",
            },
            {
                "title": "Tesla robot update",
                "published": "2026-05-16",
                "source": "github",
                "url": "https://github.com/1",
            },
            {
                "title": "OpenAI model launch",
                "published": "2026-05-17",
                "source": "hackernews",
                "url": "https://hn.com/1",
            },
        ]
        chains = detect_causal_chains(items)
        assert chains == []

    def test_max_chains_limit(self):
        """测试最大链数限制"""
        items = []
        for i in range(5):
            items.append({
                "title": f"Event A{i} funding",
                "published": "2026-05-15",
                "source": f"s{i}",
                "url": f"https://s{i}.com/{i}",
            })
            items.append({
                "title": f"Following funding, Event A{i} grows",
                "published": "2026-05-16",
                "source": f"s{i}_2",
                "url": f"https://s{i}_2.com/{i}",
            })
            items.append({
                "title": f"Because of growth, Event A{i} expands",
                "published": "2026-05-17",
                "source": f"s{i}_3",
                "url": f"https://s{i}_3.com/{i}",
            })

        chains = detect_causal_chains(items, max_chains=2)
        assert len(chains) <= 2
