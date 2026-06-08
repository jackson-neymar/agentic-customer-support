# customer_support_chat/app/services/mcp/__init__.py
"""
MCP (Model Context Protocol) 客户端框架。

提供:
- MCPToolDefinition / MCPToolResult: 工具协议数据结构
- MCPServiceBase: 外部服务抽象基类
- MCPHTTPClient: 基于 httpx.AsyncClient 的 HTTP 通信客户端
- MCPServiceRegistry: 单例注册表，支持配置驱动的动态热插拔
- create_langchain_tool_from_mcp: 将 MCP 工具适配为 LangChain StructuredTool

模块设计为可独立导入，缺失第三方依赖时不会影响整体应用启动。
"""

from .mcp_client import (
    MCPToolDefinition,
    MCPToolResult,
    MCPServiceBase,
    MCPHTTPClient,
)
from .service_registry import MCPServiceRegistry
from .tool_wrapper import create_langchain_tool_from_mcp

__all__ = [
    "MCPToolDefinition",
    "MCPToolResult",
    "MCPServiceBase",
    "MCPHTTPClient",
    "MCPServiceRegistry",
    "create_langchain_tool_from_mcp",
]
