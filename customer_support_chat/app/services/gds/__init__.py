# customer_support_chat/app/services/gds/__init__.py
"""GDS (Global Distribution System) 适配器层。

通过 AbstractGDSAdapter 抽象接口屏蔽底层数据源差异，使 Agent 工具层
不感知具体数据来源（SQLite / Amadeus / Sabre 等）。

使用方式:
    from customer_support_chat.app.services.gds import get_gds_adapter
    adapter = get_gds_adapter()
    flights = await adapter.search_flights(origin="PEK", destination="PVG")
"""

from .base_adapter import (
    AbstractGDSAdapter,
    FlightInfo,
    HotelInfo,
    CarRentalInfo,
)
from .adapter_factory import get_gds_adapter, reset_adapter

__all__ = [
    "AbstractGDSAdapter",
    "FlightInfo",
    "HotelInfo",
    "CarRentalInfo",
    "get_gds_adapter",
    "reset_adapter",
]
