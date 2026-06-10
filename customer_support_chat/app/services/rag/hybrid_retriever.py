# customer_support_chat/app/services/rag/hybrid_retriever.py

from typing import List, Dict, Any, Optional
import asyncio
import numpy as np
import re
from customer_support_chat.app.services.utils import get_qdrant_client
from customer_support_chat.app.services.rag.types import KnowledgeSource, RetrievalResult
from .document_loader import DocumentLoaderFactory, LoadedDocument, SimpleTextSplitter 
from langchain_core.documents import Document
# =====================================
# 依赖检查
# =====================================

try:
    from langchain_community.vectorstores import Qdrant
    
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    print("⚠️ Qdrant not installed. Vector search disabled.")

try:
    from sentence_transformers import CrossEncoder
    HAS_RERANKER = True
except ImportError:
    HAS_RERANKER = False
    print("⚠️ sentence-transformers not installed. Reranking disabled.")

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    print("⚠️ rank-bm25 not installed. BM25 search disabled.")

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    print("⚠️ jieba not installed. Chinese tokenization will use simple method.")

from langchain_openai import OpenAIEmbeddings
from vectorizer.app.core.settings import get_settings
from vectorizer.app.core.logger import logger
from typing import Union, List
from qdrant_client.models import VectorParams, Distance


class HybridRetriever:
    """
    混合检索器：支持多种检索策略
    - BM25: 关键词检索
    - Vector: 语义检索
    - Hybrid: 混合检索 (BM25 + Vector + 加权融合)
    - Hybrid+Rerank: 混合检索 + 重排序
    """
    
    def __init__(self, qdrant_client: Optional[Any] = None):
        # Qdrant 客户端
        if HAS_QDRANT:
            qdrant_client = get_qdrant_client()
            self.qdrant_client = qdrant_client 
        else:
            self.qdrant_client = None
        
        # 向量存储
        self.vector_retrievers: Dict[KnowledgeSource, Any] = {}
        
        # BM25 检索器
        self.bm25_retrievers: Dict[KnowledgeSource, tuple] = {}
        
        # 文档存储
        self.document_stores: Dict[KnowledgeSource, List[RetrievalResult]] = {}
        
        # 文本分块器
        self.text_splitter = SimpleTextSplitter(chunk_size=500, chunk_overlap=100)
        
        # 重排序模型
        if HAS_RERANKER:
            try:
                self.reranker = CrossEncoder(
                    '/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/ms-marco-MiniLM-L-6-v2'
                )
                print("✅ Reranker loaded successfully")
            except Exception as e:
                print(f"⚠️ Failed to load reranker: {e}")
                self.reranker = None
        else:
            self.reranker = None
    
    # =====================================
    # 分词方法
    # =====================================
    
    def tokenize(self, text: str) -> List[str]:
        """
        智能分词：支持中文和英文
        """
        if HAS_JIEBA:
            # 使用 jieba 分词（中文友好）
            tokens = jieba.lcut(text.lower())
            
            # 过滤停用词
            stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', 
                        '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', 
                        '你', '会', '着', '没有', '看', '好', '自己', '这', 'the', 'a', 
                        'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were'}
            
            tokens = [t for t in tokens if t not in stopwords and len(t) > 1]
        else:
            # 简单分词（fallback）
            tokens = re.findall(r'\w+', text.lower())
        
        return tokens
    
    # =====================================
    # 文档加载
    # =====================================
    
    def load_documents_from_file(
        self, 
        file_path: str, 
        source: KnowledgeSource,
        enable_chunking: bool = True
    ):
        """从文件加载文档"""
        print(f"\n📂 正在加载文件: {file_path}")
        
        # 1. 加载文档
        loaded_docs = DocumentLoaderFactory.load_document(file_path)
        print(f"✅ 加载完成: {len(loaded_docs)} 个文档片段")
        
        # 2. 分块
        if enable_chunking:
            loaded_docs = self.text_splitter.split_documents(loaded_docs)
            print(f"✅ 分块完成: {len(loaded_docs)} 个文档块")
        
        # 3. 转换并添加
        retrieval_docs = self._convert_to_retrieval_results(loaded_docs, source)
        self.add_documents(source, retrieval_docs)
        print(f"✅ 已添加到 {source.value} 检索器\n")
    
    def load_documents_from_directory(
        self, 
        dir_path: str, 
        source: KnowledgeSource,
        enable_chunking: bool = True,
        recursive: bool = True
    ):
        """从目录批量加载文档"""
        print(f"\n📂 正在加载目录: {dir_path}")
        
        # 1. 加载目录
        loaded_docs = DocumentLoaderFactory.load_directory(
            dir_path, 
            recursive=recursive,
            verbose=True
        )
        print(f"\n✅ 共加载 {len(loaded_docs)} 个文档片段")
        
        # 2. 分块
        if enable_chunking:
            loaded_docs = self.text_splitter.split_documents(loaded_docs)
            print(f"✅ 分块完成: {len(loaded_docs)} 个文档块")
        
        # 3. 转换并添加
        retrieval_docs = self._convert_to_retrieval_results(loaded_docs, source)
        self.add_documents(source, retrieval_docs)
        print(f"✅ 已添加到 {source.value} 检索器\n")
    
    def _convert_to_retrieval_results(
        self, 
        loaded_docs: List[LoadedDocument], 
        source: KnowledgeSource
    ) -> List[RetrievalResult]:
        """将 LoadedDocument 转换为 RetrievalResult"""
        return [
            RetrievalResult(
                content=doc.content,
                source=source,
                metadata=doc.metadata,
                score=0.0
            )
            for doc in loaded_docs
        ]
    
    # =====================================
    # 添加文档（构建索引）
    # =====================================
    
    def add_documents(self, source: KnowledgeSource, documents: List[RetrievalResult]):
        """
        添加文档并构建索引
        1. 构建 BM25 索引
        2. 构建向量索引（如果可用）
        """
        if not documents:
            print(f"⚠️ No documents to add for {source.value}")
            return
        
        print(f"\n🔨 正在为 {source.value} 构建索引...")
        
        # 存储文档
        self.document_stores[source] = documents
        
        # 1. 构建 BM25 索引
        if HAS_BM25:
            print("   ├─ 构建 BM25 索引（关键词检索）")
            tokenized_docs = [self.tokenize(doc.content) for doc in documents]
            bm25 = BM25Okapi(tokenized_docs)
            self.bm25_retrievers[source] = (bm25, documents)
            print(f"   ├─ ✅ BM25 索引完成: {len(documents)} 个文档")
        
        # 2. 构建向量索引（如果 Qdrant 可用）
        if HAS_QDRANT and self.qdrant_client:
            try:
                collection_name = f"{source.value}_collection"
                vector_store = self._init_vector_store(collection_name, documents)
                if vector_store:
                    self.vector_retrievers[source] = vector_store
                    print(f"   └─ ✅ 向量索引完成")
            except Exception as e:
                print(f"   └─ ⚠️ 向量索引失败: {e}")
        
        print(f"✅ 索引构建完成\n")
    
    def _init_vector_store(self, collection_name: str, documents: List[RetrievalResult]) -> Optional[Any]:
        """初始化向量数据库"""
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_core.documents import Document
            
            # 转换为 LangChain Document
            langchain_docs = []
            for d in documents:
                text = d.content  # 或你实际字段
                if text is None or not str(text).strip():
                    continue
                langchain_docs.append(Document(page_content=str(text), metadata=d.metadata or {}))
                
            settings = get_settings()
            base_url = settings.EMBEDDING_BASE_URL
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]  # Remove /v1 from the end
            embedding_url = f"{base_url}/v1"
            # Configure OpenAI embeddings with embedding-specific configuration
            if settings.EMBEDDING_BASE_URL:
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    openai_api_key=settings.EMBEDDING_API_KEY,
                    openai_api_base=embedding_url
                )
            # 创建向量存储
            def ensure_collection(client, name: str, size: int):
                existing = {c.name for c in client.get_collections().collections}
                if name not in existing:
                    client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(size=size, distance=Distance.COSINE),
                    )

            # 1) 先确保 collection 存在
            ensure_collection(self.qdrant_client, collection_name, size=1536)

            vector_store = Qdrant(
                client=self.qdrant_client,
                collection_name=collection_name,
                embeddings=embeddings,   # 注意这里是 embeddings（复数）
            )

            vector_store.add_documents(langchain_docs)
            return vector_store
            
            
            
        except Exception as e:
            print(f"⚠️ Vector store initialization failed: {e}")
            return None
    
    # =====================================
    # 🆕 统一检索接口
    # =====================================
    
    async def retrieve(
        self, 
        query: str, 
        sources: Optional[List[KnowledgeSource]] = None,
        method: str = "hybrid",  # 🆕 "bm25", "vector", "hybrid", "hybrid_rerank"
        top_k: int = 5,
        bm25_weight: float = 0.5,  # 🆕 BM25权重（hybrid模式）
        vector_weight: float = 0.5,  # 🆕 向量权重（hybrid模式）
        rerank: bool = False  # 🆕 是否启用重排序
    ) -> List[RetrievalResult]:
        """
        统一检索接口
        
        Args:
            query: 查询文本
            sources: 知识源列表，None表示全部
            method: 检索方法
                - "bm25": 仅BM25关键词检索
                - "vector": 仅向量语义检索
                - "hybrid": BM25 + Vector + 加权融合
                - "hybrid_rerank": hybrid + 重排序
            top_k: 返回结果数量
            bm25_weight: BM25权重（hybrid模式）
            vector_weight: 向量权重（hybrid模式）
            rerank: 是否启用重排序（对所有方法生效）
        """
        
        if sources is None:
            sources = list(self.document_stores.keys())
        
        # 根据method调用不同的检索策略
        if method == "bm25":
            results = await self._retrieve_bm25_only(query, sources, top_k * 2)
        
        elif method == "vector":
            results = await self._retrieve_vector_only(query, sources, top_k * 2)
        
        elif method == "hybrid":
            results = await self._retrieve_hybrid(
                query, sources, top_k * 2, 
                bm25_weight, vector_weight
            )
        
        elif method == "hybrid_rerank":
            # hybrid_rerank 强制启用重排序
            results = await self._retrieve_hybrid(
                query, sources, top_k * 2, 
                bm25_weight, vector_weight
            )
            rerank = True  # 强制重排序
        
        else:
            raise ValueError(
                f"Unknown method: {method}. "
                f"Choose from: bm25, vector, hybrid, hybrid_rerank"
            )
        
        # 去重
        unique_results = self._deduplicate(results)
        
        # 重排序（如果启用）
        if rerank and len(unique_results) > top_k and self.reranker is not None:
            unique_results = self._rerank(query, unique_results, top_k)
        else:
            # 按分数排序
            unique_results.sort(key=lambda r: r.score, reverse=True)
        
        return unique_results[:top_k]

    async def retrieve_multi_query(
        self,
        original_query: str,
        supplementary_queries: Optional[List[str]] = None,
        sources: Optional[List[KnowledgeSource]] = None,
        method: str = "hybrid_rerank",
        top_k: int = 5,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        rerank: bool = False
    ) -> List[RetrievalResult]:
        """
        多查询补充召回：始终保留原始 query，HyDE / query expansion 只作为补充召回信号。

        关键约束：
        - 召回阶段可以使用 supplementary_queries 扩大候选集
        - 最终 Cross-Encoder 重排序必须使用 original_query，避免被 HyDE 假设内容带偏
        """
        supplementary_queries = supplementary_queries or []

        # 去重并保序：原始 query 永远排第一
        queries: List[str] = []
        seen = set()
        for q in [original_query, *supplementary_queries]:
            if not q or not str(q).strip():
                continue
            normalized = str(q).strip()
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(normalized)

        if not queries:
            return []

        # hybrid_rerank 在单 query retrieve() 内会强制用传入 query rerank。
        # 多 query 场景下先用 hybrid 召回，最后统一用 original_query rerank。
        recall_method = "hybrid" if method == "hybrid_rerank" else method
        should_rerank = rerank or method == "hybrid_rerank"
        recall_k = max(top_k * 2, top_k)

        all_results: List[RetrievalResult] = []
        for query in queries:
            try:
                query_results = await self.retrieve(
                    query=query,
                    sources=sources,
                    method=recall_method,
                    top_k=recall_k,
                    bm25_weight=bm25_weight,
                    vector_weight=vector_weight,
                    rerank=False,
                )
                all_results.extend(query_results)
            except Exception as e:
                print(f"⚠️ Multi-query retrieval error for query '{query[:50]}': {e}")

        # 同一内容可能被原始 query / HyDE / expansion 多次召回；保留最高分，避免分数累加超过 1
        content_to_best: Dict[str, RetrievalResult] = {}
        for result in all_results:
            existing = content_to_best.get(result.content)
            if existing is None or result.score > existing.score:
                content_to_best[result.content] = result

        unique_results = list(content_to_best.values())

        if should_rerank and len(unique_results) > top_k and self.reranker is not None:
            return self._rerank(original_query, unique_results, top_k)

        unique_results.sort(key=lambda r: r.score, reverse=True)
        return unique_results[:top_k]

    # =====================================
    # 🆕 BM25 单独检索
    # =====================================
    
    async def _retrieve_bm25_only(
        self, 
        query: str, 
        sources: List[KnowledgeSource],
        k: int
    ) -> List[RetrievalResult]:
        """仅使用BM25检索"""
        
        # 并行查询多个源
        tasks = [
            self._bm25_search(query, source, k)
            for source in sources
        ]
        results_per_source = await asyncio.gather(*tasks)
        
        # 合并结果
        all_results = []
        for results in results_per_source:
            all_results.extend(results)
        
        return all_results
    
    # =====================================
    # 🆕 向量单独检索
    # =====================================
    
    async def _retrieve_vector_only(
        self, 
        query: str, 
        sources: List[KnowledgeSource],
        k: int
    ) -> List[RetrievalResult]:
        """仅使用向量检索"""
        
        # 并行查询多个源
        tasks = [
            self._vector_search(query, source, k)
            for source in sources
        ]
        results_per_source = await asyncio.gather(*tasks)
        
        # 合并结果
        all_results = []
        for results in results_per_source:
            all_results.extend(results)
        
        return all_results
    
    # =====================================
    # 🆕 混合检索
    # =====================================
    
    async def _retrieve_hybrid(
        self, 
        query: str, 
        sources: List[KnowledgeSource],
        k: int,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5
    ) -> List[RetrievalResult]:
        """
        混合检索：BM25 + Vector + 加权融合
        """
        
        # 并行查询多个源
        tasks = [
            self._retrieve_from_source_hybrid(query, source, k, bm25_weight, vector_weight)
            for source in sources
        ]
        results_per_source = await asyncio.gather(*tasks)
        
        # 合并结果
        all_results = []
        for results in results_per_source:
            all_results.extend(results)
        
        return all_results
    
    async def _retrieve_from_source_hybrid(
        self, 
        query: str, 
        source: KnowledgeSource, 
        k: int,
        bm25_weight: float,
        vector_weight: float
    ) -> List[RetrievalResult]:
        """从单个知识源进行混合检索"""
        
        # BM25 检索
        bm25_results = await self._bm25_search(query, source, k)
        
        # 向量检索
        vector_results = await self._vector_search(query, source, k)
        
        # 加权融合
        merged = self._weighted_fusion(
            bm25_results, 
            vector_results,
            bm25_weight,
            vector_weight
        )
        
        return merged
    
    # =====================================
    # 🆕 加权融合
    # =====================================
    
    def _weighted_fusion(
        self,
        bm25_results: List[RetrievalResult],
        vector_results: List[RetrievalResult],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5
    ) -> List[RetrievalResult]:
        """
        加权融合：bm25_score * w1 + vector_score * w2
        """
        
        # 归一化权重
        total_weight = bm25_weight + vector_weight
        if total_weight > 0:
            bm25_weight = bm25_weight / total_weight
            vector_weight = vector_weight / total_weight
        
        # 使用内容作为唯一标识
        fusion_scores: Dict[str, float] = {}
        content_to_result: Dict[str, RetrievalResult] = {}
        
        # 计算BM25加权分数
        for result in bm25_results:
            content = result.content
            fusion_scores[content] = fusion_scores.get(content, 0) + result.score * bm25_weight
            content_to_result[content] = result
        
        # 计算向量加权分数
        for result in vector_results:
            content = result.content
            fusion_scores[content] = fusion_scores.get(content, 0) + result.score * vector_weight
            if content not in content_to_result:
                content_to_result[content] = result
        
        # 按融合分数排序
        sorted_contents = sorted(
            fusion_scores.keys(),
            key=lambda c: fusion_scores[c],
            reverse=True
        )
        
        # 构建结果列表
        merged_results = []
        for content in sorted_contents:
            result = content_to_result[content]
            result.score = fusion_scores[content]
            merged_results.append(result)
        
        return merged_results
    
    # =====================================
    # 工具方法
    # =====================================
    
    def _deduplicate(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """去重（基于内容）"""
        seen_contents = set()
        unique_results = []
        
        for result in results:
            if result.content not in seen_contents:
                seen_contents.add(result.content)
                unique_results.append(result)
        
        return unique_results
    
    # =====================================
    # BM25 检索
    # =====================================
    
    async def _bm25_search(
        self, 
        query: str, 
        source: KnowledgeSource, 
        k: int
    ) -> List[RetrievalResult]:
        """BM25 关键词检索"""
        if source not in self.bm25_retrievers or not HAS_BM25:
            return []
        
        try:
            bm25, documents = self.bm25_retrievers[source]
            
            # 查询分词
            tokenized_query = self.tokenize(query)
            
            # 计算 BM25 分数
            raw_scores = bm25.get_scores(tokenized_query)
            
            # 归一化分数
            normalized_scores = self._normalize_scores(raw_scores)
            
            # 获取 top-k
            top_indices = np.argsort(normalized_scores)[::-1][:k]
            
            # 构建结果
            results = []
            for idx in top_indices:
                doc = documents[idx]
                results.append(RetrievalResult(
                    content=doc.content,
                    source=doc.source,
                    metadata=doc.metadata,
                    score=float(normalized_scores[idx])
                ))
            
            return results
            
        except Exception as e:
            print(f"⚠️ BM25 search error for {source.value}: {e}")
            return []
    
    def _normalize_scores(self, scores) -> np.ndarray:
        """Min-Max 归一化到 [0, 1]"""
        scores = np.array(scores)
        
        if len(scores) == 0:
            return scores
        
        min_score = scores.min()
        max_score = scores.max()
        
        # 避免除以零
        if max_score - min_score < 1e-10:
            return np.ones_like(scores) * 0.5
        
        # Min-Max 归一化
        normalized = (scores - min_score) / (max_score - min_score)
        return normalized
    
    # =====================================
    # 🆕 向量检索（带分数）
    # =====================================
    
    async def _vector_search(
        self, 
        query: str, 
        source: KnowledgeSource, 
        k: int
    ) -> List[RetrievalResult]:
        """向量语义检索（带相似度分数）"""
        if source not in self.vector_retrievers:
            return []
        
        try:
            vector_store = self.vector_retrievers[source]
            
            # 使用 similarity_search_with_score 获取分数
            docs_with_scores = await vector_store.asimilarity_search_with_score(query, k=k)
            
            results = []
            for doc, score in docs_with_scores:
                # Qdrant 返回的是距离，需要转换为相似度
                # 距离越小越相似，这里用简单的转换
                similarity_score = 1 / (1 + score)
                
                results.append(RetrievalResult(
                    content=doc.page_content,
                    source=source,
                    metadata=doc.metadata,
                    score=similarity_score
                ))
            
            return results
            
        except Exception as e:
            print(f"⚠️ Vector search error for {source.value}: {e}")
            # Fallback: 不带分数的检索
            try:
                vector_store = self.vector_retrievers[source]
                docs = await vector_store.asimilarity_search(query, k=k)
                
                results = [
                    RetrievalResult(
                        content=doc.page_content,
                        source=source,
                        metadata=doc.metadata,
                        score=0.8  # 默认分数
                    )
                    for doc in docs
                ]
                return results
            except:
                return []
    
    # =====================================
    # 重排序
    # =====================================
    
    def _rerank(
        self, 
        query: str, 
        results: List[RetrievalResult], 
        top_k: int
    ) -> List[RetrievalResult]:
        """使用 Cross-Encoder 重排序"""
        if self.reranker is None or not results:
            return results
        
        try:
            # 准备 query-document 对
            pairs = [[query, r.content] for r in results]
            
            # 计算相关性分数
            scores = self.reranker.predict(pairs)
            
            # 更新分数
            for result, score in zip(results, scores):
                result.score = float(score)
            
            # 按分数排序
            sorted_results = sorted(
                results,
                key=lambda r: r.score,
                reverse=True
            )
            
            return sorted_results[:top_k]
            
        except Exception as e:
            print(f"⚠️ Reranking error: {e}")
            return results[:top_k]