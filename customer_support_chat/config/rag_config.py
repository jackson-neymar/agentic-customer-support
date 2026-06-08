# customer_support_chat/config/rag_config.py

from pathlib import Path
from customer_support_chat.app.services.rag.types import KnowledgeSource

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 知识库根目录
KNOWLEDGE_BASE_ROOT = PROJECT_ROOT / "knowledge_base"

# 知识库路径配置 ✅ 确保使用正确的枚举值
KNOWLEDGE_BASE_PATHS = {
    KnowledgeSource.POLICY_DOCS: str(KNOWLEDGE_BASE_ROOT / "hotel_policies"),
    KnowledgeSource.FAQ: str(KNOWLEDGE_BASE_ROOT / "hotel_faq"),
    KnowledgeSource.PRODUCT_MANUAL: str(KNOWLEDGE_BASE_ROOT / "hotel_guides"),  # ✅ 使用 PRODUCT_MANUAL
}

# RAG 参数配置
RAG_CONFIG = {
    "enable_chunking": True,
    "chunk_size": 500,
    "chunk_overlap": 100,
    "default_method": "hybrid_rerank",
    "default_top_k": 5,
}

# 是否在启动时初始化 RAG
INIT_RAG_ON_STARTUP = True

# 如果知识库不存在是否继续运行
CONTINUE_WITHOUT_RAG = True