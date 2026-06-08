# customer_support_chat/app/services/mcp/tool_wrapper.py
"""将 MCP 工具适配为 LangChain Tool，使 Agent 层零感知。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple, Type

try:
    from langchain_core.tools import StructuredTool
except ImportError:  # pragma: no cover
    StructuredTool = None  # type: ignore

try:
    from pydantic import BaseModel, Field, create_model
except ImportError:  # pragma: no cover
    BaseModel = object  # type: ignore
    Field = None  # type: ignore
    create_model = None  # type: ignore

from .mcp_client import MCPToolDefinition
from .service_registry import MCPServiceRegistry

logger = logging.getLogger(__name__)


_JSON_TYPE_MAP: Dict[str, Type[Any]] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _build_args_schema(tool_def: MCPToolDefinition) -> Optional[Type[BaseModel]]:
    """根据 MCPToolDefinition.parameters (JSON schema) 动态构建 Pydantic 模型。"""
    if create_model is None:
        return None
    schema = tool_def.parameters or {}
    properties: Dict[str, Any] = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not properties:
        return None

    fields: Dict[str, Tuple[Any, Any]] = {}
    for prop_name, prop_schema in properties.items():
        json_type = (prop_schema or {}).get("type", "string")
        py_type = _JSON_TYPE_MAP.get(json_type, str)
        description = (prop_schema or {}).get("description", "")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(..., description=description))
        else:
            fields[prop_name] = (
                Optional[py_type],
                Field(default=None, description=description),
            )

    model_name = f"{tool_def.name.title().replace('_', '')}Args"
    try:
        return create_model(model_name, **fields)  # type: ignore[arg-type]
    except Exception as exc:
        logger.warning("构建 args_schema 失败 %s: %s", tool_def.name, exc)
        return None


def create_langchain_tool_from_mcp(
    tool_def: MCPToolDefinition,
    registry: MCPServiceRegistry,
) -> Any:
    """将 MCP 工具转换为 LangChain StructuredTool。

    Agent 层只需将返回的 Tool 加入 ``llm.bind_tools([...])``，调用过程会
    透明地路由到 ``MCPServiceRegistry`` 对应的远程服务。
    """
    if StructuredTool is None:
        raise RuntimeError(
            "未安装 langchain_core，无法创建 LangChain Tool。"
        )

    args_schema = _build_args_schema(tool_def)

    async def _async_tool_func(**kwargs: Any) -> str:
        # 移除值为 None 的可选参数，避免误传
        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        result = await registry.invoke_tool(tool_def.name, cleaned)
        if result.success:
            try:
                return json.dumps(result.data, ensure_ascii=False, default=str)
            except Exception:
                return str(result.data)
        return f"Error: {result.error}"

    def _sync_tool_func(**kwargs: Any) -> str:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已运行的事件循环中创建一个新的子循环
                return asyncio.run_coroutine_threadsafe(
                    _async_tool_func(**kwargs), loop
                ).result()
            return loop.run_until_complete(_async_tool_func(**kwargs))
        except RuntimeError:
            return asyncio.run(_async_tool_func(**kwargs))

    kwargs: Dict[str, Any] = {
        "name": tool_def.name,
        "description": tool_def.description,
        "coroutine": _async_tool_func,
        "func": _sync_tool_func,
    }
    if args_schema is not None:
        kwargs["args_schema"] = args_schema

    return StructuredTool.from_function(**kwargs)
