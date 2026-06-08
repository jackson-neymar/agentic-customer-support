"""
混合存储系统 - 内存 + 文件双层缓存（支持同步和异步）
"""

import json
import os
import threading
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict


class HybridStorage:
    """
    混合存储系统（同步版本，兼容 LangChain 工具）
    - 一级缓存：内存 LRU（快速读取）
    - 二级缓存：文件持久化（断电保护）
    """
    
    def __init__(
        self,
        enable_memory: bool = True,
        enable_file: bool = True,
        memory_max_size: int = 1000,
        file_base_path: str = "./storage_cache"
    ):
        self.enable_memory = enable_memory
        self.enable_file = enable_file
        self.memory_max_size = memory_max_size
        self.file_base_path = file_base_path
        
        # 内存缓存（LRU）
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()  # 使用线程锁而不是 asyncio.Lock
        
        # 统计信息
        self._stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "file_hits": 0,
            "file_misses": 0,
            "writes": 0
        }
        
        # 初始化文件存储目录
        if self.enable_file:
            os.makedirs(self.file_base_path, exist_ok=True)
        
        print(f"✅ HybridStorage initialized (sync mode):")
        print(f"   🧠 Memory cache: {self.memory_max_size} items")
        print(f"   📁 File storage: {self.file_base_path}")
    
    
    def _get_file_path(self, key: str) -> str:
        """获取文件路径"""
        safe_key = key.replace(":", "_").replace("/", "_")
        return os.path.join(self.file_base_path, f"{safe_key}.json")
    
    
    def get(self, key: str) -> Optional[Any]:
        """获取数据（同步版本）"""
        with self._lock:
            # 1️⃣ 尝试从内存读取
            if self.enable_memory and key in self._memory_cache:
                entry = self._memory_cache[key]
                
                # 检查是否过期
                if "expires_at" in entry and entry["expires_at"]:
                    if datetime.now() > datetime.fromisoformat(entry["expires_at"]):
                        del self._memory_cache[key]
                        self._stats["memory_misses"] += 1
                    else:
                        self._memory_cache.move_to_end(key)
                        self._stats["memory_hits"] += 1
                        return entry["value"]
                else:
                    self._memory_cache.move_to_end(key)
                    self._stats["memory_hits"] += 1
                    return entry["value"]
            else:
                self._stats["memory_misses"] += 1
            
            # 2️⃣ 尝试从文件读取
            if self.enable_file:
                file_path = self._get_file_path(key)
                
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            entry = json.load(f)
                        
                        # 检查是否过期
                        if "expires_at" in entry and entry["expires_at"]:
                            if datetime.now() > datetime.fromisoformat(entry["expires_at"]):
                                os.remove(file_path)
                                self._stats["file_misses"] += 1
                                return None
                        
                        # 回填到内存缓存
                        if self.enable_memory:
                            self._set_memory(key, entry)
                        
                        self._stats["file_hits"] += 1
                        return entry["value"]
                    
                    except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
                        print(f"⚠️  File read error for key '{key}': {e}")
                        self._stats["file_misses"] += 1
                        return None
                else:
                    self._stats["file_misses"] += 1
            
            return None
    
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """
        设置数据（同步版本）
        
        Args:
            key: 键名
            value: 值
            ttl: 过期时间（秒），0 表示永不过期
        """
        with self._lock:
            expires_at = None
            if ttl > 0:
                expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
            
            entry = {
                "value": value,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at
            }
            
            # 写入内存
            if self.enable_memory:
                self._set_memory(key, entry)
            
            # 写入文件
            if self.enable_file:
                file_path = self._get_file_path(key)
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(entry, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"❌ Failed to write file cache for key '{key}': {e}")
            
            self._stats["writes"] += 1
    
    
    def _set_memory(self, key: str, entry: Dict[str, Any]):
        """内存缓存设置（带 LRU 淘汰）"""
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
        
        self._memory_cache[key] = entry
        
        # LRU 淘汰：超过最大容量时删除最旧的
        while len(self._memory_cache) > self.memory_max_size:
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
    
    
    def delete(self, key: str):
        """删除数据（同步版本）"""
        with self._lock:
            # 删除内存
            if self.enable_memory and key in self._memory_cache:
                del self._memory_cache[key]
            
            # 删除文件
            if self.enable_file:
                file_path = self._get_file_path(key)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"⚠️  Failed to delete file for key '{key}': {e}")
    
    
    def clear(self):
        """清空所有缓存（同步版本）"""
        with self._lock:
            # 清空内存
            if self.enable_memory:
                self._memory_cache.clear()
            
            # 清空文件
            if self.enable_file and os.path.exists(self.file_base_path):
                for filename in os.listdir(self.file_base_path):
                    file_path = os.path.join(self.file_base_path, filename)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"⚠️  Failed to delete file '{filename}': {e}")
    
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取统计信息（同步版本）"""
        memory_size = len(self._memory_cache) if self.enable_memory else 0
        
        file_count = 0
        if self.enable_file and os.path.exists(self.file_base_path):
            try:
                file_count = len([f for f in os.listdir(self.file_base_path) if f.endswith(".json")])
            except Exception:
                file_count = 0
        
        total_requests = (
            self._stats["memory_hits"] + 
            self._stats["memory_misses"]
        )
        
        hit_rate = 0
        if total_requests > 0:
            hit_rate = (self._stats["memory_hits"] / total_requests) * 100
        
        return {
            "memory": {
                "size": memory_size,
                "max_size": self.memory_max_size,
                "hits": self._stats["memory_hits"],
                "misses": self._stats["memory_misses"],
                "hit_rate": f"{hit_rate:.2f}%"
            },
            "file": {
                "count": file_count,
                "hits": self._stats["file_hits"],
                "misses": self._stats["file_misses"]
            },
            "writes": self._stats["writes"]
        }


# ==================== 异步包装器（可选） ====================

class AsyncHybridStorage:
    """
    HybridStorage 的异步包装器
    用于需要异步调用的场景（如 FastAPI 路由）
    """
    
    def __init__(self, storage: HybridStorage):
        self._storage = storage
    
    async def get(self, key: str) -> Optional[Any]:
        """异步获取数据"""
        return self._storage.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """异步设置数据"""
        self._storage.set(key, value, ttl)
    
    async def delete(self, key: str):
        """异步删除数据"""
        self._storage.delete(key)
    
    async def clear(self):
        """异步清空缓存"""
        self._storage.clear()
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """异步获取统计信息"""
        return self._storage.get_all_stats()