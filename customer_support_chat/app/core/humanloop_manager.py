"""GoHumanLoop integration for sensitive tool approval.

This module centralizes HumanLoopManager/HumanloopAdapter creation so booking
and cancellation tools can require approval without importing graph.py and
creating circular imports.
"""

import os
from typing import List

from customer_support_chat.app.core.logger import logger

try:
    from gohumanloop import APIProvider, DefaultHumanLoopManager
    from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter
    from gohumanloop.providers.terminal_provider import TerminalProvider
    from gohumanloop.utils import get_secret_from_env
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise ImportError(
        "GoHumanLoop is required for HITL approvals but is not installed. "
        "Install project dependencies or run `pip install gohumanloop==0.0.9`."
    ) from exc


def _get_timeout() -> int:
    raw_timeout = os.environ.get("GOHUMANLOOP_TIMEOUT_SECONDS", "300")
    try:
        return int(raw_timeout)
    except ValueError:
        logger.warning(
            "Invalid GOHUMANLOOP_TIMEOUT_SECONDS=%r; falling back to 300 seconds",
            raw_timeout,
        )
        return 300


def _build_providers() -> List[object]:
    """Build configured GoHumanLoop providers.

    Defaults to TerminalProvider for local development. Set
    GOHUMANLOOP_PROVIDER=api (or provide both GOHUMANLOOP_API_KEY and
    GOHUMANLOOP_API_BASE_URL) to route approval requests to the API provider,
    e.g. a Feishu-backed approval service.
    """

    provider = os.environ.get("GOHUMANLOOP_PROVIDER", "terminal").strip().lower()
    api_key = os.environ.get("GOHUMANLOOP_API_KEY")
    api_base_url = os.environ.get("GOHUMANLOOP_API_BASE_URL")

    if provider == "api" or (api_key and api_base_url):
        if not api_key or not api_base_url:
            raise ValueError(
                "GOHUMANLOOP_PROVIDER=api requires both GOHUMANLOOP_API_KEY "
                "and GOHUMANLOOP_API_BASE_URL."
            )

        logger.info("🧑‍💼 GoHumanLoop APIProvider enabled for HITL approvals")
        return [
            APIProvider(
                name=os.environ.get("GOHUMANLOOP_PROVIDER_NAME", "ApiProvider"),
                api_base_url=api_base_url,
                api_key=get_secret_from_env("GOHUMANLOOP_API_KEY"),
                default_platform=os.environ.get("GOHUMANLOOP_PLATFORM", "feishu"),
                request_timeout=int(os.environ.get("GOHUMANLOOP_REQUEST_TIMEOUT", "30")),
                poll_interval=int(os.environ.get("GOHUMANLOOP_POLL_INTERVAL", "5")),
                max_retries=int(os.environ.get("GOHUMANLOOP_MAX_RETRIES", "3")),
            )
        ]

    logger.info("🧑‍💼 GoHumanLoop TerminalProvider enabled for HITL approvals")
    return [TerminalProvider(name=os.environ.get("GOHUMANLOOP_PROVIDER_NAME", "TerminalProvider"))]


humanloop_manager = DefaultHumanLoopManager(initial_providers=_build_providers())
humanloop_adapter = HumanloopAdapter(
    manager=humanloop_manager,
    default_timeout=_get_timeout(),
)
