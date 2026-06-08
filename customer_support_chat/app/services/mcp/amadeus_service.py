# customer_support_chat/app/services/mcp/amadeus_service.py
"""Amadeus GDS Mock MCP 服务实现。

返回结构尽量贴近真实 Amadeus Self-Service API 响应，但所有数据均为本地
生成的 Mock，便于在没有真实账号 / API Key 的情况下进行开发与演示。
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .mcp_client import (
    MCPServiceBase,
    MCPToolDefinition,
    MCPToolResult,
)

logger = logging.getLogger(__name__)


_AIRLINES = [
    {"code": "CA", "name": "Air China"},
    {"code": "MU", "name": "China Eastern"},
    {"code": "CZ", "name": "China Southern"},
    {"code": "HU", "name": "Hainan Airlines"},
    {"code": "CX", "name": "Cathay Pacific"},
    {"code": "SQ", "name": "Singapore Airlines"},
    {"code": "EK", "name": "Emirates"},
    {"code": "LH", "name": "Lufthansa"},
    {"code": "AA", "name": "American Airlines"},
    {"code": "BA", "name": "British Airways"},
]

_CABIN_CLASSES = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]
_FLIGHT_STATUSES = ["SCHEDULED", "ON_TIME", "DELAYED", "BOARDING", "DEPARTED", "ARRIVED", "CANCELLED"]


def _seeded_random(*keys: Any) -> random.Random:
    """根据输入 key 生成稳定的伪随机源，保证同样输入返回一致 mock。"""
    h = hashlib.md5("|".join(str(k) for k in keys).encode("utf-8")).hexdigest()
    return random.Random(int(h[:8], 16))


class AmadeusMockService(MCPServiceBase):
    """模拟 Amadeus GDS 的 MCP 服务。

    暴露工具:
    - search_flights: 航班搜索
    - get_flight_status: 航班状态查询
    - book_flight: 航班预订 (Mock)
    """

    def __init__(self, name: str = "amadeus", config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config=config)
        self.service_name = name
        self.timeout: float = float((config or {}).get("timeout", 15))
        self.mode: str = (config or {}).get("mode", "mock")

    async def connect(self) -> None:
        # Mock 服务无外部资源
        self._connected = True
        logger.info("AmadeusMockService 已连接 (mode=%s)", self.mode)

    async def disconnect(self) -> None:
        self._connected = False

    async def list_tools(self) -> List[MCPToolDefinition]:
        return [
            MCPToolDefinition(
                name="search_flights",
                description=(
                    "搜索两地之间在指定日期的航班 (Amadeus Mock)。"
                    "返回 flight_number / departure / arrival / price 等结构化字段。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "出发机场 IATA 代码，例如 PEK / PVG / JFK",
                        },
                        "destination": {
                            "type": "string",
                            "description": "到达机场 IATA 代码",
                        },
                        "departure_date": {
                            "type": "string",
                            "description": "出发日期，格式 YYYY-MM-DD",
                        },
                        "adults": {
                            "type": "integer",
                            "description": "成人乘客数，默认 1",
                        },
                        "cabin_class": {
                            "type": "string",
                            "description": "舱位等级",
                            "enum": _CABIN_CLASSES,
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数，默认 5",
                        },
                    },
                    "required": ["origin", "destination", "departure_date"],
                },
                service_name=self.service_name,
            ),
            MCPToolDefinition(
                name="get_flight_status",
                description="查询单个航班的实时状态 (Amadeus Mock)。",
                parameters={
                    "type": "object",
                    "properties": {
                        "flight_number": {
                            "type": "string",
                            "description": "航班号，例如 'CA123'",
                        },
                        "date": {
                            "type": "string",
                            "description": "航班日期 YYYY-MM-DD，默认今日",
                        },
                    },
                    "required": ["flight_number"],
                },
                service_name=self.service_name,
            ),
            MCPToolDefinition(
                name="book_flight",
                description=(
                    "为指定乘客预订航班 (Amadeus Mock)，返回订单号、票价、状态等。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "flight_number": {"type": "string"},
                        "departure_date": {
                            "type": "string",
                            "description": "出发日期 YYYY-MM-DD",
                        },
                        "passenger_name": {"type": "string"},
                        "cabin_class": {
                            "type": "string",
                            "enum": _CABIN_CLASSES,
                        },
                    },
                    "required": [
                        "flight_number",
                        "departure_date",
                        "passenger_name",
                    ],
                },
                service_name=self.service_name,
            ),
        ]

    async def invoke_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        if tool_name == "search_flights":
            return self._search_flights(arguments)
        if tool_name == "get_flight_status":
            return self._get_flight_status(arguments)
        if tool_name == "book_flight":
            return self._book_flight(arguments)
        return MCPToolResult(success=False, error=f"未知工具: {tool_name}")

    # ------------------------------------------------------------------
    # Mock 实现
    # ------------------------------------------------------------------
    def _search_flights(self, args: Dict[str, Any]) -> MCPToolResult:
        origin = (args.get("origin") or "").upper().strip()
        destination = (args.get("destination") or "").upper().strip()
        departure_date = (args.get("departure_date") or "").strip()
        if not (origin and destination and departure_date):
            return MCPToolResult(
                success=False,
                error="缺少必要参数 origin / destination / departure_date",
            )
        try:
            base_dt = datetime.strptime(departure_date, "%Y-%m-%d")
        except ValueError:
            return MCPToolResult(
                success=False,
                error=f"departure_date 格式错误，需为 YYYY-MM-DD: {departure_date}",
            )
        adults = max(1, int(args.get("adults") or 1))
        cabin_class = (args.get("cabin_class") or "ECONOMY").upper()
        if cabin_class not in _CABIN_CLASSES:
            cabin_class = "ECONOMY"
        max_results = max(1, min(int(args.get("max_results") or 5), 10))

        rng = _seeded_random(origin, destination, departure_date, cabin_class)
        flights: List[Dict[str, Any]] = []
        for i in range(max_results):
            airline = rng.choice(_AIRLINES)
            number = rng.randint(100, 9999)
            dep_hour = rng.randint(6, 22)
            dep_min = rng.choice([0, 15, 30, 45])
            duration_min = rng.randint(90, 720)
            dep_time = base_dt.replace(hour=dep_hour, minute=dep_min)
            arr_time = dep_time + timedelta(minutes=duration_min)
            base_price = {
                "ECONOMY": 600,
                "PREMIUM_ECONOMY": 1100,
                "BUSINESS": 2400,
                "FIRST": 4800,
            }[cabin_class]
            price = round(base_price + rng.uniform(-150, 350), 2) * adults
            flights.append(
                {
                    "flight_number": f"{airline['code']}{number}",
                    "airline": airline["name"],
                    "airline_code": airline["code"],
                    "departure_airport": origin,
                    "arrival_airport": destination,
                    "departure_time": dep_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "arrival_time": arr_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "duration_minutes": duration_min,
                    "price": round(price, 2),
                    "currency": "USD",
                    "cabin_class": cabin_class,
                    "status": "SCHEDULED",
                    "stops": 0 if duration_min < 360 else rng.randint(0, 1),
                    "available_seats": rng.randint(1, 30),
                }
            )

        flights.sort(key=lambda f: f["price"])
        return MCPToolResult(
            success=True,
            data={
                "meta": {
                    "count": len(flights),
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "adults": adults,
                    "cabin_class": cabin_class,
                    "source": "amadeus_mock",
                },
                "flights": flights,
            },
        )

    def _get_flight_status(self, args: Dict[str, Any]) -> MCPToolResult:
        flight_number = (args.get("flight_number") or "").upper().strip()
        if not flight_number:
            return MCPToolResult(
                success=False, error="参数 flight_number 不能为空"
            )
        date = (args.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
        try:
            base_dt = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return MCPToolResult(
                success=False,
                error=f"date 格式错误，需为 YYYY-MM-DD: {date}",
            )
        rng = _seeded_random(flight_number, date)
        airline_code = "".join(c for c in flight_number if c.isalpha())[:2] or "CA"
        airline_name = next(
            (a["name"] for a in _AIRLINES if a["code"] == airline_code),
            "Unknown Airline",
        )
        dep_time = base_dt.replace(
            hour=rng.randint(5, 22), minute=rng.choice([0, 15, 30, 45])
        )
        duration = timedelta(minutes=rng.randint(90, 600))
        status = rng.choice(_FLIGHT_STATUSES)
        delay_minutes = rng.choice([0, 0, 0, 15, 30, 60]) if status == "DELAYED" else 0
        return MCPToolResult(
            success=True,
            data={
                "flight_number": flight_number,
                "airline": airline_name,
                "airline_code": airline_code,
                "date": date,
                "scheduled_departure": dep_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "estimated_departure": (
                    dep_time + timedelta(minutes=delay_minutes)
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "scheduled_arrival": (dep_time + duration).strftime(
                    "%Y-%m-%dT%H:%M:%S"
                ),
                "departure_airport": rng.choice(["PEK", "PVG", "CAN", "HKG"]),
                "arrival_airport": rng.choice(["JFK", "LAX", "LHR", "NRT"]),
                "status": status,
                "delay_minutes": delay_minutes,
                "gate": f"{rng.choice(['A', 'B', 'C', 'D'])}{rng.randint(1, 30)}",
                "terminal": str(rng.randint(1, 4)),
                "source": "amadeus_mock",
            },
        )

    def _book_flight(self, args: Dict[str, Any]) -> MCPToolResult:
        flight_number = (args.get("flight_number") or "").upper().strip()
        departure_date = (args.get("departure_date") or "").strip()
        passenger_name = (args.get("passenger_name") or "").strip()
        cabin_class = (args.get("cabin_class") or "ECONOMY").upper()
        if not (flight_number and departure_date and passenger_name):
            return MCPToolResult(
                success=False,
                error="缺少必要参数 flight_number / departure_date / passenger_name",
            )
        if cabin_class not in _CABIN_CLASSES:
            cabin_class = "ECONOMY"
        rng = _seeded_random(
            flight_number, departure_date, passenger_name, cabin_class
        )
        airline_code = "".join(c for c in flight_number if c.isalpha())[:2] or "CA"
        airline_name = next(
            (a["name"] for a in _AIRLINES if a["code"] == airline_code),
            "Unknown Airline",
        )
        base_price = {
            "ECONOMY": 650,
            "PREMIUM_ECONOMY": 1200,
            "BUSINESS": 2600,
            "FIRST": 5000,
        }[cabin_class]
        price = round(base_price + rng.uniform(-100, 300), 2)
        booking_id = f"AMA-{rng.randint(100000, 999999)}"
        ticket_number = f"{airline_code}-{rng.randint(10**9, 10**10 - 1)}"
        return MCPToolResult(
            success=True,
            data={
                "booking_id": booking_id,
                "ticket_number": ticket_number,
                "passenger_name": passenger_name,
                "flight_number": flight_number,
                "airline": airline_name,
                "departure_date": departure_date,
                "cabin_class": cabin_class,
                "price": price,
                "currency": "USD",
                "status": "CONFIRMED",
                "issued_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "source": "amadeus_mock",
            },
        )
