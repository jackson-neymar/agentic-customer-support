"""RAG service package: retrieval, query enhancement, and self-reflection."""

from customer_support_chat.app.services.rag.types import (
    KnowledgeSource,
    RetrievalResult,
    EnhancedQuery,
)
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.query_enhancer import QueryEnhancer

# Self-reflection pipeline (Task #14)
from customer_support_chat.app.services.rag.llm_grader import (
    HallucinationGrader,
    RelevanceGrader,
    HallucinationScore,
    RelevanceScore,
)
from customer_support_chat.app.services.rag.reflection_loop import (
    SelfReflectionLoop,
    ReflectionResult,
    ReflectionAttempt,
)

__all__ = [
    # types
    "KnowledgeSource",
    "RetrievalResult",
    "EnhancedQuery",
    # core
    "RAGService",
    "HybridRetriever",
    "QueryEnhancer",
    # graders
    "HallucinationGrader",
    "RelevanceGrader",
    "HallucinationScore",
    "RelevanceScore",
    # reflection
    "SelfReflectionLoop",
    "ReflectionResult",
    "ReflectionAttempt",
]
