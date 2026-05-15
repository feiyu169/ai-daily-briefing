"""
交付模块
========
支持多输出通道：stdout、文件、飞书等
"""

from .channels import (
    DeliveryChannel,
    DeliveryManager,
    FileChannel,
    StdoutChannel,
    create_default_delivery,
)

__all__ = [
    "DeliveryChannel",
    "DeliveryManager",
    "FileChannel",
    "StdoutChannel",
    "create_default_delivery",
]
