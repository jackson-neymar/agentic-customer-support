"""
内存存储层 - L1缓存
特点：速度最快、容量有限、不持久化
"""
import time
import asyncio
from typing import Any, Optional, Dict, List
from collections import OrderedDict
from .base import BaseStorage, StorageStats
import logging

logger = logging.getLogger(__name__)


class MemoryStorage(BaseStorage):
    """
    内存存储实现（LRU缓存）
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        初始化内存存储
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.ttl_map: Dict[str, float] = {}
        self.stats = StorageStats()
        self.lock = asyncio.Lock()
        
        logger.info(f"✅ MemoryStorage initialized (max_size={max_size}, ttl={default_ttl}s)")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取数据（LRU更新）"""
        async with self.lock:
            self.stats.reads += 1
            
            # 检查是否存在
            if key not in self.cache:
                self.stats.misses += 1
                logger.debug(f"🔍 Memory MISS: {key}")
                return None
            
            # 检查是否过期
            if key in self.ttl_map and time.time() > self.ttl_map[key]:
                await self._delete_key(key)
                self.stats.misses += 1
                logger.debug(f"⏰ Memory EXPIRED: {key}")
                return None
            
            # LRU：移到末尾
            self.cache.move_to_end(key)
            self.stats.hits += 1
            logger.debug(f"✅ Memory HIT: {key}")
            return self.cache[key]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """存储数据"""
        async with self.lock:
            try:
                self.stats.writes += 1
                
                # 如果已存在，先删除（更新）
                if key in self.cache:
                    self.cache.move_to_end(key)
                else:
                    # 检查容量限制
                    if len(self.cache) >= self.max_size:
                        # 删除最老的条目
                        oldest_key = next(iter(self.cache))
                        await self._delete_key(oldest_key)
                        logger.debug(f"🗑️  LRU evict: {oldest_key}")
                
                # 存储数据
                self.cache[key] = value
                
                # 设置TTL
                if ttl is not None or self.default_ttl > 0:
                    expire_time = time.time() + (ttl or self.default_ttl)
                    self.ttl_map[key] = expire_time
                
                logger.debug(f"💾 Memory SET: {key} (ttl={ttl or self.default_ttl}s)")
                return True
                
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"❌ Memory SET error: {e}")
                return False
    
    async def delete(self, key: str) -> bool:
        """删除数据"""
        async with self.lock:
            return await self._delete_key(key)
    
    async def _delete_key(self, key: str) -> bool:
        """内部删除方法（不加锁）"""
        self.stats.deletes += 1
        if key in self.cache:
            del self.cache[key]
            if key in self.ttl_map:
                del self.ttl_map[key]
            logger.debug(f"🗑️  Memory DELETE: {key}")
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        result = await self.get(key)
        return result is not None
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有键"""
        async with self.lock:
            if pattern == "*":
                return list(self.cache.keys())
            else:
                # 简单通配符匹配
                import fnmatch
                return [k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)]
    
    async def clear(self) -> bool:
        """清空所有数据"""
        async with self.lock:
            self.cache.clear()
            self.ttl_map.clear()
            logger.warning("⚠️  Memory storage cleared")
            return True
    
    async def size(self) -> int:
        """获取存储大小"""
        return len(self.cache)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats.to_dict(),
            "size": len(self.cache),
            "max_size": self.max_size,
            "utilization": round(len(self.cache) / self.max_size * 100, 2)
        }