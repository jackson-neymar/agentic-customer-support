# customer_support_chat/app/services/gds/mock_amadeus_adapter.py
"""Mock Amadeus GDS 适配器实现。

通过 MCPServiceRegistry 调用 AmadeusMockService 获取航班数据，并将
MCP 返回的 JSON 转换为标准 dataclass。酒店与租车操作 Amadeus Mock
不直接覆盖，这里返回简单的本地 Mock 数据。
"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_adapter import (
    AbstractGDSAdapter,
    FlightInfo,
    HotelInfo,
    CarRentalInfo,
)

logger = logging.getLogger(__name__)


class MockAmadeusAdapter(AbstractGDSAdapter):
    """Amadeus Mock 适配器：航班走 MCP，酒店/租车返回简单 Mock。"""

    def __init__(self, service_name: str = "amadeus") -> None:
        self.service_name = service_name
        self._registry = None
        self._direct_service = None

    # ------------------------------------------------------------------
    # 内部：获取 MCP 注册表 / 兜底直接实例化 AmadeusMockService
    # ------------------------------------------------------------------
    def _get_registry(self):
        if self._registry is None:
            try:
                from customer_support_chat.app.services.mcp import (
                    MCPServiceRegistry,
                )

                self._registry = MCPServiceRegistry()
            except Exception as exc:
                logger.warning("无法加载 MCPServiceRegistry: %s", exc)
                self._registry = None
        return self._registry

    def _get_direct_service(self):
        """注册表无 amadeus 服务时，直接构造一个本地实例兜底。"""
        if self._direct_service is None:
            try:
                from customer_support_chat.app.services.mcp.amadeus_service import (
                    AmadeusMockService,
                )

                self._direct_service = AmadeusMockService(name=self.service_name)
            except Exception as exc:
                logger.warning("无法加载 AmadeusMockService: %s", exc)
                self._direct_service = None
        return self._direct_service

    async def _invoke(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具，返回 dict 形式的数据；失败时返回 {} 。"""
        registry = self._get_registry()
        result = None
        if registry is not None and registry.get_tool(tool_name) is not None:
            try:
                result = await registry.invoke_tool(tool_name, args)
            except Exception as exc:
                logger.warning("MCP invoke_tool 失败: %s", exc)
                result = None

        if result is None:
            service = self._get_direct_service()
            if service is None:
                return {}
            try:
                result = await service.invoke_tool(tool_name, args)
            except Exception as exc:
                logger.warning("AmadeusMockService.invoke_tool 失败: %s", exc)
                return {}

        if not getattr(result, "success", False):
            logger.info(
                "Amadeus MCP 调用未成功: tool=%s err=%s",
                tool_name,
                getattr(result, "error", None),
            )
            return {}
        return getattr(result, "data", {}) or {}

    # ------------------------------------------------------------------
    # Flights
    # ------------------------------------------------------------------
    async def search_flights(
        self,
        origin: str = None,
        destination: str = None,
        date: str = None,
        **kwargs,
    ) -> List[FlightInfo]:
        if not (origin and destination and date):
            logger.info(
                "MockAmadeusAdapter.search_flights 缺少必要参数 origin/destination/date"
            )
            return []
        args = {
            "origin": origin,
            "destination": destination,
            "departure_date": date,
            "adults": kwargs.get("adults", 1),
            "cabin_class": kwargs.get("cabin_class", "ECONOMY"),
            "max_results": kwargs.get("limit", 5),
        }
        data = await self._invoke("search_flights", args)
        flights = data.get("flights") or []
        results: List[FlightInfo] = []
        for f in flights:
            results.append(
                FlightInfo(
                    flight_id=f.get("flight_number", ""),
                    flight_number=f.get("flight_number", ""),
                    departure_airport=f.get("departure_airport", ""),
                    arrival_airport=f.get("arrival_airport", ""),
                    departure_time=f.get("departure_time", ""),
                    arrival_time=f.get("arrival_time", ""),
                    airline=f.get("airline", ""),
                    price=float(f.get("price") or 0.0),
                    currency=f.get("currency", "USD"),
                    status=str(f.get("status", "scheduled")).lower(),
                    cabin_class=str(f.get("cabin_class", "economy")).lower(),
                )
            )
        return results

    async def get_flight_by_id(self, flight_id: str) -> Optional[FlightInfo]:
        if not flight_id:
            return None
        data = await self._invoke(
            "get_flight_status",
            {"flight_number": flight_id},
        )
        if not data:
            return None
        return FlightInfo(
            flight_id=str(data.get("flight_number") or flight_id),
            flight_number=str(data.get("flight_number") or flight_id),
            departure_airport=data.get("departure_airport", ""),
            arrival_airport=data.get("arrival_airport", ""),
            departure_time=data.get("scheduled_departure", ""),
            arrival_time=data.get("scheduled_arrival", ""),
            airline=data.get("airline", ""),
            price=0.0,
            status=str(data.get("status", "scheduled")).lower(),
        )

    async def update_flight_booking(
        self, ticket_no: str, new_flight_id: str, **kwargs
    ) -> Dict[str, Any]:
        # Amadeus Mock 不持久化预订，这里返回模拟的成功响应
        passenger_name = kwargs.get("passenger_name", "Passenger")
        departure_date = kwargs.get(
            "departure_date", datetime.now().strftime("%Y-%m-%d")
        )
        cabin_class = kwargs.get("cabin_class", "ECONOMY")
        data = await self._invoke(
            "book_flight",
            {
                "flight_number": new_flight_id,
                "departure_date": departure_date,
                "passenger_name": passenger_name,
                "cabin_class": cabin_class,
            },
        )
        if not data:
            return {
                "success": False,
                "message": (
                    f"Failed to update ticket {ticket_no} via Amadeus Mock."
                ),
            }
        return {
            "success": True,
            "message": (
                f"Ticket {ticket_no} updated to flight {new_flight_id} "
                f"(booking_id={data.get('booking_id')})."
            ),
            "ticket_no": ticket_no,
            "new_flight_id": new_flight_id,
            "booking": data,
        }

    async def cancel_flight_booking(
        self, ticket_no: str, **kwargs
    ) -> Dict[str, Any]:
        # Amadeus Mock 无真实订单库，这里直接返回成功响应
        return {
            "success": True,
            "message": f"Ticket {ticket_no} cancelled (amadeus_mock).",
            "ticket_no": ticket_no,
            "source": "amadeus_mock",
        }

    # ------------------------------------------------------------------
    # Hotels (Amadeus Mock 未直接提供，使用本地 Mock)
    # ------------------------------------------------------------------
    async def search_hotels(
        self,
        location: str = None,
        checkin: str = None,
        checkout: str = None,
        **kwargs,
    ) -> List[HotelInfo]:
        rng = random.Random((location or "city") + (checkin or ""))
        chains = ["Hilton", "Marriott", "Hyatt", "InterContinental", "Holiday Inn"]
        hotels = []
        for i in range(min(int(kwargs.get("limit", 3)), 5)):
            hotels.append(
                HotelInfo(
                    hotel_id=f"AMA-HTL-{rng.randint(10000, 99999)}",
                    name=f"{rng.choice(chains)} {(location or 'City').title()}",
                    location=location or "",
                    price_per_night=round(80 + rng.uniform(0, 320), 2),
                    rating=round(rng.uniform(3.5, 5.0), 1),
                    amenities=["wifi", "breakfast", "parking"],
                )
            )
        return hotels

    async def book_hotel(
        self, hotel_id: str, guest_info: dict, **kwargs
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Hotel {hotel_id} booked (amadeus_mock).",
            "hotel_id": hotel_id,
            "guest_info": guest_info or {},
            "source": "amadeus_mock",
        }

    async def cancel_hotel_booking(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Hotel booking {booking_id} cancelled (amadeus_mock).",
            "hotel_id": booking_id,
            "source": "amadeus_mock",
        }

    # ------------------------------------------------------------------
    # Car Rentals (Mock)
    # ------------------------------------------------------------------
    async def search_car_rentals(
        self,
        location: str = None,
        pickup_date: str = None,
        return_date: str = None,
        **kwargs,
    ) -> List[CarRentalInfo]:
        rng = random.Random((location or "city") + (pickup_date or ""))
        companies = ["Hertz", "Avis", "Enterprise", "Budget", "Sixt"]
        car_types = ["Economy", "Compact", "SUV", "Van", "Luxury"]
        rentals = []
        for i in range(min(int(kwargs.get("limit", 3)), 5)):
            rentals.append(
                CarRentalInfo(
                    rental_id=f"AMA-CAR-{rng.randint(10000, 99999)}",
                    car_type=rng.choice(car_types),
                    company=rng.choice(companies),
                    price_per_day=round(30 + rng.uniform(0, 120), 2),
                    location=location or "",
                )
            )
        return rentals

    async def book_car_rental(
        self, rental_id: str, driver_info: dict, **kwargs
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Car rental {rental_id} booked (amadeus_mock).",
            "rental_id": rental_id,
            "driver_info": driver_info or {},
            "source": "amadeus_mock",
        }

    async def cancel_car_rental(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "message": f"Car rental {booking_id} cancelled (amadeus_mock).",
            "rental_id": booking_id,
            "source": "amadeus_mock",
        }
