# customer_support_chat/app/services/gds/base_adapter.py
"""GDS (Global Distribution System) 适配器基类

定义所有 GDS 操作的抽象接口，Agent 工具层通过此接口操作数据，
不感知底层是 SQLite、Amadeus、Sabre 或其他 GDS 提供商。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FlightInfo:
    """航班信息标准格式"""
    flight_id: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    airline: str
    price: float
    currency: str = "USD"
    status: str = "scheduled"
    cabin_class: str = "economy"


@dataclass
class HotelInfo:
    """酒店信息标准格式"""
    hotel_id: str
    name: str
    location: str
    price_per_night: float
    currency: str = "USD"
    rating: float = 0.0
    amenities: List[str] = field(default_factory=list)


@dataclass
class CarRentalInfo:
    """租车信息标准格式"""
    rental_id: str
    car_type: str
    company: str
    price_per_day: float
    currency: str = "USD"
    location: str = ""


class AbstractGDSAdapter(ABC):
    """GDS 适配器抽象基类。

    所有具体 GDS 实现（SQLite / Amadeus / Sabre 等）必须继承此类
    并实现下列方法。Agent 工具层只依赖此抽象接口。
    """

    # ------------------------------------------------------------------
    # Flights
    # ------------------------------------------------------------------
    @abstractmethod
    async def search_flights(
        self,
        origin: str = None,
        destination: str = None,
        date: str = None,
        **kwargs,
    ) -> List[FlightInfo]:
        """搜索航班"""

    @abstractmethod
    async def get_flight_by_id(self, flight_id: str) -> Optional[FlightInfo]:
        """按 ID 获取航班"""

    @abstractmethod
    async def update_flight_booking(
        self, ticket_no: str, new_flight_id: str, **kwargs
    ) -> Dict[str, Any]:
        """更新航班预订（写操作）"""

    @abstractmethod
    async def cancel_flight_booking(
        self, ticket_no: str, **kwargs
    ) -> Dict[str, Any]:
        """取消航班预订（写操作）"""

    # ------------------------------------------------------------------
    # Hotels
    # ------------------------------------------------------------------
    @abstractmethod
    async def search_hotels(
        self,
        location: str = None,
        checkin: str = None,
        checkout: str = None,
        **kwargs,
    ) -> List[HotelInfo]:
        """搜索酒店"""

    @abstractmethod
    async def book_hotel(
        self, hotel_id: str, guest_info: dict, **kwargs
    ) -> Dict[str, Any]:
        """预订酒店（写操作）"""

    @abstractmethod
    async def cancel_hotel_booking(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        """取消酒店预订"""

    # ------------------------------------------------------------------
    # Car Rentals
    # ------------------------------------------------------------------
    @abstractmethod
    async def search_car_rentals(
        self,
        location: str = None,
        pickup_date: str = None,
        return_date: str = None,
        **kwargs,
    ) -> List[CarRentalInfo]:
        """搜索租车"""

    @abstractmethod
    async def book_car_rental(
        self, rental_id: str, driver_info: dict, **kwargs
    ) -> Dict[str, Any]:
        """预订租车（写操作）"""

    @abstractmethod
    async def cancel_car_rental(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        """取消租车预订"""
