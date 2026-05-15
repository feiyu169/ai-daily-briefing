"""
配额监控测试
============
"""

from unittest.mock import patch

from src.utils.quota import (
    load_quota,
    record_api_call,
    check_quota,
    get_degradation_strategy,
    log_quota_status,
)


class TestLoadQuota:
    """加载配额测试"""

    def test_load_quota_default(self):
        """测试默认配额"""
        with patch("src.utils.quota.load_json_file") as mock_load:
            # 模拟文件不存在的情况
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 0,
                    "monthly_usage": 0,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            quota = load_quota()
            assert "exa" in quota
            assert quota["exa"]["daily_usage"] == 0

    def test_load_quota_existing(self):
        """测试加载已有配额"""
        with patch("src.utils.quota.load_json_file") as mock_load:
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 10,
                    "monthly_usage": 100,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            quota = load_quota()
            assert quota["exa"]["daily_usage"] == 10


class TestRecordApiCall:
    """记录 API 调用测试"""

    def test_record_api_call_new(self):
        """测试记录新 API 调用"""
        with patch("src.utils.quota.load_json_file") as mock_load, \
             patch("src.utils.quota.save_json_file") as mock_save:
            mock_load.return_value = {}
            record_api_call("exa", 1)
            mock_save.assert_called_once()

    def test_record_api_call_existing(self):
        """测试记录已有 API 调用"""
        with patch("src.utils.quota.load_json_file") as mock_load, \
             patch("src.utils.quota.save_json_file") as mock_save:
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 10,
                    "monthly_usage": 100,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            record_api_call("exa", 1)
            mock_save.assert_called_once()


class TestCheckQuota:
    """检查配额测试"""

    def test_check_quota_ok(self):
        """测试配额正常"""
        with patch("src.utils.quota.load_quota") as mock_load:
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 10,
                    "monthly_usage": 100,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            status = check_quota("exa")
            assert status["status"] == "ok"
            assert status["daily_ratio"] == 0.1

    def test_check_quota_warning(self):
        """测试配额警告"""
        with patch("src.utils.quota.load_quota") as mock_load:
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 85,
                    "monthly_usage": 850,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            status = check_quota("exa")
            assert status["status"] == "warning"

    def test_check_quota_critical(self):
        """测试配额临界"""
        with patch("src.utils.quota.load_quota") as mock_load:
            mock_load.return_value = {
                "exa": {
                    "daily_usage": 96,
                    "monthly_usage": 960,
                    "last_reset_date": "2026-05-16",
                    "last_reset_month": "2026-05",
                }
            }
            status = check_quota("exa")
            assert status["status"] == "critical"


class TestLogQuotaStatus:
    """log_quota_status 测试"""

    def test_log_quota_status_ok(self):
        """测试配额正常时日志记录"""
        with patch("src.utils.quota.check_quota") as mock_check, \
             patch("src.utils.quota.logger") as mock_logger:
            mock_check.return_value = {
                "status": "ok",
                "daily_ratio": 0.1,
                "monthly_ratio": 0.05,
            }
            log_quota_status("exa")
            # ok 状态不输出任何日志（不调用 logger.info/warning）
            mock_logger.info.assert_not_called()
            mock_logger.warning.assert_not_called()

    def test_log_quota_status_warning(self):
        """测试配额警告时日志记录"""
        with patch("src.utils.quota.check_quota") as mock_check, \
             patch("src.utils.quota.logger") as mock_logger:
            mock_check.return_value = {
                "status": "warning",
                "daily_ratio": 0.85,
                "monthly_ratio": 0.80,
            }
            log_quota_status("exa")
            mock_logger.info.assert_called_once()

    def test_log_quota_status_critical(self):
        """测试配额临界时日志记录"""
        with patch("src.utils.quota.check_quota") as mock_check, \
             patch("src.utils.quota.logger") as mock_logger:
            mock_check.return_value = {
                "status": "critical",
                "daily_ratio": 0.96,
                "monthly_ratio": 0.95,
            }
            log_quota_status("exa")
            mock_logger.warning.assert_called_once()


class TestGetDegradationStrategy:
    """获取降级策略测试"""

    def test_degradation_normal(self):
        """测试正常策略"""
        with patch("src.utils.quota.check_quota") as mock_check:
            mock_check.return_value = {
                "status": "ok",
                "daily_ratio": 0.1,
                "monthly_ratio": 0.1,
            }
            strategy = get_degradation_strategy("exa")
            assert strategy["should_degrade"] is False

    def test_degradation_warning(self):
        """测试警告策略"""
        with patch("src.utils.quota.check_quota") as mock_check:
            mock_check.return_value = {
                "status": "warning",
                "daily_ratio": 0.85,
                "monthly_ratio": 0.85,
            }
            strategy = get_degradation_strategy("exa")
            assert strategy["should_degrade"] is False

    def test_degradation_critical(self):
        """测试临界策略"""
        with patch("src.utils.quota.check_quota") as mock_check:
            mock_check.return_value = {
                "status": "critical",
                "daily_ratio": 0.96,
                "monthly_ratio": 0.96,
            }
            strategy = get_degradation_strategy("exa")
            assert strategy["should_degrade"] is True
            assert strategy["reduction_ratio"] == 0.5
