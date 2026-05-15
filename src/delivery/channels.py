"""
交付模块
========
支持多输出通道：stdout、文件、飞书等
"""

import json
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DeliveryChannel(ABC):
    """交付通道基类"""

    @abstractmethod
    def deliver(self, data: Dict[str, Any]) -> bool:
        """交付数据
        
        Args:
            data: 要交付的数据
            
        Returns:
            是否成功
        """
        pass


class StdoutChannel(DeliveryChannel):
    """标准输出通道"""

    def deliver(self, data: Dict[str, Any]) -> bool:
        """输出到标准输出"""
        try:
            print(json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            print(f"输出到 stdout 失败: {e}", file=sys.stderr)
            return False


class FileChannel(DeliveryChannel):
    """文件输出通道"""

    def __init__(self, file_path: str):
        """初始化文件通道
        
        Args:
            file_path: 输出文件路径
        """
        self.file_path = file_path

    def deliver(self, data: Dict[str, Any]) -> bool:
        """输出到文件"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"输出到文件 {self.file_path} 失败: {e}", file=sys.stderr)
            return False


class DeliveryManager:
    """交付管理器"""

    def __init__(self):
        """初始化交付管理器"""
        self.channels: List[DeliveryChannel] = []

    def add_channel(self, channel: DeliveryChannel) -> None:
        """添加交付通道
        
        Args:
            channel: 交付通道实例
        """
        self.channels.append(channel)

    def deliver_all(self, data: Dict[str, Any]) -> Dict[str, bool]:
        """交付到所有通道
        
        Args:
            data: 要交付的数据
            
        Returns:
            各通道交付结果
        """
        results = {}
        for channel in self.channels:
            channel_name = channel.__class__.__name__
            results[channel_name] = channel.deliver(data)
        return results


def create_default_delivery(file_path: str) -> DeliveryManager:
    """创建默认交付管理器
    
    Args:
        file_path: 输出文件路径
        
    Returns:
        配置好的交付管理器
    """
    manager = DeliveryManager()
    manager.add_channel(StdoutChannel())
    manager.add_channel(FileChannel(file_path))
    return manager
