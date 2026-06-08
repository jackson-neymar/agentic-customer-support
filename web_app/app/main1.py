from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
import uuid
import os
import sys
import psutil
import time
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
    MetricsCollector, 
    track_performance,
    generate_latest,
    CONTENT_TYPE_LATEST
)

# Load environment variables
load_dotenv()

app = FastAPI()

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

# ============ 中间件：请求追踪（必须在路由之前定义）============
metrics_collector = MetricsCollector() 
import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 配置日志
logger = logging.getLogger(__name__)

@app.middleware("http")
async def track_requests(request: Request, call_next):
    """追踪所有HTTP请求，排除监控端点"""
    
    # 定义需要排除的路径
    EXCLUDED_PATHS = (
        "/api/stats",
        "/api/pending-action",
        "/api/operation-log",
        "/api/metrics",
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/static",
        "/favicon.ico",
    )
    
    path = request.url.path
    
    # 🔧 判断是否需要追踪（注意：startswith 需要完整匹配）
    should_track = not any(path.startswith(excluded) for excluded in EXCLUDED_PATHS)
    
    # 添加调试日志
    if should_track:
        logger.info(f"✅ TRACKING: {request.method} {path}")
    else:
        logger.debug(f"⏭️  SKIPPING: {request.method} {path}")
    
    start_time = time.time()
    status = "success"
    status_code = 200
    
    try:
        # 处理请求
        response = await call_next(request)
        status_code = response.status_code
        
        # 根据状态码判断成功/失败
        if status_code >= 400:
            status = "error"
        
        # 添加处理时间到响应头
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        
        return response
        
    except Exception as e:
        status = "error"
        status_code = 500
        logger.error(f"❌ Request error on {path}: {e}", exc_info=True)
        
        # 返回错误响应
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(e),
                "path": path
            }
        )
        
    finally:
        # 🔧 只记录需要追踪的请求
        if should_track:
            duration = time.time() - start_time
            
            try:
                metrics_collector.record_request(
                    endpoint=path,
                    method=request.method,
                    status_code=status_code,
                    duration=duration
                )
                logger.info(
                    f"📊 Recorded: {request.method} {path} "
                    f"[{status_code}] ({status}, {duration:.3f}s)"
                )
            except Exception as e:
                logger.error(f"❌ Failed to record metrics: {e}")
# @app.middleware("http")
# async def track_requests(request: Request, call_next):
#     """追踪所有HTTP请求，排除监控端点"""
    
#     # 定义需要排除的路径
#     EXCLUDED_PATHS = (
#         "/stats",
#         "/pending-action",
#         "/operation-log",
#         "/metrics",
#         "/health",
#         "/docs",
#         "/openapi.json",
#         "/redoc",
#         "/static",
#         "/favicon.ico",
#     )
    
#     path = request.url.path
    
#     # 🔧 关键修复：在处理请求之前就判断
#     should_track = not path.startswith(EXCLUDED_PATHS)
    
#     # 添加调试日志（可选，生产环境可删除）
#     if should_track:
#         logger.info(f"✅ TRACKING: {path}")
#     else:
#         logger.debug(f"⏭️  SKIPPING: {path}")
    
#     start_time = time.time()
#     status = "success"
    
#     try:
#         # 处理请求
#         response = await call_next(request)
        
#         # 根据状态码判断成功/失败
#         if response.status_code >= 400:
#             status = "error"
        
#         return response
        
#     except Exception as e:
#         status = "error"
#         logger.error(f"Request error on {path}: {e}")
#         raise
        
#     finally:
#         # 🔧 关键：只记录需要追踪的请求
#         if should_track:
#             duration = time.time() - start_time
#             metrics_collector.record_request(
#                 endpoint=path,
#                 status=status,
#                 duration=duration
#             )
#             logger.info(f"📊 Recorded: {path} ({status}, {duration:.3f}s)")

# ============ 路由定义 ============

@app.get("/", response_class=HTMLResponse)
@track_performance("chat_page")
async def get_chat_page(request: Request, session_data: dict = Depends(get_session_data)):
    """Serve the chat interface."""
    # 记录会话开始
    MetricsCollector.record_session(session_data["session_id"], action='start')
    
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
        MetricsCollector.estimate_tokens(chat_message.message, 'input')
        
        # Process the user message
        ai_response = await process_user_message(session_data, chat_message.message)
        
        # 估算输出token
        MetricsCollector.estimate_tokens(ai_response, 'output')
        
        # Update the user's chat history
        update_user_chat_history(session_data["session_id"], chat_message.message, ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        print(f"Error processing chat message: {e}")
        MetricsCollector.record_error(type(e).__name__, "chat")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


# ============ HITL (Human-in-the-Loop) 端点 ============

@app.get("/pending-action")
async def get_pending_action_endpoint(session_data: dict = Depends(get_session_data)):
    """Check if there is a pending action requiring user approval."""
    try:
        pending_action = get_pending_action(session_data["session_id"])
        if pending_action:
            return JSONResponse(content={"pending_action": pending_action})
        else:
            return JSONResponse(content={"pending_action": None})
    except Exception as e:
        print(f"Error checking pending action: {e}")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


@app.post("/approve-action")
@track_performance("approve")
async def approve_action(request: Request, session_data: dict = Depends(get_session_data)):
    """Approve a pending action."""
    try:
        # 记录审批决策
        MetricsCollector.record_approval('approved')
        
        from customer_support_chat.app.services.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "approve")
        
        update_user_chat_history(session_data["session_id"], "[User approved action]", ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        print(f"Error processing approval: {e}")
        MetricsCollector.record_error(type(e).__name__, "approve")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


@app.post("/reject-action")
@track_performance("reject")
async def reject_action(request: Request, session_data: dict = Depends(get_session_data)):
    """Reject a pending action."""
    try:
        # 记录审批决策
        MetricsCollector.record_approval('rejected')
        
        from customer_support_chat.app.services.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "reject")
        
        update_user_chat_history(session_data["session_id"], "[User rejected action]", ai_response)
        
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        print(f"Error processing rejection: {e}")
        MetricsCollector.record_error(type(e).__name__, "reject")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


@app.get("/operation-log")
async def get_operation_log_endpoint(session_data: dict = Depends(get_session_data)):
    """Get the operation log for the current session."""
    try:
        # Get only the most recent 20 log entries to reduce data transfer
        operation_log = get_operation_log(session_data["session_id"], limit=20)
        return JSONResponse(content={"operation_log": operation_log})
    except Exception as e:
        print(f"Error retrieving operation log: {e}")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


# ============ 监控端点 ============

@app.get("/metrics")
@track_performance("metrics")
async def prometheus_metrics():
    """Prometheus指标端点 - 供Prometheus抓取"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/health")
@track_performance("health")
async def health_check():
    """健康检查端点"""
    return JSONResponse(content={
        "status": "healthy",
        "timestamp": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    })


@app.get("/stats")
@track_performance("stats")
async def get_realtime_stats():
    """实时统计数据 - 供Dashboard前端使用"""
    stats = MetricsCollector.get_stats()
    
    # 添加系统资源信息
    stats['system'] = {
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'memory_percent': psutil.virtual_memory().percent,
        'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2)
    }
    
    return JSONResponse(content=stats)


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """性能监控Dashboard页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})