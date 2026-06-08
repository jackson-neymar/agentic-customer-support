"""安全审计日志记录器 - 记录护栏拦截事件和安全相关操作"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """专用安全审计日志记录器

    记录格式为结构化 JSON，每行一条记录。
    支持越狱检测、相关性过滤、恶意请求拦截等事件。
    """

    def __init__(self, log_dir: str = "audit_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_file_handler()

    def _setup_file_handler(self):
        """设置文件日志处理器"""
        self.audit_logger = logging.getLogger("security_audit")
        self.audit_logger.setLevel(logging.INFO)

        # 避免重复添加 handler
        if not self.audit_logger.handlers:
            file_handler = logging.FileHandler(
                self.log_dir / "security_audit.jsonl",
                encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self.audit_logger.addHandler(file_handler)

    def _write_event(self, event: dict):
        """写入一条审计事件"""
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.audit_logger.info(json.dumps(event, ensure_ascii=False))

    def log_jailbreak_attempt(self, session_id: str, message: str, reason: str):
        """记录越狱尝试"""
        self._write_event({
            "event_type": "jailbreak_attempt",
            "session_id": session_id,
            "user_message": message[:500],  # 截断过长消息
            "action": "blocked",
            "reason": reason,
        })
        logger.warning(f"Jailbreak attempt blocked for session {session_id}: {reason}")

    def log_irrelevant_message(self, session_id: str, message: str, reason: str):
        """记录无关消息过滤"""
        self._write_event({
            "event_type": "irrelevant_message",
            "session_id": session_id,
            "user_message": message[:500],
            "action": "filtered",
            "reason": reason,
        })
        logger.info(f"Irrelevant message filtered for session {session_id}: {reason}")

    def log_guardrail_pass(self, session_id: str, check_duration_ms: float):
        """记录通过护栏检查（采样 10% 记录）"""
        import random
        if random.random() < 0.1:  # 10% 采样
            self._write_event({
                "event_type": "guardrail_pass",
                "session_id": session_id,
                "action": "passed",
                "duration_ms": round(check_duration_ms, 2),
            })


# 全局单例
audit_logger = AuditLogger()
