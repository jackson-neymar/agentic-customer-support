# customer_support_chat/app/services/gds/sqlite_adapter.py
"""SQLite GDS 适配器实现。

将原本散落在 tools/flights.py, tools/hotels.py, tools/cars.py 中的
SQL 操作集中到此适配器内，统一通过 AbstractGDSAdapter 接口对外暴露。

注意：
- 所有方法以协程形式暴露，但 SQLite 操作本身是同步的，这里直接执行即可。
- 数据库路径来自 settings.SQLITE_DB_PATH。
- 异常被捕获并以 dict 形式返回，避免上层 Agent 工具因异常崩溃。
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Optional

from customer_support_chat.app.core.settings import get_settings
from .base_adapter import (
    AbstractGDSAdapter,
    FlightInfo,
    HotelInfo,
    CarRentalInfo,
)

logger = logging.getLogger(__name__)


class SQLiteGDSAdapter(AbstractGDSAdapter):
    """基于本地 SQLite 数据库 (travel2.sqlite) 的 GDS 适配器。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.db_path = db_path or settings.SQLITE_DB_PATH

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

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
        limit = int(kwargs.get("limit", 10))
        try:
            conn = self._connect()
            cursor = conn.cursor()
            sql = (
                "SELECT flight_id, flight_no, departure_airport, arrival_airport, "
                "scheduled_departure, scheduled_arrival, status FROM flights "
                "WHERE 1=1"
            )
            params: List[Any] = []
            if origin:
                sql += " AND departure_airport = ?"
                params.append(origin)
            if destination:
                sql += " AND arrival_airport = ?"
                params.append(destination)
            if date:
                sql += " AND DATE(scheduled_departure) = ?"
                params.append(date)
            sql += " LIMIT ?"
            params.append(limit)

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            return [
                FlightInfo(
                    flight_id=str(r[0]),
                    flight_number=r[1] or "",
                    departure_airport=r[2] or "",
                    arrival_airport=r[3] or "",
                    departure_time=str(r[4]) if r[4] else "",
                    arrival_time=str(r[5]) if r[5] else "",
                    airline="",
                    price=0.0,
                    status=r[6] or "scheduled",
                )
                for r in rows
            ]
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.search_flights 失败: %s", exc)
            return []

    async def get_flight_by_id(self, flight_id: str) -> Optional[FlightInfo]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT flight_id, flight_no, departure_airport, arrival_airport, "
                "scheduled_departure, scheduled_arrival, status FROM flights "
                "WHERE flight_id = ?",
                (flight_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return FlightInfo(
                flight_id=str(row[0]),
                flight_number=row[1] or "",
                departure_airport=row[2] or "",
                arrival_airport=row[3] or "",
                departure_time=str(row[4]) if row[4] else "",
                arrival_time=str(row[5]) if row[5] else "",
                airline="",
                price=0.0,
                status=row[6] or "scheduled",
            )
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.get_flight_by_id 失败: %s", exc)
            return None

    async def update_flight_booking(
        self, ticket_no: str, new_flight_id: str, **kwargs
    ) -> Dict[str, Any]:
        passenger_id = kwargs.get("passenger_id")
        try:
            conn = self._connect()
            cursor = conn.cursor()

            if passenger_id:
                cursor.execute(
                    "SELECT 1 FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
                    (ticket_no, passenger_id),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM tickets WHERE ticket_no = ?",
                    (ticket_no,),
                )
            if cursor.fetchone() is None:
                conn.close()
                return {
                    "success": False,
                    "message": f"Ticket {ticket_no} not found"
                    + (f" for passenger {passenger_id}" if passenger_id else ""),
                }

            cursor.execute(
                "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ?",
                (new_flight_id, ticket_no),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated > 0:
                return {
                    "success": True,
                    "message": f"Ticket {ticket_no} successfully updated to flight {new_flight_id}.",
                    "ticket_no": ticket_no,
                    "new_flight_id": new_flight_id,
                }
            return {
                "success": False,
                "message": f"Failed to update ticket {ticket_no}.",
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.update_flight_booking 失败: %s", exc)
            return {"success": False, "message": str(exc)}

    async def cancel_flight_booking(
        self, ticket_no: str, **kwargs
    ) -> Dict[str, Any]:
        passenger_id = kwargs.get("passenger_id")
        try:
            conn = self._connect()
            cursor = conn.cursor()
            if passenger_id:
                cursor.execute(
                    "SELECT 1 FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
                    (ticket_no, passenger_id),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM tickets WHERE ticket_no = ?",
                    (ticket_no,),
                )
            if cursor.fetchone() is None:
                conn.close()
                return {
                    "success": False,
                    "message": f"Ticket {ticket_no} not found"
                    + (f" for passenger {passenger_id}" if passenger_id else ""),
                }

            cursor.execute(
                "DELETE FROM ticket_flights WHERE ticket_no = ?",
                (ticket_no,),
            )
            cursor.execute(
                "DELETE FROM tickets WHERE ticket_no = ?",
                (ticket_no,),
            )
            conn.commit()
            conn.close()
            return {
                "success": True,
                "message": f"Ticket {ticket_no} successfully cancelled.",
                "ticket_no": ticket_no,
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.cancel_flight_booking 失败: %s", exc)
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # Hotels
    # ------------------------------------------------------------------
    async def search_hotels(
        self,
        location: str = None,
        checkin: str = None,
        checkout: str = None,
        **kwargs,
    ) -> List[HotelInfo]:
        limit = int(kwargs.get("limit", 10))
        try:
            conn = self._connect()
            cursor = conn.cursor()
            sql = (
                "SELECT id, name, location, price_tier FROM hotels WHERE 1=1"
            )
            params: List[Any] = []
            if location:
                sql += " AND location LIKE ?"
                params.append(f"%{location}%")
            sql += " LIMIT ?"
            params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return [
                HotelInfo(
                    hotel_id=str(r[0]),
                    name=r[1] or "",
                    location=r[2] or "",
                    price_per_night=self._price_tier_to_value(r[3]),
                )
                for r in rows
            ]
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.search_hotels 失败: %s", exc)
            return []

    @staticmethod
    def _price_tier_to_value(tier: Optional[str]) -> float:
        mapping = {
            "Midscale": 80.0,
            "Upper Midscale": 120.0,
            "Upscale": 200.0,
            "Luxury": 400.0,
        }
        return mapping.get(tier or "", 100.0)

    async def book_hotel(
        self, hotel_id: str, guest_info: dict, **kwargs
    ) -> Dict[str, Any]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE hotels SET booked = 1 WHERE id = ?",
                (hotel_id,),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated > 0:
                return {
                    "success": True,
                    "message": f"Hotel {hotel_id} successfully booked.",
                    "hotel_id": hotel_id,
                    "guest_info": guest_info or {},
                }
            return {
                "success": False,
                "message": f"No hotel found with ID {hotel_id}.",
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.book_hotel 失败: %s", exc)
            return {"success": False, "message": str(exc)}

    async def cancel_hotel_booking(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE hotels SET booked = 0 WHERE id = ?",
                (booking_id,),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated > 0:
                return {
                    "success": True,
                    "message": f"Hotel {booking_id} successfully cancelled.",
                    "hotel_id": booking_id,
                }
            return {
                "success": False,
                "message": f"No hotel found with ID {booking_id}.",
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.cancel_hotel_booking 失败: %s", exc)
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # Car Rentals
    # ------------------------------------------------------------------
    async def search_car_rentals(
        self,
        location: str = None,
        pickup_date: str = None,
        return_date: str = None,
        **kwargs,
    ) -> List[CarRentalInfo]:
        limit = int(kwargs.get("limit", 10))
        try:
            conn = self._connect()
            cursor = conn.cursor()
            sql = (
                "SELECT id, name, location, price_tier FROM car_rentals WHERE 1=1"
            )
            params: List[Any] = []
            if location:
                sql += " AND location LIKE ?"
                params.append(f"%{location}%")
            sql += " LIMIT ?"
            params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return [
                CarRentalInfo(
                    rental_id=str(r[0]),
                    car_type=r[1] or "",
                    company=r[1] or "",
                    price_per_day=self._price_tier_to_value(r[3]),
                    location=r[2] or "",
                )
                for r in rows
            ]
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.search_car_rentals 失败: %s", exc)
            return []

    async def book_car_rental(
        self, rental_id: str, driver_info: dict, **kwargs
    ) -> Dict[str, Any]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE car_rentals SET booked = 1 WHERE id = ?",
                (rental_id,),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated > 0:
                return {
                    "success": True,
                    "message": f"Car rental {rental_id} successfully booked.",
                    "rental_id": rental_id,
                    "driver_info": driver_info or {},
                }
            return {
                "success": False,
                "message": f"No car rental found with ID {rental_id}.",
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.book_car_rental 失败: %s", exc)
            return {"success": False, "message": str(exc)}

    async def cancel_car_rental(
        self, booking_id: str, **kwargs
    ) -> Dict[str, Any]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE car_rentals SET booked = 0 WHERE id = ?",
                (booking_id,),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated > 0:
                return {
                    "success": True,
                    "message": f"Car rental {booking_id} successfully cancelled.",
                    "rental_id": booking_id,
                }
            return {
                "success": False,
                "message": f"No car rental found with ID {booking_id}.",
            }
        except Exception as exc:
            logger.exception("SQLiteGDSAdapter.cancel_car_rental 失败: %s", exc)
            return {"success": False, "message": str(exc)}
