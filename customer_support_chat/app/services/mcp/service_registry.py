# customer_support_chat/app/services/mcp/service_registry.py
"""MCP 服务注册表，支持配置驱动的动态热插拔。"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .mcp_client import (
    MCPServiceBase,
    MCPToolDefinition,
    MCPToolResult,
)

logger = logging.getLogger(__name__)

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env_vars(value: Any) -> Any:
    """递归展开 ${VAR} 形式的环境变量占位。"""
    if isinstance(value, str):
        def _sub(match: "re.Match[str]") -> str:
            return os.environ.get(match.group(1), "")

        return _ENV_VAR_PATTERN.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


class MCPServiceRegistry:
    """单例注册表，集中管理所有 MCP 外部服务及其工具。"""

    _instance: Optional["MCPServiceRegistry"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "MCPServiceRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._services: Dict[str, MCPServiceBase] = {}
        # tool_name -> MCPToolDefinition
        self._tools: Dict[str, MCPToolDefinition] = {}
        # 上一次加载的服务配置: name -> service_config_dict
        self._last_config: Dict[str, Dict[str, Any]] = {}
        self._config_path: Optional[Path] = None
        self._initialized = True

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    def load_config(self, config_path: str) -> Dict[str, Dict[str, Any]]:
        """从 YAML 加载服务配置，并按照配置注册启用的服务。

        返回最终生效的服务配置字典 (name -> config)。
        """
        path = Path(config_path)
        self._config_path = path
        services_config = self._read_yaml_services(path)

        # 计算与上次的差异
        prev_names = set(self._last_config.keys())
        curr_names = set(services_config.keys())

        # 卸载已被移除或被禁用的
        for name in prev_names - curr_names:
            self._run_async(self.unregister_service(name))
        for name in curr_names & prev_names:
            if not services_config[name].get("enabled", True):
                self._run_async(self.unregister_service(name))

        # 注册新增 / 重新启用的服务
        for name, cfg in services_config.items():
            if not cfg.get("enabled", True):
                continue
            if name in self._services and self._last_config.get(name) == cfg:
                continue  # 配置无变化
            service = self._build_service(name, cfg)
            if service is not None:
                self._run_async(self.register_service(service))

        self._last_config = services_config
        return services_config

    def reload_config(self) -> Dict[str, Dict[str, Any]]:
        """热重载: 基于 self._config_path 重新执行 load_config。"""
        if self._config_path is None:
            logger.warning("MCPServiceRegistry.reload_config 在未加载配置前调用")
            return {}
        return self.load_config(str(self._config_path))

    @staticmethod
    def _read_yaml_services(path: Path) -> Dict[str, Dict[str, Any]]:
        if not path.exists():
            logger.warning("MCP 配置文件不存在: %s", path)
            return {}
        try:
            import yaml  # 延迟导入，避免影响应用启动
        except ImportError:
            logger.warning("未安装 PyYAML，无法加载 MCP 配置")
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error("解析 MCP 配置失败: %s", exc)
            return {}

        services = raw.get("mcp_services", {}) or {}
        return {name: _expand_env_vars(cfg or {}) for name, cfg in services.items()}

    def _build_service(
        self, name: str, cfg: Dict[str, Any]
    ) -> Optional[MCPServiceBase]:
        """按 type 字段实例化具体的 MCPServiceBase 子类。"""
        service_type = (cfg.get("type") or name).lower()
        try:
            if service_type in ("openweathermap", "weather"):
                from .weather_service import OpenWeatherMapService

                return OpenWeatherMapService(name=name, config=cfg)
            if service_type in ("amadeus_mock", "amadeus"):
                from .amadeus_service import AmadeusMockService

                return AmadeusMockService(name=name, config=cfg)
        except Exception as exc:
            logger.exception("构建 MCP 服务 %s 失败: %s", name, exc)
            return None

        logger.warning("未知 MCP 服务类型: %s (name=%s)", service_type, name)
        return None

    # ------------------------------------------------------------------
    # 服务注册 / 卸载
    # ------------------------------------------------------------------
    async def register_service(self, service: MCPServiceBase) -> None:
        name = service.service_name
        # 已存在则先卸载，避免重复
        if name in self._services:
            await self.unregister_service(name)
        try:
            await service.connect()
        except Exception as exc:
            logger.warning("MCP 服务 %s connect() 失败: %s", name, exc)
        self._services[name] = service
        try:
            tools = await service.list_tools()
        except Exception as exc:
            logger.warning("MCP 服务 %s list_tools() 失败: %s", name, exc)
            tools = []
        for tool in tools:
            tool.service_name = name
            self._tools[tool.name] = tool
        logger.info(
            "MCP 服务已注册: name=%s, tools=%s",
            name,
            [t.name for t in tools],
        )

    async def unregister_service(self, service_name: str) -> None:
        service = self._services.pop(service_name, None)
        # 移除该服务对应的工具
        removed = [n for n, t in self._tools.items() if t.service_name == service_name]
        for n in removed:
            self._tools.pop(n, None)
        if service is not None:
            try:
                await service.disconnect()
            except Exception as exc:
                logger.warning("MCP 服务 %s disconnect() 失败: %s", service_name, exc)
            logger.info("MCP 服务已卸载: %s", service_name)

    # ------------------------------------------------------------------
    # 工具访问
    # ------------------------------------------------------------------
    def get_tool(self, tool_name: str) -> Optional[MCPToolDefinition]:
        return self._tools.get(tool_name)

    def list_all_tools(self) -> List[MCPToolDefinition]:
        return list(self._tools.values())

    def list_services(self) -> List[str]:
        return list(self._services.keys())

    async def invoke_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            return MCPToolResult(
                success=False, error=f"工具未注册: {tool_name}"
            )
        service = self._services.get(tool.service_name)
        if service is None:
            return MCPToolResult(
                success=False,
                error=f"工具 {tool_name} 对应的服务未连接: {tool.service_name}",
            )
        try:
            return await service.invoke_tool(tool_name, arguments or {})
        except Exception as exc:
            logger.exception("调用 MCP 工具 %s 失败", tool_name)
            return MCPToolResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # 内部 async 调度工具
    # ------------------------------------------------------------------
    @staticmethod
    def _run_async(coro: Any) -> Any:
        """在已有事件循环 / 同步上下文中安全执行协程。"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中: 创建一个 future 任务
                return asyncio.ensure_future(coro)
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
