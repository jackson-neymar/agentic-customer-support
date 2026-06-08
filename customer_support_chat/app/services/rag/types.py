# customer_support_chat/app/services/rag/types.py

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class KnowledgeSource(Enum):
    """知识源类型"""
    STRUCTURED_DATA = "structured_data"
    POLICY_DOCS = "policy_docs"
    FAQ = "faq"
    PRODUCT_MANUAL = "product_manual"  # ✅ 添加这个
    TRAVEL_GUIDES = "travel_guides"
    USER_REVIEWS = "user_reviews"
    REAL_TIME_NEWS = "real_time_news"


@dataclass
class RetrievalResult:
    """检索结果"""
    content: str                                      # ✅ 必填字段放前面
    source: KnowledgeSource                           # ✅ 必填字段放前面
    score: float = 0.0                                # ✅ 可选字段放后面
    metadata: Dict[str, Any] = field(default_factory=dict)  # ✅ 可选字段放后面
    
    def __post_init__(self):
        """验证数据"""
        if self.score < 0 or self.score > 1:
            raise ValueError("Score must be between 0 and 1")


@dataclass
class EnhancedQuery:
    """增强后的查询"""
    original: str
    hypothetical_doc: str
    sub_queries: List[str] = field(default_factory=list)
    expanded_queries: List[str] = field(default_factory=list)