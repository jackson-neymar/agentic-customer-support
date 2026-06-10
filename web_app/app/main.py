from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv
from pydantic import BaseModel
import uuid
import os
import sys
import psutil
import time
import json
import asyncio
from customer_support_chat.app.core.logger import logger

# Add the customer_support_chat directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from customer_support_chat.app.services.chat_service import process_user_message
from .core.user_data_manager import (
    get_user_session, 
    update_user_chat_history, 
    get_pending_action, 
    set_user_decision, 
    clear_pending_action, 
    clear_user_decision,
    get_operation_log
)

# 导入指标模块
from customer_support_chat.app.core.metrics import (
    get_metrics_collector,
    track_performance,
    generate_latest,
    CONTENT_TYPE_LATEST,
    stream_first_byte_time
)

# Load environment variables
load_dotenv()

# ✅ 创建全局MetricsCollector实例
metrics_collector = get_metrics_collector()

app = FastAPI(
    title="Customer Support RAG System",
    description="Multi-Agent RAG System for Customer Support with HITL",
    version="1.0.0"
)

# Mount static files directory
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


class ChatMessage(BaseModel):
    message: str


class ApprovalDecision(BaseModel):
    decision: str


def get_session_data(request: Request):
    """Get or create session data for the current user."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Get the user session data
    session_data = get_user_session(session_id)
    
    # Ensure config exists in session_data
    if "config" not in session_data:
        session_data["config"] = {
            "thread_id": session_id,
            "passenger_id": "5102 899977"  # Default passenger ID
        }
    
    return {
        "session_id": session_id,
        "config": session_data["config"],
        "user_data": session_data
    }


# ============ 中间件：请求追踪 ============

@app.middleware("http")
async def track_requests(request: Request, call_next):
    """
    追踪所有HTTP请求，排除监控端点
    ✅ 只记录业务请求
    ✅ 排除 /stats, /pending-action, /operation-log 等
    """
    
    path = request.url.path
    
    # 🚫 需要排除的路径（精确匹配）
    EXCLUDED_EXACT = {
        "/stats",
        "/pending-action",
        "/operation-log",
        "/metrics",
        "/health",
        "/openapi.json",
        "/favicon.ico",
    }
    
    # 🚫 需要排除的路径前缀
    EXCLUDED_PREFIXES = (
        "/docs",
        "/redoc",
        "/static",
    )
    
    # 判断是否需要跳过
    should_skip = (
        path in EXCLUDED_EXACT or 
        path.startswith(EXCLUDED_PREFIXES)
    )
    
    # 如果需要跳过，直接返回，不记录
    if should_skip:
        logger.debug(f"⏭️  SKIPPING: {path}")
        return await call_next(request)
    
    # ✅ 只有业务请求走到这里
    logger.info(f"✅ TRACKING: {path}")
    start_time = time.time()
    status = "success"
    
    try:
        # 处理请求
        response = await call_next(request)
        
        # 根据状态码判断成功/失败
        if response.status_code >= 400:
            status = "error"
        
        return response
        
    except Exception as e:
        status = "error"
        logger.error(f"❌ Request error on {path}: {e}")
        raise
        
    finally:
        # 🔧 记录业务请求
        duration = time.time() - start_time
        await metrics_collector.record_request(
            endpoint=path,
            status=status,
            duration=duration
        )
        logger.info(f"📊 Recorded: {path} ({status}, {duration:.3f}s)")


# ============ 路由定义 ============

@app.get("/", response_class=HTMLResponse)
@track_performance("chat_page")
async def get_chat_page(request: Request, session_data: dict = Depends(get_session_data)):
    """Serve the chat interface."""
    # 记录会话开始
    metrics_collector.record_session(session_data["session_id"], action='start')
    
    response = templates.TemplateResponse("chat.html", {
        "request": request, 
        "session_id": session_data["session_id"],
        "chat_history": session_data["user_data"].get("chat_history", [])
    })
    response.set_cookie(key="session_id", value=session_data["session_id"])
    return response


@app.post("/chat")
@track_performance("chat")
async def chat(chat_message: ChatMessage, session_data: dict = Depends(get_session_data)):
    """Process a chat message and return the AI response."""
    try:
        # 估算输入token
        metrics_collector.estimate_tokens(chat_message.message, 'input')
        
        # 增加活跃会话
        await metrics_collector.increment_sessions()
        
        # Process the user message
        ai_response = await process_user_message(session_data, chat_message.message)
        
        # 估算输出token
        metrics_collector.estimate_tokens(ai_response, 'output')
        
        # Update the user's chat history
        update_user_chat_history(session_data["session_id"], chat_message.message, ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        logger.error(f"❌ Error processing chat message: {e}")
        metrics_collector.record_error(type(e).__name__, "chat")
        return JSONResponse(
            content={"error": "An unexpected error occurred. Please try again later."}, 
            status_code=500
        )
    finally:
        # 减少活跃会话
        await metrics_collector.decrement_sessions()


# ============ SSE 流式聊天端点 ============

async def _stream_chat_events(session_data: dict, user_message: str):
    """
    异步生成器：调用 LangGraph 的 astream_events 逐 token 推送 SSE 事件。
    事件类型: token / done / error / pending_action
    """
    from customer_support_chat.app.graph import multi_agentic_graph
    from langchain_core.messages import ToolMessage

    # 准备 LangGraph config
    config = session_data.get("config", {})
    if "configurable" not in config:
        langgraph_config = {"configurable": config}
    else:
        langgraph_config = config

    session_id = session_data["session_id"]

    # 估算输入 token
    metrics_collector.estimate_tokens(user_message, 'input')
    await metrics_collector.increment_sessions()

    start_time = time.time()
    first_byte_recorded = False
    accumulated_content = ""

    # 写入用户输入到操作日志
    try:
        from web_app.app.core.user_data_manager import add_operation_log
        add_operation_log(session_id, {
            "type": "user_input",
            "title": "User Message",
            "content": user_message
        })
    except Exception as log_err:
        logger.debug(f"Skip operation log (user_input): {log_err}")

    try:
        # 使用 astream_events 获取细粒度事件流
        async for event in multi_agentic_graph.astream_events(
            {"messages": [("user", user_message)]},
            langgraph_config,
            version="v2"
        ):
            kind = event.get("event")

            # 仅捕获 LLM 流式产出的内容 token
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None) if chunk is not None else None

                # content 可能是 str 或 list[dict]（多模态），统一处理为字符串
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            text += part["text"]

                if not text:
                    continue

                # 记录首字节时间
                if not first_byte_recorded:
                    ttfb = time.time() - start_time
                    stream_first_byte_time.labels(endpoint="chat_stream").observe(ttfb)
                    first_byte_recorded = True
                    logger.info(f"⚡ SSE first byte: {ttfb*1000:.1f}ms")

                accumulated_content += text
                yield {
                    "event": "message",
                    "data": json.dumps({"content": text, "type": "token"}, ensure_ascii=False)
                }

        # 流结束后：检查是否有 HITL 中断需要等待用户审批
        try:
            snapshot = multi_agentic_graph.get_state(langgraph_config)
        except Exception as snap_err:
            logger.warning(f"Failed to get graph snapshot: {snap_err}")
            snapshot = None

        if snapshot is not None and snapshot.next:
            messages = snapshot.values.get("messages", []) if snapshot.values else []
            last_message = messages[-1] if messages else None

            if last_message and getattr(last_message, "tool_calls", None):
                tool_calls_details = [
                    {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                    for tc in last_message.tool_calls
                ]

                # 写入 pending_action 与操作日志
                try:
                    from web_app.app.core.user_data_manager import set_pending_action, add_operation_log
                    set_pending_action(session_id, {
                        "tool_calls": tool_calls_details,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    add_operation_log(session_id, {
                        "type": "system_message",
                        "title": "HITL Interrupt",
                        "content": "Sensitive action requires user approval",
                        "details": {"tool_calls": tool_calls_details}
                    })
                except Exception as he:
                    logger.warning(f"HITL persistence skipped: {he}")

                metrics_collector.record_approval('pending')

                # 推送 pending_action 事件
                yield {
                    "event": "message",
                    "data": json.dumps(
                        {"content": tool_calls_details, "type": "pending_action"},
                        ensure_ascii=False
                    )
                }

        # 持久化对话历史
        final_text = accumulated_content if accumulated_content else \
            "I'm sorry, I didn't understand that. Could you please rephrase?"
        try:
            update_user_chat_history(session_id, user_message, final_text)
        except Exception as hist_err:
            logger.warning(f"Failed to persist chat history: {hist_err}")

        # 估算输出 token
        metrics_collector.estimate_tokens(final_text, 'output')

        # 推送 done 事件
        yield {
            "event": "message",
            "data": json.dumps({"content": "", "type": "done"}, ensure_ascii=False)
        }

    except asyncio.CancelledError:
        # 客户端断连：优雅终止
        logger.info(f"🔌 SSE client disconnected: session={session_id}")
        raise
    except Exception as e:
        logger.error(f"❌ SSE stream error: {e}")
        metrics_collector.record_error(type(e).__name__, "chat_stream")
        yield {
            "event": "message",
            "data": json.dumps(
                {"content": "An unexpected error occurred. Please try again later.", "type": "error"},
                ensure_ascii=False
            )
        }
    finally:
        await metrics_collector.decrement_sessions()


@app.post("/chat/stream")
async def chat_stream(chat_message: ChatMessage, request: Request,
                     session_data: dict = Depends(get_session_data)):
    """
    SSE 流式聊天端点：使用 LangGraph astream_events 逐 token 推送。
    保留 /chat JSON 端点作为降级路径。
    """
    async def event_generator():
        async for evt in _stream_chat_events(session_data, chat_message.message):
            # 客户端断连检查
            if await request.is_disconnected():
                logger.info("🔌 Client disconnected, terminating stream")
                break
            yield evt

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，保证首字节
        }
    )


# ============ HITL (Human-in-the-Loop) 端点 ============

@app.get("/pending-action")
async def get_pending_action_endpoint(session_data: dict = Depends(get_session_data)):
    """
    检查是否有待审批的操作
    ⚠️  此端点被排除，不会计入 total_requests
    """
    try:
        pending_action = get_pending_action(session_data["session_id"])
        if pending_action:
            # 记录待审批请求
            metrics_collector.record_approval('pending')
            return JSONResponse(content={"pending_action": pending_action})
        else:
            return JSONResponse(content={"pending_action": None})
    except Exception as e:
        logger.error(f"❌ Error checking pending action: {e}")
        return JSONResponse(
            content={"error": "An unexpected error occurred. Please try again later."}, 
            status_code=500
        )


@app.post("/approve-action")
@track_performance("approve")
async def approve_action(request: Request, session_data: dict = Depends(get_session_data)):
    """Approve a pending action."""
    try:
        # 记录审批决策
        metrics_collector.record_approval('approved')
        
        from customer_support_chat.app.services.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "approve")
        
        update_user_chat_history(session_data["session_id"], "[User approved action]", ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        logger.error(f"❌ Error processing approval: {e}")
        metrics_collector.record_error(type(e).__name__, "approve")
        return JSONResponse(
            content={"error": "An unexpected error occurred. Please try again later."}, 
            status_code=500
        )


@app.post("/reject-action")
@track_performance("reject")
async def reject_action(request: Request, session_data: dict = Depends(get_session_data)):
    """Reject a pending action."""
    try:
        # 记录审批决策
        metrics_collector.record_approval('rejected')
        
        from customer_support_chat.app.services.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "reject")
        
        update_user_chat_history(session_data["session_id"], "[User rejected action]", ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        logger.error(f"❌ Error processing rejection: {e}")
        metrics_collector.record_error(type(e).__name__, "reject")
        return JSONResponse(
            content={"error": "An unexpected error occurred. Please try again later."}, 
            status_code=500
        )


@app.get("/operation-log")
async def get_operation_log_endpoint(session_data: dict = Depends(get_session_data)):
    """
    获取操作日志
    ⚠️  此端点被排除，不会计入 total_requests
    """
    try:
        # Get only the most recent 20 log entries to reduce data transfer
        operation_log = get_operation_log(session_data["session_id"], limit=20)
        return JSONResponse(content={"operation_log": operation_log})
    except Exception as e:
        logger.error(f"❌ Error retrieving operation log: {e}")
        return JSONResponse(
            content={"error": "An unexpected error occurred. Please try again later."}, 
            status_code=500
        )


# ============ 监控端点 ============

@app.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus指标端点 - 供Prometheus抓取
    ⚠️  此端点被排除，不会计入 total_requests
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/health")
async def health_check():
    """
    健康检查端点
    ⚠️  此端点被排除，不会计入 total_requests
    """
    return JSONResponse(content={
        "status": "healthy",
        "timestamp": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    })


@app.get("/stats")
async def get_realtime_stats():
    """
    实时统计数据 - 供Dashboard前端使用
    ⚠️  此端点被排除，不会计入 total_requests
    """
    try:
        # ✅ 获取统计数据（不增加计数）
        stats = await metrics_collector.get_stats()
        
        # 添加系统资源信息
        stats['system'] = {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2)
        }
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"❌ Error getting stats: {e}")
        return JSONResponse(
            content={"error": "Failed to retrieve statistics"}, 
            status_code=500
        )


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """性能监控Dashboard页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ============ 应用生命周期事件 ============

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("🚀 Application starting up...")
    logger.info(f"📊 MetricsCollector initialized: {metrics_collector}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("👋 Application shutting down...")