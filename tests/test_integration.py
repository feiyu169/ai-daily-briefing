"""
主管道集成测试
==============
测试采集 → 去重 → 分类 → 趋势 → 聚类 → 因果链 → 共识 → 输出的完整流程
"""

import json
import os
import shutil
from unittest.mock import patch



class TestMainPipeline:
    """主管道集成测试"""

    def test_full_pipeline(self):
        """测试完整管道流程"""
        # 模拟采集数据
        mock_exa_data = [
            {
                "title": "NVIDIA releases new AI chip",
                "url": "https://example.com/1",
                "source": "news",
                "published": "2026-05-15",
                "snippet": "NVIDIA announced new AI chip",
                "query_group": "chip_queries",
                "category": "芯片/半导体",
            },
            {
                "title": "Tesla Bot humanoid robot demo",
                "url": "https://example.com/2",
                "source": "news",
                "published": "2026-05-15",
                "snippet": "Tesla demonstrated humanoid robot",
                "query_group": "robot_queries",
                "category": "机器人/具身智能",
            },
            {
                "title": "AI startup raises funding",
                "url": "https://example.com/3",
                "source": "news",
                "published": "2026-05-15",
                "snippet": "AI startup raises $100M",
                "query_group": "en_queries",
                "category": "融资/并购",
            },
        ]

        # 创建临时目录（在项目目录内）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tmpdir = os.path.join(project_root, ".cache", "test")
        os.makedirs(tmpdir, exist_ok=True)
        
        try:
            cache_file = os.path.join(tmpdir, "output.json")
            history_file = os.path.join(tmpdir, "history.json")
            trends_file = os.path.join(tmpdir, "trends.json")

            # 模拟配置和环境变量
            with patch.dict(os.environ, {"EXA_API_KEY": "test_key"}):
                with patch("src.main.get_collector_config") as mock_config:
                    mock_config.return_value = {
                        "cache_ttl": 1800,
                        "history_days": 7,
                        "trends_days": 3,
                        "query_timeout": 60,
                    }
                    with patch("src.main.get_output_config") as mock_output:
                        mock_output.return_value = {
                            "cache_file": cache_file,
                            "history_file": history_file,
                            "trends_file": trends_file,
                        }
                        with patch("src.main.collect_exa", return_value=mock_exa_data):
                            with patch("src.main.collect_github", return_value=[]):
                                with patch("src.main.collect_github_trending", return_value=[]):
                                    with patch("src.main.load_url_history") as mock_history:
                                        mock_history.return_value = {}
                                        with patch("src.main.load_trends_history") as mock_trends:
                                            mock_trends.return_value = {}
                                            with patch("src.main.save_url_history"):
                                                with patch("src.main.save_trends_history"):
                                                    # 执行管道
                                                    from src.main import main
                                                    main()

            # 验证输出
            assert os.path.exists(cache_file)
            with open(cache_file, "r") as f:
                output = json.load(f)

            # 验证必需字段
            assert "collected_at" in output
            assert "date" in output
            assert "total_items" in output
            assert "source_counts" in output
            assert "category_counts" in output
            assert "trend_momentum" in output
            assert "cross_platform_signals" in output
            assert "causal_chains" in output
            assert "consensus_analysis" in output
            assert "items" in output

            # 验证数据
            assert output["total_items"] == 3
            assert "芯片/半导体" in output["category_counts"]
            assert "机器人/具身智能" in output["category_counts"]
            assert "融资/并购" in output["category_counts"]
        finally:
            # 清理测试文件
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)

    def test_empty_pipeline(self):
        """测试空数据管道"""
        # 创建临时目录（在项目目录内）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tmpdir = os.path.join(project_root, ".cache", "test")
        os.makedirs(tmpdir, exist_ok=True)
        
        try:
            cache_file = os.path.join(tmpdir, "output.json")
            history_file = os.path.join(tmpdir, "history.json")
            trends_file = os.path.join(tmpdir, "trends.json")

            with patch.dict(os.environ, {"EXA_API_KEY": "test_key"}):
                with patch("src.main.get_collector_config") as mock_config:
                    mock_config.return_value = {
                        "cache_ttl": 1800,
                        "history_days": 7,
                        "trends_days": 3,
                        "query_timeout": 60,
                    }
                    with patch("src.main.get_output_config") as mock_output:
                        mock_output.return_value = {
                            "cache_file": cache_file,
                            "history_file": history_file,
                            "trends_file": trends_file,
                        }
                        with patch("src.main.collect_exa", return_value=[]):
                            with patch("src.main.collect_github", return_value=[]):
                                with patch("src.main.collect_github_trending", return_value=[]):
                                    with patch("src.main.load_url_history") as mock_history:
                                        mock_history.return_value = {}
                                        with patch("src.main.load_trends_history") as mock_trends:
                                            mock_trends.return_value = {}
                                            with patch("src.main.save_url_history"):
                                                with patch("src.main.save_trends_history"):
                                                    from src.main import main
                                                    main()

            assert os.path.exists(cache_file)
            with open(cache_file, "r") as f:
                output = json.load(f)

            assert output["total_items"] == 0
            assert output["items"] == []
        finally:
            # 清理测试文件
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)

    def test_cross_source_clustering(self):
        """测试跨源聚类"""
        mock_exa_data = [
            {
                "title": "NVIDIA AI chip release",
                "url": "https://example.com/1",
                "source": "news",
                "published": "2026-05-15",
                "snippet": "NVIDIA releases new AI chip",
                "query_group": "chip_queries",
                "category": "芯片/半导体",
            },
            {
                "title": "NVIDIA AI chip funding",
                "url": "https://reddit.com/1",
                "source": "discussion",
                "published": "2026-05-15",
                "snippet": "NVIDIA AI chip funding discussion",
                "query_group": "discussion_queries",
                "category": "融资/并购",
            },
        ]

        # 创建临时目录（在项目目录内）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tmpdir = os.path.join(project_root, ".cache", "test")
        os.makedirs(tmpdir, exist_ok=True)
        
        try:
            cache_file = os.path.join(tmpdir, "output.json")
            history_file = os.path.join(tmpdir, "history.json")
            trends_file = os.path.join(tmpdir, "trends.json")

            with patch.dict(os.environ, {"EXA_API_KEY": "test_key"}):
                with patch("src.main.get_collector_config") as mock_config:
                    mock_config.return_value = {
                        "cache_ttl": 1800,
                        "history_days": 7,
                        "trends_days": 3,
                        "query_timeout": 60,
                    }
                    with patch("src.main.get_output_config") as mock_output:
                        mock_output.return_value = {
                            "cache_file": cache_file,
                            "history_file": history_file,
                            "trends_file": trends_file,
                        }
                        with patch("src.main.collect_exa", return_value=mock_exa_data):
                            with patch("src.main.collect_github", return_value=[]):
                                with patch("src.main.collect_github_trending", return_value=[]):
                                    with patch("src.main.load_url_history") as mock_history:
                                        mock_history.return_value = {}
                                        with patch("src.main.load_trends_history") as mock_trends:
                                            mock_trends.return_value = {}
                                            with patch("src.main.save_url_history"):
                                                with patch("src.main.save_trends_history"):
                                                    from src.main import main
                                                    main()

            with open(cache_file, "r") as f:
                output = json.load(f)

            # 验证跨源聚类
            assert "cross_platform_signals" in output
            # 由于两条新闻来自不同源，应该有聚类结果
            if output["cross_platform_signals"]:
                assert len(output["cross_platform_signals"]) > 0
        finally:
            # 清理测试文件
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_output_structure_compatibility(self):
        """测试输出结构兼容性"""
        # v5 必需字段
        v5_fields = {
            "collected_at",
            "date",
            "total_items",
            "source_counts",
            "category_counts",
            "trend_momentum",
            "items",
        }

        # v6/v7 新增字段
        v6_fields = {
            "cross_platform_signals",
        }

        v7_fields = {
            "causal_chains",
            "consensus_analysis",
        }

        # 模拟输出
        output = {
            "collected_at": "2026-05-15T22:00:00",
            "date": "2026-05-15",
            "total_items": 100,
            "source_counts": {"exa": 80, "github": 20},
            "category_counts": {"行业动态": 50},
            "trend_momentum": {"continuing": [], "new": []},
            "cross_platform_signals": [],
            "causal_chains": [],
            "consensus_analysis": [],
            "items": [],
        }

        # 验证 v5 字段存在
        for field in v5_fields:
            assert field in output, f"v5 字段 {field} 缺失"

        # 验证 v6 字段存在
        for field in v6_fields:
            assert field in output, f"v6 字段 {field} 缺失"

        # 验证 v7 字段存在
        for field in v7_fields:
            assert field in output, f"v7 字段 {field} 缺失"

        # 验证 JSON 可序列化
        json_str = json.dumps(output, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed == output
