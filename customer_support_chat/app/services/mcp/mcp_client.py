# customer_support_chat/app/services/mcp/mcp_client.py
"""MCP 协议核心数据结构与基础 HTTP 客户端。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - graceful degradation
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class MCPToolDefinition:
    """单个 MCP 工具的元数据描述。"""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    service_name: str = ""


@dataclass
class MCPToolResult:
    """MCP 工具调用统一结果包装。"""

    success: bool
    data: Any = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------
class MCPServiceBase(ABC):
    """所有 MCP 外部服务必须实现的抽象接口。"""

    service_name: str = "base"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config or {}
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """初始化资源 (HTTP client / 鉴权等)。"""

    @abstractmethod
    async def disconnect(self) -> None:
        """释放资源。"""

    @abstractmethod
    async def list_tools(self) -> List[MCPToolDefinition]:
        """返回该服务暴露的所有 MCP 工具。"""

    @abstractmethod
    async def invoke_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """根据工具名调用并返回结构化结果。"""


# ---------------------------------------------------------------------------
# 通用 HTTP 客户端
# ---------------------------------------------------------------------------
class MCPHTTPClient:
    """基于 httpx.AsyncClient 的轻量 HTTP 通信客户端。

    支持 graceful degradation: 当 httpx 未安装时，所有请求均返回失败结果，
    避免影响整个应用的启动。
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self.headers = headers or {}
        self._client: Optional[Any] = None

    async def connect(self) -> None:
        if httpx is None:
            logger.warning("httpx 未安装, MCPHTTPClient 将不可用")
            return
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
            )

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:  # pragma: no cover
                logger.warning("关闭 httpx client 失败: %s", exc)
            finally:
                self._client = None

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> MCPToolResult:
        """统一请求入口，所有异常被捕获并包装为 MCPToolResult。"""
        if httpx is None:
            return MCPToolResult(
                success=False,
                error="httpx 未安装，无法发起 HTTP 请求",
            )
        if self._client is None:
            await self.connect()
        assert self._client is not None
        try:
            response = await self._client.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_body,
                headers=headers,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return MCPToolResult(success=True, data=response.json())
            return MCPToolResult(success=True, data=response.text)
        except httpx.TimeoutException as exc:
            logger.warning("HTTP 请求超时 %s %s: %s", method, url, exc)
            return MCPToolResult(success=False, error=f"请求超时: {exc}")
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "HTTP 错误 %s %s -> %s",
                method,
                url,
                exc.response.status_code if exc.response else "?",
            )
            body = ""
            if exc.response is not None:
                try:
                    body = exc.response.text
                except Exception:
                    body = ""
            return MCPToolResult(
                success=False,
                error=f"HTTP {exc.response.status_code if exc.response else '?'}: {body}",
            )
        except httpx.HTTPError as exc:
            logger.warning("HTTP 通信异常 %s %s: %s", method, url, exc)
            return MCPToolResult(success=False, error=f"HTTP 错误: {exc}")
        except Exception as exc:  # pragma: no cover - 兜底
            logger.exception("MCPHTTPClient 未知错误")
            return MCPToolResult(success=False, error=str(exc))

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> MCPToolResult:
        return await self.request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> MCPToolResult:
        return await self.request("POST", url, json_body=json_body, headers=headers)
