# customer_support_chat/app/services/assistants/weather_search_assistant.py

import logging
from datetime import datetime
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from customer_support_chat.app.services.tools.weather import search_weather_posts
from customer_support_chat.app.services.assistants.assistant_base import (
    Assistant,
    llm,
    CompleteOrEscalate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 通过 MCP 注册表加载天气工具 (graceful degradation)
# ---------------------------------------------------------------------------
def _load_mcp_weather_tools() -> list:
    """尝试通过 MCP 注册表加载 OpenWeatherMap 工具。

    任何异常 (缺少 httpx / yaml / 配置文件 / API Key 未设置等) 都将被吞掉，
    并返回空列表，由 Agent 自动 fallback 到 ``search_weather_posts``。
    """
    try:
        from customer_support_chat.app.services.mcp import (
            MCPServiceRegistry,
            create_langchain_tool_from_mcp,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("MCP 模块导入失败，Weather Assistant 将仅使用 fallback 工具: %s", exc)
        return []

    config_path = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "mcp_services.yaml"
    )

    try:
        registry = MCPServiceRegistry()
        registry.load_config(str(config_path))
    except Exception as exc:
        logger.warning("加载 MCP 配置失败: %s", exc)
        return []

    tools = []
    for tool_name in ("get_current_weather", "get_weather_forecast"):
        tool_def = registry.get_tool(tool_name)
        if tool_def is None:
            continue
        try:
            tools.append(create_langchain_tool_from_mcp(tool_def, registry))
        except Exception as exc:
            logger.warning("包装 MCP 工具 %s 失败: %s", tool_name, exc)
    return tools


_mcp_weather_tools = _load_mcp_weather_tools()


# weather search assistant prompt
weather_search_assistant_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a specialized assistant for weather search. "
        "You have access to MCP-powered tools that call the real OpenWeatherMap API: "
        "use `get_current_weather` for current conditions and `get_weather_forecast` "
        "for multi-day forecasts whenever possible. "
        "If the MCP tools are unavailable or return an error (e.g. missing API key), "
        "fall back to the legacy `search_weather_posts` tool. "
        "Present the weather information in a clear and readable format, showing "
        "location, current conditions, temperature, and forecast if available. "
        "If the user's request is not related to weather search, "
        "use the CompleteOrEscalate tool to return control to the main assistant. "
        "Current time: {time}.",
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now())


# Weather search assistant tools: MCP tools first, legacy tool as fallback
weather_search_assistant_tools = [
    *_mcp_weather_tools,
    search_weather_posts,
    CompleteOrEscalate,
]

# Create the weather search assistant runnable
weather_search_assistant_runnable = (
    weather_search_assistant_prompt | llm.bind_tools(weather_search_assistant_tools)
)

# Instantiate the weather search assistant
weather_search_assistant = Assistant(weather_search_assistant_runnable)
