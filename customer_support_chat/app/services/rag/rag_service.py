# customer_support_chat/app/services/rag/rag_service.py

from typing import Optional, List, Callable, Awaitable
import os
import logging
from pathlib import Path

from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.types import KnowledgeSource
from customer_support_chat.app.services.utils import get_qdrant_client

logger = logging.getLogger(__name__)

# 反思循环开关（通过环境变量控制，不修改 settings.py）
REFLECTION_ENABLED = os.environ.get("RAG_REFLECTION_ENABLED", "true").lower() == "true"
REFLECTION_GRADER_MODEL = os.environ.get("RAG_REFLECTION_MODEL", "gpt-4o")


class RAGService:
    """RAG 服务：统一管理检索器的初始化和使用"""

    _instance: Optional['RAGService'] = None
    _initialized: bool = False

    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化（只执行一次）"""
        if not self._initialized:
            self.retriever: Optional[HybridRetriever] = None
            # 反思循环相关组件（懒加载）
            self._reflection_loop = None
            self._query_enhancer = None
            RAGService._initialized = True

    def initialize(
        self,
        knowledge_base_paths: dict[KnowledgeSource, str],
        enable_chunking: bool = True,
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ):
        """
        初始化 RAG 系统

        Args:
            knowledge_base_paths: 知识源路径映射
                例如: {
                    KnowledgeSource.POLICY_DOCS: "/path/to/policy_docs",
                    KnowledgeSource.PRODUCT_MANUAL: "/path/to/manuals",
                }
            enable_chunking: 是否启用分块
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """

        print("\n" + "="*100)
        print("🚀 初始化 RAG 系统")
        print("="*100)

        # 1. 创建检索器
        client = get_qdrant_client()
        self.retriever = HybridRetriever()

        # 更新分块参数
        if enable_chunking:
            from customer_support_chat.app.services.rag.document_loader import SimpleTextSplitter
            self.retriever.text_splitter = SimpleTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

        # 2. 加载各个知识源
        for source, path in knowledge_base_paths.items():
            if not os.path.exists(path):
                print(f"⚠️ 路径不存在，跳过: {path}")
                continue

            print(f"\n{'='*100}")
            print(f"📚 加载知识源: {source.value}")
            print(f"📂 路径: {path}")
            print(f"{'='*100}")

            try:
                # 判断是文件还是目录
                if os.path.isfile(path):
                    self.retriever.load_documents_from_file(
                        file_path=path,
                        source=source,
                        enable_chunking=enable_chunking
                    )
                elif os.path.isdir(path):
                    self.retriever.load_documents_from_directory(
                        dir_path=path,
                        source=source,
                        enable_chunking=enable_chunking,
                        recursive=True
                    )
            except Exception as e:
                print(f"❌ 加载失败: {e}")
                continue

        print("\n" + "="*100)
        print("✅ RAG 系统初始化完成")
        print(f"🪞 Self-Reflection: {'ENABLED' if REFLECTION_ENABLED else 'DISABLED'} "
              f"(model={REFLECTION_GRADER_MODEL})")
        print("="*100 + "\n")

    async def search(
        self,
        query: str,
        sources: Optional[list[KnowledgeSource]] = None,
        method: str = "hybrid_rerank",
        top_k: int = 5,
        **kwargs
    ):
        """
        检索接口

        Args:
            query: 查询文本
            sources: 知识源列表
            method: 检索方法 (bm25, vector, hybrid, hybrid_rerank)
            top_k: 返回结果数量
            **kwargs: 其他参数 (bm25_weight, vector_weight, rerank等)
        """
        if self.retriever is None:
            raise RuntimeError("RAG 系统未初始化，请先调用 initialize()")

        return await self.retriever.retrieve(
            query=query,
            sources=sources,
            method=method,
            top_k=top_k,
            **kwargs
        )

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self.retriever is not None

    def get_available_sources(self) -> list[KnowledgeSource]:
        """获取已加载的知识源"""
        if self.retriever is None:
            return []
        return list(self.retriever.document_stores.keys())

    # =====================================================================
    # Self-Reflection Loop 集成
    # =====================================================================

    def _get_reflection_loop(self,
                             generate_answer_fn: Optional[Callable[[str, List[str]], Awaitable[str]]] = None):
        """懒加载并构造 SelfReflectionLoop。

        graceful fallback：当 QueryEnhancer 创建失败时，loop 仍可工作（仅丧失 query 改写能力）。
        """
        from customer_support_chat.app.services.rag.llm_grader import (
            HallucinationGrader, RelevanceGrader,
        )
        from customer_support_chat.app.services.rag.reflection_loop import SelfReflectionLoop

        # 懒加载 query enhancer（不可用时 graceful fallback）
        if self._query_enhancer is None:
            try:
                from langchain_openai import ChatOpenAI
                from customer_support_chat.app.services.rag.query_enhancer import QueryEnhancer
                enhancer_llm = ChatOpenAI(model=REFLECTION_GRADER_MODEL, temperature=0)
                self._query_enhancer = QueryEnhancer(enhancer_llm)
            except Exception as e:
                logger.warning(f"QueryEnhancer unavailable, reflection will skip rewriting: {e}")
                self._query_enhancer = None

        # 每次都新建 loop（generate_answer_fn 可能不同）
        return SelfReflectionLoop(
            hallucination_grader=HallucinationGrader(model_name=REFLECTION_GRADER_MODEL),
            relevance_grader=RelevanceGrader(model_name=REFLECTION_GRADER_MODEL),
            query_enhancer=self._query_enhancer,
            retriever=self.retriever,
            generate_answer_fn=generate_answer_fn,
        )

    async def retrieve_with_rewrite(
        self,
        query: str,
        conversation_history: Optional[list] = None,
        sources: Optional[list[KnowledgeSource]] = None,
        method: str = "hybrid_rerank",
        top_k: int = 5,
        **kwargs,
    ) -> dict:
        """带 Query Rewriting 的检索便捷接口。

        安全版 HyDE 策略：原始 query 始终保留，HyDE / query expansion / sub queries
        只作为补充召回信号，不替代用户原始问题。最终重排序仍锚定 original query。

        当 QueryEnhancer 创建/调用失败时，graceful fallback 回原 query。

        Returns:
            {
                "query": <用户原始 query>,
                "original_query": <用户原始 query>,
                "supplementary_queries": <用于补充召回的 query 列表>,
                "retrieval_queries": <实际参与召回的 query 列表>,
                "results": <retriever 返回的结果列表>,
                "enhanced": <QueryEnhancer 返回的完整 Dict 或 None>,
            }
        """
        if self.retriever is None:
            raise RuntimeError("RAG 系统未初始化，请先调用 initialize()")

        enhanced_payload = None
        supplementary_queries: List[str] = []

        # 懒加载 QueryEnhancer（与 _get_reflection_loop 共享同一实例）
        if self._query_enhancer is None:
            try:
                from langchain_openai import ChatOpenAI
                from customer_support_chat.app.services.rag.query_enhancer import QueryEnhancer
                enhancer_llm = ChatOpenAI(model=REFLECTION_GRADER_MODEL, temperature=0)
                self._query_enhancer = QueryEnhancer(enhancer_llm)
            except Exception as e:
                logger.warning(
                    f"retrieve_with_rewrite: QueryEnhancer unavailable, "
                    f"using original query: {e}"
                )
                self._query_enhancer = None

        if self._query_enhancer is not None:
            try:
                enhanced_payload = await self._query_enhancer.enhance_query(
                    query, conversation_history or []
                )
                supplementary_queries = self._extract_supplementary_queries(query, enhanced_payload)
            except Exception as e:
                logger.error(f"retrieve_with_rewrite: enhance_query failed: {e}")
                supplementary_queries = []

        try:
            if supplementary_queries and hasattr(self.retriever, "retrieve_multi_query"):
                results = await self.retriever.retrieve_multi_query(
                    original_query=query,
                    supplementary_queries=supplementary_queries,
                    sources=sources,
                    method=method,
                    top_k=top_k,
                    **kwargs,
                )
            else:
                results = await self.retriever.retrieve(
                    query=query,
                    sources=sources,
                    method=method,
                    top_k=top_k,
                    **kwargs,
                )
        except Exception as e:
            logger.error(f"retrieve_with_rewrite: retrieval failed: {e}")
            results = []

        return {
            "query": query,
            "original_query": query,
            "supplementary_queries": supplementary_queries,
            "retrieval_queries": [query, *supplementary_queries],
            "results": results,
            "enhanced": enhanced_payload,
        }

    def _extract_supplementary_queries(self, original_query: str, enhanced_payload) -> List[str]:
        """从 QueryEnhancer 输出中提取补充召回 query，保留原始 query 作为唯一事实锚点。"""
        if not isinstance(enhanced_payload, dict):
            return []

        candidates: List[str] = []

        hyde = enhanced_payload.get("hypothetical_doc")
        if isinstance(hyde, str) and hyde.strip():
            candidates.append(hyde.strip())

        for key in ("expanded_queries", "sub_queries"):
            values = enhanced_payload.get(key) or []
            if isinstance(values, list):
                candidates.extend(str(v).strip() for v in values if v and str(v).strip())

        # 去重并过滤与原 query 完全相同的项
        result: List[str] = []
        seen = {original_query.strip().lower()}
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)

        return result

    async def search_and_reflect(
        self,
        query: str,
        initial_answer: str,
        documents: Optional[List[str]] = None,
        sources: Optional[list[KnowledgeSource]] = None,
        method: str = "hybrid_rerank",
        top_k: int = 5,
        conversation_history: Optional[list] = None,
        generate_answer_fn: Optional[Callable[[str, List[str]], Awaitable[str]]] = None,
        **kwargs,
    ):
        """检索 + 反思的统一入口。

        - 当 RAG_REFLECTION_ENABLED=false 时，直接返回 initial_answer（旁路反思）。
        - 否则：若未提供 documents，则自动用 query 检索一次得到 documents；
          然后对 (query, documents, initial_answer) 进行幻觉/相关性评估，
          必要时通过 QueryEnhancer 改写 + 重新检索/生成进行重试，
          最终仍不达标则降级到网络搜索。

        Returns:
            ReflectionResult（包含 final_answer / 评分 / 尝试历史 / 是否网搜降级 等）。
        """
        if self.retriever is None:
            raise RuntimeError("RAG 系统未初始化，请先调用 initialize()")

        if not REFLECTION_ENABLED:
            # 旁路：构造一个直通的结果对象（无需评估，直接返回）
            from customer_support_chat.app.services.rag.reflection_loop import (
                ReflectionResult, ReflectionAttempt,
            )
            return ReflectionResult(
                final_answer=initial_answer,
                passed=True,
                hallucination_score=0.0,
                relevance_score=1.0,
                total_attempts=0,
                used_web_search=False,
                total_duration_seconds=0.0,
                attempts_history=[],
            )

        # 自动补齐文档（若调用方未提供）
        if documents is None:
            try:
                results = await self.retriever.retrieve(
                    query=query, sources=sources, method=method, top_k=top_k, **kwargs
                )
                documents = [
                    getattr(r, "content", None) or getattr(r, "page_content", "")
                    for r in (results or [])
                ]
                documents = [d for d in documents if d]
            except Exception as e:
                logger.error(f"search_and_reflect: retrieval failed: {e}")
                documents = []

        loop = self._get_reflection_loop(generate_answer_fn=generate_answer_fn)

        try:
            result = await loop.run(
                query=query,
                documents=documents,
                initial_answer=initial_answer,
                conversation_history=conversation_history,
            )
        except Exception as e:
            logger.error(f"Self-reflection loop failed, falling back to initial answer: {e}")
            from customer_support_chat.app.services.rag.reflection_loop import ReflectionResult
            return ReflectionResult(
                final_answer=initial_answer,
                passed=False,
                hallucination_score=0.5,
                relevance_score=0.5,
                total_attempts=0,
                used_web_search=False,
                total_duration_seconds=0.0,
                attempts_history=[],
            )

        # 反思结果日志
        logger.info(
            "[Reflection] passed=%s attempts=%d web_fallback=%s "
            "hallucination=%.2f relevance=%.2f duration=%.2fs",
            result.passed, result.total_attempts, result.used_web_search,
            result.hallucination_score, result.relevance_score,
            result.total_duration_seconds,
        )
        return result
