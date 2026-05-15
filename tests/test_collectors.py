"""
采集器测试
==========
使用 mock 测试采集器模块
"""

from unittest.mock import patch, MagicMock
from datetime import datetime


class TestExaCollector:
    """Exa 采集器测试"""

    @patch("src.utils.security.get_api_key")
    @patch("src.collectors.exa_collector.Exa")
    def test_collect_exa_success(self, mock_exa_cls, mock_get_api_key):
        """测试成功采集"""
        from src.collectors.exa_collector import collect_exa

        # Mock API key
        mock_get_api_key.return_value = "test_api_key"

        # Mock Exa client
        mock_exa = MagicMock()
        mock_exa_cls.return_value = mock_exa

        # Mock search result
        mock_result = MagicMock()
        mock_result.url = "https://example.com/1"
        mock_result.title = "Test Title"
        mock_result.text = "Test snippet"
        mock_result.published_date = datetime.now().strftime("%Y-%m-%d")

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_exa.search.return_value = mock_response

        # Execute
        results = collect_exa()

        # Verify
        assert isinstance(results, list)
        mock_exa.search.assert_called()

    @patch("src.utils.security.get_api_key")
    def test_collect_exa_no_api_key(self, mock_get_api_key):
        """测试无 API Key"""
        from src.collectors.exa_collector import collect_exa

        mock_get_api_key.return_value = None

        results = collect_exa()
        assert results == []

    @patch("src.utils.security.get_api_key")
    @patch("src.collectors.exa_collector.Exa")
    def test_collect_exa_api_error(self, mock_exa_cls, mock_get_api_key):
        """测试 API 错误"""
        from src.collectors.exa_collector import collect_exa

        mock_get_api_key.return_value = "test_api_key"
        mock_exa = MagicMock()
        mock_exa_cls.return_value = mock_exa
        mock_exa.search.side_effect = Exception("API Error")

        results = collect_exa()
        assert isinstance(results, list)


class TestGithubCollector:
    """GitHub 采集器测试"""

    @patch("src.utils.security.get_api_key")
    @patch("urllib.request.urlopen")
    def test_collect_github_success(self, mock_urlopen, mock_get_api_key):
        """测试成功采集"""
        from src.collectors.github_collector import collect_github

        mock_get_api_key.return_value = "test_token"

        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items": [{"html_url": "https://github.com/test/repo", "full_name": "test/repo", "description": "Test", "stargazers_count": 100, "forks_count": 10, "language": "Python", "topics": ["ai"], "updated_at": "2026-05-15", "created_at": "2026-05-15"}]}'
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = collect_github()
        assert isinstance(results, list)

    @patch("src.utils.security.get_api_key")
    def test_collect_github_no_token(self, mock_get_api_key):
        """测试无 Token"""
        from src.collectors.github_collector import collect_github

        mock_get_api_key.return_value = None

        # 应该仍然可以工作（只是速率限制较低）
        results = collect_github()
        assert isinstance(results, list)


class TestTrendingCollector:
    """GitHub Trending 采集器测试"""

    @patch("src.utils.security.get_api_key")
    @patch("src.collectors.trending_collector.Exa")
    def test_collect_trending_success(self, mock_exa_cls, mock_get_api_key):
        """测试成功采集"""
        from src.collectors.trending_collector import collect_github_trending

        mock_get_api_key.return_value = "test_api_key"

        # Mock Exa client
        mock_exa = MagicMock()
        mock_exa_cls.return_value = mock_exa

        # Mock search result
        mock_result = MagicMock()
        mock_result.url = "https://github.com/test/repo"
        mock_result.title = "Test Repo"
        mock_result.text = "Test description"
        mock_result.published_date = datetime.now().strftime("%Y-%m-%d")

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_exa.search.return_value = mock_response

        results = collect_github_trending()
        assert isinstance(results, list)

    @patch("src.utils.security.get_api_key")
    def test_collect_trending_no_api_key(self, mock_get_api_key):
        """测试无 API Key"""
        from src.collectors.trending_collector import collect_github_trending

        mock_get_api_key.return_value = None

        results = collect_github_trending()
        assert results == []
