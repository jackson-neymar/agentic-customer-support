"""
存储管理器 - 统一接口
对外提供单一访问入口
"""
from typing import Any, Optional, Dict
from app.core.storage.hybrid_store import HybridStorage
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """全局存储管理器（单例）"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # 初始化混合存储
            self.storage = HybridStorage(
                enable_memory=True,
                enable_file=True,
                enable_db=False,
                memory_max_size=1000,
                file_base_path="./data/hybrid_storage"
            )
            self._initialized = True
            logger.info("✅ StorageManager initialized")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        return await self.storage.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """存储数据"""
        return await self.storage.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除数据"""
        return await self.storage.delete(key)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return await self.storage.get_all_stats()


# 全局单例
storage_manager = StorageManager()