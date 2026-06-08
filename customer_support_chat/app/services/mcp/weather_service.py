# customer_support_chat/app/services/mcp/weather_service.py
"""OpenWeatherMap MCP 服务实现 (真实 API)。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .mcp_client import (
    MCPHTTPClient,
    MCPServiceBase,
    MCPToolDefinition,
    MCPToolResult,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openweathermap.org/data/2.5"


class OpenWeatherMapService(MCPServiceBase):
    """通过 HTTP 调用 OpenWeatherMap 的 MCP 服务。

    暴露工具:
    - get_current_weather(city, units?): 当前天气
    - get_weather_forecast(city, days?, units?): 5 天 / 3 小时 预报
    """

    def __init__(self, name: str = "openweathermap", config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config=config)
        self.service_name = name
        cfg = self.config
        self.base_url: str = cfg.get("base_url") or DEFAULT_BASE_URL
        # 优先使用配置中的 api_key，其次环境变量
        self.api_key: str = cfg.get("api_key") or os.environ.get(
            "OPENWEATHERMAP_API_KEY", ""
        )
        self.timeout: float = float(cfg.get("timeout", 10))
        self._http: MCPHTTPClient = MCPHTTPClient(
            base_url=self.base_url, timeout=self.timeout
        )

    async def connect(self) -> None:
        await self._http.connect()
        if not self.api_key:
            logger.warning(
                "OpenWeatherMapService 未配置 API Key (OPENWEATHERMAP_API_KEY)，"
                "实际调用将返回错误结果，但服务可正常注册。"
            )
        self._connected = True

    async def disconnect(self) -> None:
        await self._http.disconnect()
        self._connected = False

    async def list_tools(self) -> List[MCPToolDefinition]:
        return [
            MCPToolDefinition(
                name="get_current_weather",
                description=(
                    "查询指定城市的当前天气 (温度、湿度、天气状况等)，"
                    "通过 OpenWeatherMap API 返回真实数据。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称，例如 'Beijing'、'Shanghai'、'New York'",
                        },
                        "units": {
                            "type": "string",
                            "description": "单位制: metric (摄氏) / imperial (华氏)，默认 metric",
                            "enum": ["metric", "imperial", "standard"],
                        },
                    },
                    "required": ["city"],
                },
                service_name=self.service_name,
            ),
            MCPToolDefinition(
                name="get_weather_forecast",
                description=(
                    "查询指定城市未来若干天的天气预报 (基于 OpenWeatherMap "
                    "5 天 / 3 小时预报接口)。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称",
                        },
                        "days": {
                            "type": "integer",
                            "description": "预报天数 (1-5)，默认 3",
                        },
                        "units": {
                            "type": "string",
                            "description": "单位制: metric / imperial / standard",
                            "enum": ["metric", "imperial", "standard"],
                        },
                    },
                    "required": ["city"],
                },
                service_name=self.service_name,
            ),
        ]

    async def invoke_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        if not self.api_key:
            return MCPToolResult(
                success=False,
                error="OpenWeatherMap API Key 未配置 (请设置 OPENWEATHERMAP_API_KEY)",
            )
        if tool_name == "get_current_weather":
            return await self._get_current_weather(arguments)
        if tool_name == "get_weather_forecast":
            return await self._get_weather_forecast(arguments)
        return MCPToolResult(
            success=False, error=f"未知工具: {tool_name}"
        )

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------
    async def _get_current_weather(
        self, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        city = (arguments.get("city") or "").strip()
        if not city:
            return MCPToolResult(success=False, error="参数 city 不能为空")
        units = arguments.get("units") or "metric"
        params = {"q": city, "appid": self.api_key, "units": units}
        result = await self._http.get("/weather", params=params)
        if not result.success:
            return result
        data = result.data or {}
        normalized = {
            "city": data.get("name"),
            "country": (data.get("sys") or {}).get("country"),
            "temperature": (data.get("main") or {}).get("temp"),
            "feels_like": (data.get("main") or {}).get("feels_like"),
            "temp_min": (data.get("main") or {}).get("temp_min"),
            "temp_max": (data.get("main") or {}).get("temp_max"),
            "humidity": (data.get("main") or {}).get("humidity"),
            "pressure": (data.get("main") or {}).get("pressure"),
            "weather": [
                {"main": w.get("main"), "description": w.get("description")}
                for w in (data.get("weather") or [])
            ],
            "wind": data.get("wind") or {},
            "clouds": (data.get("clouds") or {}).get("all"),
            "visibility": data.get("visibility"),
            "units": units,
            "source": "openweathermap",
            "raw": data,
        }
        return MCPToolResult(success=True, data=normalized)

    async def _get_weather_forecast(
        self, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        city = (arguments.get("city") or "").strip()
        if not city:
            return MCPToolResult(success=False, error="参数 city 不能为空")
        days = int(arguments.get("days") or 3)
        days = max(1, min(days, 5))
        units = arguments.get("units") or "metric"
        # OpenWeatherMap 5 天预报: 每 3 小时一个数据点 -> 8 * days
        params = {
            "q": city,
            "appid": self.api_key,
            "units": units,
            "cnt": 8 * days,
        }
        result = await self._http.get("/forecast", params=params)
        if not result.success:
            return result
        data = result.data or {}
        items = data.get("list") or []
        simplified = [
            {
                "dt_txt": it.get("dt_txt"),
                "temperature": (it.get("main") or {}).get("temp"),
                "humidity": (it.get("main") or {}).get("humidity"),
                "weather": [
                    {"main": w.get("main"), "description": w.get("description")}
                    for w in (it.get("weather") or [])
                ],
                "wind": it.get("wind") or {},
            }
            for it in items
        ]
        normalized = {
            "city": (data.get("city") or {}).get("name"),
            "country": (data.get("city") or {}).get("country"),
            "days": days,
            "units": units,
            "forecast": simplified,
            "source": "openweathermap",
        }
        return MCPToolResult(success=True, data=normalized)
