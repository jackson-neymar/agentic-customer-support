"""
文件存储层 - L2缓存
特点：持久化、容量较大、速度中等
"""
import os
import json
import pickle
import asyncio
import aiofiles
from pathlib import Path
from typing import Any, Optional, Dict, List
from .base import BaseStorage, StorageStats
import logging

logger = logging.getLogger(__name__)


class FileStorage(BaseStorage):
    """
    文件系统存储实现
    """
    
    def __init__(self, base_path: str = "./data/storage", use_pickle: bool = False):
        """
        初始化文件存储
        
        Args:
            base_path: 存储根目录
            use_pickle: 是否使用pickle（支持复杂对象）
        """
        self.base_path = Path(base_path)
        self.use_pickle = use_pickle
        self.stats = StorageStats()
        self.lock = asyncio.Lock()
        
        # 创建存储目录
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ FileStorage initialized at {self.base_path}")
    
    def _get_file_path(self, key: str) -> Path:
        """获取键对应的文件路径"""
        # 使用哈希避免文件名冲突
        import hashlib
        hashed = hashlib.md5(key.encode()).hexdigest()
        ext = ".pkl" if self.use_pickle else ".json"
        return self.base_path / f"{hashed}{ext}"
    
    async def get(self, key: str) -> Optional[Any]:
        """读取数据"""
        async with self.lock:
            self.stats.reads += 1
            file_path = self._get_file_path(key)
            
            try:
                if not file_path.exists():
                    self.stats.misses += 1
                    logger.debug(f"🔍 File MISS: {key}")
                    return None
                
                # 读取文件
                async with aiofiles.open(file_path, 'rb' if self.use_pickle else 'r') as f:
                    content = await f.read()
                
                # 反序列化
                if self.use_pickle:
                    data = pickle.loads(content)
                else:
                    data = json.loads(content)
                
                self.stats.hits += 1
                logger.debug(f"✅ File HIT: {key}")
                return data
                
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"❌ File GET error: {e}")
                return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """存储数据"""
        async with self.lock:
            self.stats.writes += 1
            file_path = self._get_file_path(key)
            
            try:
                # 序列化
                if self.use_pickle:
                    content = pickle.dumps(value)
                    mode = 'wb'
                else:
                    content = json.dumps(value, ensure_ascii=False, indent=2)
                    mode = 'w'
                
                # 写入文件
                async with aiofiles.open(file_path, mode) as f:
                    await f.write(content)
                
                logger.debug(f"💾 File SET: {key}")
                return True
                
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"❌ File SET error: {e}")
                return False
    
    async def delete(self, key: str) -> bool:
        """删除数据"""
        async with self.lock:
            self.stats.deletes += 1
            file_path = self._get_file_path(key)
            
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"🗑️  File DELETE: {key}")
                    return True
                return False
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"❌ File DELETE error: {e}")
                return False
    
    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        file_path = self._get_file_path(key)
        return file_path.exists()
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有键（注意：需要反向映射）"""
        # 警告：文件存储难以反向查找键名
        logger.warning("⚠️  FileStorage.keys() is inefficient")
        return []
    
    async def clear(self) -> bool:
        """清空所有文件"""
        async with self.lock:
            try:
                for file in self.base_path.glob("*"):
                    if file.is_file():
                        file.unlink()
                logger.warning("⚠️  File storage cleared")
                return True
            except Exception as e:
                logger.error(f"❌ File CLEAR error: {e}")
                return False
    
    async def size(self) -> int:
        """获取文件数量"""
        return len(list(self.base_path.glob("*")))
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_size = sum(f.stat().st_size for f in self.base_path.glob("*") if f.is_file())
        return {
            **self.stats.to_dict(),
            "size": await self.size(),
            "total_bytes": total_size,
            "total_mb": round(total_size / 1024 / 1024, 2)
        }