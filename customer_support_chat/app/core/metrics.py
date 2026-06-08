"""
Performance Metrics Collection Module
实时收集系统性能指标，支持Prometheus导出
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import logging
from functools import wraps
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# ============ 核心指标定义 ============

# 1. 请求总数
request_counter = Counter(
    'chatbot_requests_total',
    'Total number of chat requests',
    ['endpoint', 'status']  # 标签：端点名称、状态（success/error）
)

# 2. 响应时间分布
response_time = Histogram(
    'chatbot_response_seconds',
    'Response time distribution in seconds',
    ['endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]  # 时间桶
)

# 3. 活跃会话数
active_sessions = Gauge(
    'chatbot_active_sessions',
    'Number of currently active chat sessions'
)

# 4. 人工审批请求数
approval_requests = Counter(
    'chatbot_approval_requests_total',
    'Total HITL approval requests',
    ['decision']  # approved/rejected/pending
)

# 5. 工具调用统计
tool_calls = Counter(
    'chatbot_tool_calls_total',
    'Total tool invocations',
    ['tool_name', 'status']
)

# 6. Token使用量（估算）
estimated_tokens = Counter(
    'chatbot_tokens_total',
    'Estimated token usage',
    ['type']  # input/output
)

# 7. 错误统计
error_counter = Counter(
    'chatbot_errors_total',
    'Total number of errors',
    ['error_type', 'endpoint']
)

# 8. 会话时长
session_duration = Histogram(
    'chatbot_session_duration_seconds',
    'User session duration',
    buckets=[60, 300, 600, 1800, 3600]  # 1分钟到1小时
)


# ============ 实时统计类 ============

class MetricsCollector:
    """
    实时指标收集器（单例模式）
    ✅ 支持异步操作
    ✅ 线程安全
    ✅ 排除监控端点
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化指标收集器"""
        if not self._initialized:
            self.metrics = {
                "total_requests": 0,
                "active_sessions": 0,
                "error_count": 0,
                "response_times": [],
                "requests_by_endpoint": {},
                "request_timeline": [],
                "session_start_times": {},  # 会话开始时间
            }
            self.lock = asyncio.Lock()
            self._initialized = True
            logger.info("✅ MetricsCollector initialized")
    
    async def record_request(self, endpoint: str, status: str, duration: float):
        """
        记录业务请求（排除监控端点）
        
        Args:
            endpoint: 请求路径
            status: 状态 (success/error)
            duration: 响应时间（秒）
        """
        async with self.lock:
            try:
                # 增加总请求数
                self.metrics["total_requests"] += 1
                
                # 更新Prometheus指标
                request_counter.labels(endpoint=endpoint, status=status).inc()
                response_time.labels(endpoint=endpoint).observe(duration)
                
                # 记录响应时间
                self.metrics["response_times"].append(duration)
                if len(self.metrics["response_times"]) > 100:
                    self.metrics["response_times"] = self.metrics["response_times"][-100:]
                
                # 记录错误
                if status == "error":
                    self.metrics["error_count"] += 1
                
                # 按端点统计
                if endpoint not in self.metrics["requests_by_endpoint"]:
                    self.metrics["requests_by_endpoint"][endpoint] = {
                        "count": 0,
                        "errors": 0,
                        "total_duration": 0,
                        "avg_duration": 0,
                    }
                
                endpoint_stats = self.metrics["requests_by_endpoint"][endpoint]
                endpoint_stats["count"] += 1
                endpoint_stats["total_duration"] += duration
                endpoint_stats["avg_duration"] = (
                    endpoint_stats["total_duration"] / endpoint_stats["count"]
                )
                
                if status == "error":
                    endpoint_stats["errors"] += 1
                
                # 记录时间线（保留最近50个）
                self.metrics["request_timeline"].append({
                    "timestamp": time.time(),
                    "endpoint": endpoint,
                    "status": status,
                    "duration": duration,
                })
                
                if len(self.metrics["request_timeline"]) > 50:
                    self.metrics["request_timeline"] = self.metrics["request_timeline"][-50:]
                
                logger.debug(f"📊 Recorded request: {endpoint} ({status}, {duration:.3f}s)")
                
            except Exception as e:
                logger.error(f"❌ Error recording request: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取统计数据（只读，不修改计数器）
        
        Returns:
            包含所有统计信息的字典
        """
        async with self.lock:
            try:
                return {
                    "total_requests": self.metrics["total_requests"],
                    "active_sessions": self.metrics["active_sessions"],
                    "error_count": self.metrics["error_count"],
                    "avg_response_time": (
                        sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
                        if self.metrics["response_times"]
                        else 0
                    ),
                    "requests_by_endpoint": dict(self.metrics["requests_by_endpoint"]),
                    "request_timeline": self.metrics["request_timeline"][-20:],
                }
            except Exception as e:
                logger.error(f"❌ Error getting stats: {e}")
                return {
                    "total_requests": 0,
                    "active_sessions": 0,
                    "error_count": 0,
                    "avg_response_time": 0,
                    "requests_by_endpoint": {},
                    "request_timeline": [],
                }
    
    async def increment_sessions(self):
        """增加活跃会话数"""
        async with self.lock:
            self.metrics["active_sessions"] += 1
            active_sessions.set(self.metrics["active_sessions"])
            logger.debug(f"📈 Active sessions: {self.metrics['active_sessions']}")
    
    async def decrement_sessions(self):
        """减少活跃会话数"""
        async with self.lock:
            if self.metrics["active_sessions"] > 0:
                self.metrics["active_sessions"] -= 1
            active_sessions.set(self.metrics["active_sessions"])
            logger.debug(f"📉 Active sessions: {self.metrics['active_sessions']}")
    
    def record_session(self, session_id: str, action: str = 'start'):
        """
        记录会话生命周期（同步方法，用于装饰器）
        
        Args:
            session_id: 会话ID
            action: 'start' 或 'end'
        """
        try:
            if action == 'start':
                self.metrics["session_start_times"][session_id] = time.time()
                logger.debug(f"🟢 Session started: {session_id}")
            elif action == 'end' and session_id in self.metrics["session_start_times"]:
                duration = time.time() - self.metrics["session_start_times"][session_id]
                session_duration.observe(duration)
                del self.metrics["session_start_times"][session_id]
                logger.debug(f"🔴 Session ended: {session_id} (duration: {duration:.1f}s)")
        except Exception as e:
            logger.error(f"❌ Error recording session: {e}")
    
    def record_approval(self, decision: str):
        """
        记录HITL审批决策（同步方法）
        
        Args:
            decision: 'approved', 'rejected', 或 'pending'
        """
        try:
            approval_requests.labels(decision=decision).inc()
            logger.debug(f"✅ Approval recorded: {decision}")
        except Exception as e:
            logger.error(f"❌ Error recording approval: {e}")
    
    def record_tool_call(self, tool_name: str, status: str = 'success'):
        """
        记录工具调用（同步方法）
        
        Args:
            tool_name: 工具名称
            status: 'success' 或 'error'
        """
        try:
            tool_calls.labels(tool_name=tool_name, status=status).inc()
            logger.debug(f"🔧 Tool call recorded: {tool_name} ({status})")
        except Exception as e:
            logger.error(f"❌ Error recording tool call: {e}")
    
    def estimate_tokens(self, text: str, token_type: str = 'input'):
        """
        估算Token使用量（同步方法）
        
        Args:
            text: 文本内容
            token_type: 'input' 或 'output'
        """
        try:
            # 粗略估算：1 token ≈ 4 字符
            token_count = len(text) // 4
            estimated_tokens.labels(type=token_type).inc(token_count)
            logger.debug(f"📊 Tokens estimated: {token_count} ({token_type})")
        except Exception as e:
            logger.error(f"❌ Error estimating tokens: {e}")
    
    def record_error(self, error_type: str, endpoint: str):
        """
        记录错误（同步方法）
        
        Args:
            error_type: 错误类型
            endpoint: 发生错误的端点
        """
        try:
            error_counter.labels(error_type=error_type, endpoint=endpoint).inc()
            logger.debug(f"❌ Error recorded: {error_type} at {endpoint}")
        except Exception as e:
            logger.error(f"❌ Error recording error: {e}")
    
    async def reset(self):
        """重置所有指标（仅用于测试）"""
        async with self.lock:
            self.metrics = {
                "total_requests": 0,
                "active_sessions": 0,
                "error_count": 0,
                "response_times": [],
                "requests_by_endpoint": {},
                "request_timeline": [],
                "session_start_times": {},
            }
            logger.warning("⚠️  Metrics reset!")


# ============ 装饰器：自动追踪性能 ============

def track_performance(endpoint_name: str):
    """
    装饰器：自动记录端点性能
    
    Args:
        endpoint_name: 端点名称（用于标识）
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                # 使用单例实例
                collector = MetricsCollector()
                collector.record_error(type(e).__name__, endpoint_name)
                raise
            finally:
                duration = time.time() - start_time
                # 注意：不在这里记录请求，由中间件统一处理
                logger.debug(f"⏱️  {endpoint_name} completed in {duration:.3f}s ({status})")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                # 使用单例实例
                collector = MetricsCollector()
                collector.record_error(type(e).__name__, endpoint_name)
                raise
            finally:
                duration = time.time() - start_time
                logger.debug(f"⏱️  {endpoint_name} completed in {duration:.3f}s ({status})")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# ============ 导出函数（方便使用）============

def get_metrics_collector() -> MetricsCollector:
    """获取全局MetricsCollector实例"""
    return MetricsCollector()


# ============ SSE 流式输出指标 ============

# SSE 流式输出指标
stream_first_byte_time = Histogram(
    'chatbot_stream_first_byte_seconds',
    'Time to first byte in streaming responses',
    ['endpoint'],
    buckets=[0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]
)


# ============ 护栏安全指标 ============
guardrail_blocks_total = Counter(
    'chatbot_guardrail_blocks_total',
    'Total number of messages blocked by guardrails',
    ['type']  # jailbreak, irrelevant
)

guardrail_check_duration = Histogram(
    'chatbot_guardrail_check_seconds',
    'Guardrail check duration in seconds',
    buckets=[0.1, 0.2, 0.3, 0.5, 1.0, 2.0]
)