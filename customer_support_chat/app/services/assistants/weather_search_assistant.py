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
        "你是专门处理天气查询的助手。"
        "你可以使用基于 MCP 的工具来调用真实的 OpenWeatherMap API："
        "只要可用，查询当前天气时使用 `get_current_weather`，"
        "查询多日天气预报时使用 `get_weather_forecast`。"
        "如果 MCP 工具不可用或返回错误（例如缺少 API key），"
        "请降级使用旧的 `search_weather_posts` 工具。"
        "请用清晰易读的格式展示天气信息，包括地点、当前天气、温度，"
        "以及可用的天气预报。"
        "如果用户请求与天气查询无关，"
        "请使用 CompleteOrEscalate 工具将控制权交还给主助手。"
        "当前时间：{time}.",
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
