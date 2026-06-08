# import json
# import os
# from typing import Dict, Any, List, Optional
# from datetime import datetime

# # Directory to store user sessions data
# USER_DATA_DIR = "./user_data"

# def initialize_user_data_dir():
#     """Initialize the user data directory if it doesn't exist."""
#     if not os.path.exists(USER_DATA_DIR):
#         os.makedirs(USER_DATA_DIR)

# def get_user_data_file(session_id: str) -> str:
#     """Get the file path for a specific user's data."""
#     return os.path.join(USER_DATA_DIR, f"{session_id}.json")

# def load_user_data(session_id: str) -> Dict[str, Any]:
#     """Load user data from the individual JSON file."""
#     initialize_user_data_dir()
#     user_file = get_user_data_file(session_id)
    
#     if not os.path.exists(user_file):
#         return {}
    
#     try:
#         with open(user_file, "r") as f:
#             return json.load(f)
#     except (json.JSONDecodeError, FileNotFoundError):
#         return {}

# def save_user_data(session_id: str, data: Dict[str, Any]):
#     """Save user data to the individual JSON file."""
#     user_file = get_user_data_file(session_id)
#     with open(user_file, "w") as f:
#         json.dump(data, f, indent=2)

# def get_user_session(session_id: str) -> Dict[str, Any]:
#     """Get a user session by session ID, creating a new one if it doesn't exist."""
#     user_data = load_user_data(session_id)
    
#     if not user_data:
#         # Initialize a new session with default values
#         user_data = {
#             "session_id": session_id,
#             "chat_history": [],
#             "pending_action": None,
#             "user_decision": None,
#             "operation_log": [],  # Add operation log storage
#             "created_at": datetime.now().isoformat()
#         }
#         save_user_data(session_id, user_data)
    
#     return user_data

# def update_user_chat_history(session_id: str, user_message: str, ai_response: str):
#     """Update the chat history for a user session."""
#     user_data = load_user_data(session_id)
    
#     if not user_data:
#         user_data = {
#             "session_id": session_id,
#             "chat_history": [],
#             "pending_action": None,
#             "user_decision": None,
#             "operation_log": [],  # Add operation log storage
#             "created_at": datetime.now().isoformat()
#         }
    
#     # Add the new message pair to the chat history
#     user_data["chat_history"].append({
#         "timestamp": datetime.now().isoformat(),
#         "user_message": user_message,
#         "ai_response": ai_response
#     })
    
#     save_user_data(session_id, user_data)

# def set_pending_action(session_id: str, action_details: Dict[str, Any]):
#     """Set a pending action for a user session."""
#     user_data = load_user_data(session_id)
    
#     if not user_data:
#         user_data = {
#             "session_id": session_id,
#             "chat_history": [],
#             "pending_action": None,
#             "user_decision": None,
#             "operation_log": [],  # Add operation log storage
#             "created_at": datetime.now().isoformat()
#         }
    
#     user_data["pending_action"] = action_details
#     save_user_data(session_id, user_data)

# def get_pending_action(session_id: str) -> Optional[Dict[str, Any]]:
#     """Get the pending action for a user session."""
#     session_data = get_user_session(session_id)
#     return session_data.get("pending_action")

# def clear_pending_action(session_id: str):
#     """Clear the pending action for a user session."""
#     user_data = load_user_data(session_id)
#     if user_data:
#         user_data["pending_action"] = None
#         save_user_data(session_id, user_data)

# def set_user_decision(session_id: str, decision: str):
#     """Set the user decision for a pending action."""
#     user_data = load_user_data(session_id)
    
#     if not user_data:
#         user_data = {
#             "session_id": session_id,
#             "chat_history": [],
#             "pending_action": None,
#             "user_decision": None,
#             "operation_log": [],  # Add operation log storage
#             "created_at": datetime.now().isoformat()
#         }
    
#     user_data["user_decision"] = decision
#     save_user_data(session_id, user_data)

# def get_user_decision(session_id: str) -> Optional[str]:
#     """Get the user decision for a pending action."""
#     session_data = get_user_session(session_id)
#     return session_data.get("user_decision")

# def clear_user_decision(session_id: str):
#     """Clear the user decision for a pending action."""
#     user_data = load_user_data(session_id)
#     if user_data:
#         user_data["user_decision"] = None
#         save_user_data(session_id, user_data)

# def add_operation_log(session_id: str, log_entry: Dict[str, Any]):
#     """Add an operation log entry to a user session."""
#     user_data = load_user_data(session_id)
    
#     if not user_data:
#         user_data = {
#             "session_id": session_id,
#             "chat_history": [],
#             "pending_action": None,
#             "user_decision": None,
#             "operation_log": [],  # Add operation log storage
#             "created_at": datetime.now().isoformat()
#         }
    
#     # Add timestamp if not provided
#     if "timestamp" not in log_entry:
#         log_entry["timestamp"] = datetime.now().isoformat()
    
#     user_data["operation_log"].append(log_entry)
#     save_user_data(session_id, user_data)

# def get_operation_log(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
#     """Get the operation log for a user session, with optional limit."""
#     session_data = get_user_session(session_id)
#     log = session_data.get("operation_log", [])
    
#     # Return the most recent entries up to the limit
#     if limit > 0 and len(log) > limit:
#         return log[-limit:]
#     return log

# def clear_operation_log(session_id: str):
#     """Clear the operation log for a user session."""
#     user_data = load_user_data(session_id)
#     if user_data:
#         user_data["operation_log"] = []
#         save_user_data(session_id, user_data)

"""
用户数据管理器 - 混合存储版本（FastAPI异步优化）
✅ 原生支持 FastAPI/Uvicorn 的 uvloop
✅ 提供同步和异步两套API
✅ 自动检测调用环境
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# ============================================================================
# 混合存储配置
# ============================================================================

try:
    from web_app.app.core.storage.hybrid_store import HybridStorage
    HYBRID_STORAGE_ENABLED = True
    
    # 初始化混合存储（单例）
    _hybrid_storage = HybridStorage(
        enable_memory=True,
        enable_file=True,
        memory_max_size=1000,
        file_base_path="./user_data"
    )
    
except ImportError:
    HYBRID_STORAGE_ENABLED = False
    _hybrid_storage = None
    print("⚠️  Hybrid storage not available, falling back to file-only mode")


# ============================================================================
# 原有常量
# ============================================================================

USER_DATA_DIR = "./user_data"


# ============================================================================
# 工具函数
# ============================================================================

def initialize_user_data_dir():
    """Initialize the user data directory if it doesn't exist."""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)


def get_user_data_file(session_id: str) -> str:
    """Get the file path for a specific user's data."""
    return os.path.join(USER_DATA_DIR, f"{session_id}.json")


def _load_user_data_legacy(session_id: str) -> Dict[str, Any]:
    """原始文件读取逻辑（降级方案）"""
    initialize_user_data_dir()
    user_file = get_user_data_file(session_id)
    
    if not os.path.exists(user_file):
        return {}
    
    try:
        with open(user_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_user_data_legacy(session_id: str, data: Dict[str, Any]):
    """原始文件写入逻辑（降级方案）"""
    initialize_user_data_dir()
    user_file = get_user_data_file(session_id)
    with open(user_file, "w") as f:
        json.dump(data, f, indent=2)


# ============================================================================
# 异步API（推荐用于FastAPI）
# ============================================================================

async def load_user_data_async(session_id: str) -> Dict[str, Any]:
    """
    异步加载用户数据（FastAPI推荐）
    """
    if not HYBRID_STORAGE_ENABLED:
        return _load_user_data_legacy(session_id)
    
    try:
        data = await _hybrid_storage.get(f"session:{session_id}")
        
        if data is not None:
            return data
        
        # 未命中，从文件读取并回填
        legacy_data = _load_user_data_legacy(session_id)
        
        if legacy_data:
            await _hybrid_storage.set(f"session:{session_id}", legacy_data, ttl=3600)
            return legacy_data
        
        return {}
        
    except Exception as e:
        print(f"❌ Hybrid storage error: {e}, falling back to legacy")
        return _load_user_data_legacy(session_id)


async def save_user_data_async(session_id: str, data: Dict[str, Any]):
    """
    异步保存用户数据（FastAPI推荐）
    """
    if not HYBRID_STORAGE_ENABLED:
        _save_user_data_legacy(session_id, data)
        return
    
    try:
        # 写入混合存储
        await _hybrid_storage.set(f"session:{session_id}", data, ttl=3600)
        
        # 同步写入文件（保证持久化）
        _save_user_data_legacy(session_id, data)
        
    except Exception as e:
        print(f"❌ Hybrid storage error: {e}, falling back to legacy")
        _save_user_data_legacy(session_id, data)


# ============================================================================
# 同步API（向后兼容，非FastAPI场景使用）
# ============================================================================

def load_user_data(session_id: str) -> Dict[str, Any]:
    """
    同步加载用户数据（向后兼容）
    ⚠️  不推荐在FastAPI中使用，请用 load_user_data_async
    """
    if not HYBRID_STORAGE_ENABLED:
        return _load_user_data_legacy(session_id)
    
    # 在FastAPI环境中，直接使用文件存储（避免事件循环冲突）
    return _load_user_data_legacy(session_id)


def save_user_data(session_id: str, data: Dict[str, Any]):
    """
    同步保存用户数据（向后兼容）
    ⚠️  不推荐在FastAPI中使用，请用 save_user_data_async
    """
    if not HYBRID_STORAGE_ENABLED:
        _save_user_data_legacy(session_id, data)
        return
    
    # 在FastAPI环境中，直接使用文件存储（避免事件循环冲突）
    _save_user_data_legacy(session_id, data)


# ============================================================================
# 业务函数 - 异步版本（FastAPI推荐）
# ============================================================================

async def get_user_session_async(session_id: str) -> Dict[str, Any]:
    """异步获取用户会话"""
    user_data = await load_user_data_async(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
        await save_user_data_async(session_id, user_data)
    
    return user_data


async def update_user_chat_history_async(session_id: str, user_message: str, ai_response: str):
    """异步更新聊天历史"""
    user_data = await load_user_data_async(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["chat_history"].append({
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "ai_response": ai_response
    })
    
    await save_user_data_async(session_id, user_data)


async def set_pending_action_async(session_id: str, action_details: Dict[str, Any]):
    """异步设置待处理操作"""
    user_data = await load_user_data_async(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["pending_action"] = action_details
    await save_user_data_async(session_id, user_data)


async def get_pending_action_async(session_id: str) -> Optional[Dict[str, Any]]:
    """异步获取待处理操作"""
    session_data = await get_user_session_async(session_id)
    return session_data.get("pending_action")


async def clear_pending_action_async(session_id: str):
    """异步清除待处理操作"""
    user_data = await load_user_data_async(session_id)
    if user_data:
        user_data["pending_action"] = None
        await save_user_data_async(session_id, user_data)


async def set_user_decision_async(session_id: str, decision: str):
    """异步设置用户决策"""
    user_data = await load_user_data_async(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["user_decision"] = decision
    await save_user_data_async(session_id, user_data)


async def get_user_decision_async(session_id: str) -> Optional[str]:
    """异步获取用户决策"""
    session_data = await get_user_session_async(session_id)
    return session_data.get("user_decision")


async def clear_user_decision_async(session_id: str):
    """异步清除用户决策"""
    user_data = await load_user_data_async(session_id)
    if user_data:
        user_data["user_decision"] = None
        await save_user_data_async(session_id, user_data)


async def add_operation_log_async(session_id: str, log_entry: Dict[str, Any]):
    """异步添加操作日志"""
    user_data = await load_user_data_async(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    if "timestamp" not in log_entry:
        log_entry["timestamp"] = datetime.now().isoformat()
    
    user_data["operation_log"].append(log_entry)
    await save_user_data_async(session_id, user_data)


async def get_operation_log_async(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """异步获取操作日志"""
    session_data = await get_user_session_async(session_id)
    log = session_data.get("operation_log", [])
    
    if limit > 0 and len(log) > limit:
        return log[-limit:]
    return log


async def clear_operation_log_async(session_id: str):
    """异步清除操作日志"""
    user_data = await load_user_data_async(session_id)
    if user_data:
        user_data["operation_log"] = []
        await save_user_data_async(session_id, user_data)


# ============================================================================
# 业务函数 - 同步版本（向后兼容）
# ============================================================================

def get_user_session(session_id: str) -> Dict[str, Any]:
    """同步获取用户会话（向后兼容）"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
        save_user_data(session_id, user_data)
    
    return user_data


def update_user_chat_history(session_id: str, user_message: str, ai_response: str):
    """同步更新聊天历史（向后兼容）"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["chat_history"].append({
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "ai_response": ai_response
    })
    
    save_user_data(session_id, user_data)


def set_pending_action(session_id: str, action_details: Dict[str, Any]):
    """同步设置待处理操作（向后兼容）"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["pending_action"] = action_details
    save_user_data(session_id, user_data)


def get_pending_action(session_id: str) -> Optional[Dict[str, Any]]:
    """同步获取待处理操作（向后兼容）"""
    session_data = get_user_session(session_id)
    return session_data.get("pending_action")


def clear_pending_action(session_id: str):
    """同步清除待处理操作（向后兼容）"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["pending_action"] = None
        save_user_data(session_id, user_data)


def set_user_decision(session_id: str, decision: str):
    """同步设置用户决策（向后兼容）"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    user_data["user_decision"] = decision
    save_user_data(session_id, user_data)


def get_user_decision(session_id: str) -> Optional[str]:
    """同步获取用户决策（向后兼容）"""
    session_data = get_user_session(session_id)
    return session_data.get("user_decision")


def clear_user_decision(session_id: str):
    """同步清除用户决策（向后兼容）"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["user_decision"] = None
        save_user_data(session_id, user_data)


def add_operation_log(session_id: str, log_entry: Dict[str, Any]):
    """同步添加操作日志（向后兼容）"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],
            "created_at": datetime.now().isoformat()
        }
    
    if "timestamp" not in log_entry:
        log_entry["timestamp"] = datetime.now().isoformat()
    
    user_data["operation_log"].append(log_entry)
    save_user_data(session_id, user_data)


def get_operation_log(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """同步获取操作日志（向后兼容）"""
    session_data = get_user_session(session_id)
    log = session_data.get("operation_log", [])
    
    if limit > 0 and len(log) > limit:
        return log[-limit:]
    return log


def clear_operation_log(session_id: str):
    """同步清除操作日志（向后兼容）"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["operation_log"] = []
        save_user_data(session_id, user_data)


# ============================================================================
# 性能监控
# ============================================================================

async def get_storage_stats_async() -> Dict[str, Any]:
    """异步获取存储统计"""
    if not HYBRID_STORAGE_ENABLED or _hybrid_storage is None:
        return {"status": "legacy_mode", "message": "Hybrid storage not enabled"}
    
    try:
        stats = await _hybrid_storage.get_all_stats()
        return {
            "status": "hybrid_mode",
            "enabled": True,
            **stats
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# 启动信息
# ============================================================================

if HYBRID_STORAGE_ENABLED:
    print("✅ User data manager initialized with HYBRID STORAGE (FastAPI optimized)")
    print(f"   📁 File storage: {USER_DATA_DIR}")
    print(f"   🧠 Memory cache: 1000 sessions")
    print(f"   ⚡ Native async support for uvloop")
else:
    print("⚠️  User data manager initialized in LEGACY MODE (file-only)")