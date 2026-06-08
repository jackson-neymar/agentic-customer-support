"""
存储抽象基类
定义统一的存储接口
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
import asyncio


class BaseStorage(ABC):
    """存储层抽象基类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """存储数据"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除数据"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass
    
    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取所有键"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """清空所有数据"""
        pass
    
    @abstractmethod
    async def size(self) -> int:
        """获取存储大小"""
        pass


class StorageStats:
    """存储统计信息"""
    def __init__(self):
        self.hits = 0           # 命中次数
        self.misses = 0         # 未命中次数
        self.reads = 0          # 读取次数
        self.writes = 0         # 写入次数
        self.deletes = 0        # 删除次数
        self.errors = 0         # 错误次数
    
    @property
    def hit_rate(self) -> float:
        """计算命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "reads": self.reads,
            "writes": self.writes,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate * 100, 2)
        }