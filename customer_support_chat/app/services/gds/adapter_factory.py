# customer_support_chat/app/services/gds/adapter_factory.py
"""GDS 适配器工厂 - 根据配置返回对应实现。"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .base_adapter import AbstractGDSAdapter

logger = logging.getLogger(__name__)

_adapter_instance: Optional[AbstractGDSAdapter] = None


def get_gds_adapter() -> AbstractGDSAdapter:
    """获取 GDS 适配器单例（根据 GDS_PROVIDER 环境变量）。

    支持取值:
    - sqlite (默认)：使用本地 SQLite 数据库
    - amadeus_mock：通过 MCP 调用 Amadeus Mock
    """
    global _adapter_instance
    if _adapter_instance is None:
        provider = (os.environ.get("GDS_PROVIDER") or "sqlite").strip().lower()
        try:
            if provider == "amadeus_mock":
                from .mock_amadeus_adapter import MockAmadeusAdapter

                _adapter_instance = MockAmadeusAdapter()
                logger.info("GDS adapter 初始化: amadeus_mock")
            else:
                from .sqlite_adapter import SQLiteGDSAdapter

                _adapter_instance = SQLiteGDSAdapter()
                logger.info("GDS adapter 初始化: sqlite")
        except Exception as exc:
            logger.exception(
                "GDS adapter 初始化失败 (provider=%s): %s，回退到 SQLite",
                provider,
                exc,
            )
            from .sqlite_adapter import SQLiteGDSAdapter

            _adapter_instance = SQLiteGDSAdapter()
    return _adapter_instance


def reset_adapter() -> None:
    """重置适配器（用于配置切换 / 单测场景）。"""
    global _adapter_instance
    _adapter_instance = None
