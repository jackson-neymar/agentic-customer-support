# customer_support_chat/app/services/rag/enhanced_lookup.py

from typing import List, Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.citation_tracker import CitationTracker
from customer_support_chat.app.services.rag.types import KnowledgeSource

# 初始化组件
try:
    llm = ChatOpenAI(model="gpt-4")
    hybrid_retriever = HybridRetriever()
    citation_tracker = CitationTracker()
    HAS_DEPENDENCIES = True
except Exception as e:
    print(f"Error initializing RAG components: {e}")
    HAS_DEPENDENCIES = False

@tool
async def lookup_policy_enhanced(
    query: str, 
    config: Optional[RunnableConfig] = None
) -> str:
    """
    增强版政策查询工具：
    - 混合检索（向量+关键词）
    - 重排序
    - 引用溯源
    
    Args:
        query: 用户查询
        config: 运行配置
    
    Returns:
        带引用的答案
    """
    
    if not HAS_DEPENDENCIES:
        return "Error: RAG dependencies not properly initialized"
    
    # 1. 混合检索
    results = await hybrid_retriever.retrieve(
        query=query,
        sources=[KnowledgeSource.POLICY_DOCS, KnowledgeSource.FAQ],
        top_k=5
    )
    
    if not results:
        return "抱歉，未找到相关政策信息。"
    
    # 2. 生成答案
    context = "\n\n".join([r.content for r in results])
    
    prompt = f"""请基于以下政策文档回答用户问题。

用户问题：{query}

相关文档：
{context}

请给出简洁、准确的回答："""
    
    answer = await llm.ainvoke(prompt)
    
    # 3. 添加引用
    answer_with_citations = citation_tracker.format_answer_with_citations(
        answer.content,
        results
    )
    
    return answer_with_citations

@tool
async def search_travel_guides(
    destination: str,
    interests: Optional[List[str]] = None,
    config: Optional[RunnableConfig] = None
) -> str:
    """
    搜索旅游攻略
    
    Args:
        destination: 目的地
        interests: 兴趣点列表
        config: 运行配置
    
    Returns:
        个性化旅游推荐
    """
    
    if not HAS_DEPENDENCIES:
        return "Error: RAG dependencies not properly initialized"
    
    query = f"{destination} 旅游攻略"
    if interests:
        query += f"，重点关注：{', '.join(interests)}"
    
    results = await hybrid_retriever.retrieve(
        query=query,
        sources=[KnowledgeSource.TRAVEL_GUIDES, KnowledgeSource.USER_REVIEWS],
        top_k=3
    )
    
    if not results:
        return f"抱歉，暂无{destination}的旅游攻略。"
    
    # 生成个性化推荐
    context = "\n\n".join([r.content for r in results])
    
    interests_str = "、".join(interests) if interests else "常规观光"
    
    prompt = f"""请为 {destination} 生成个性化旅游推荐。

可用信息：
{context}

用户兴趣：{interests_str}

请给出具体、有帮助的推荐："""
    
    recommendation = await llm.ainvoke(prompt)
    
    return citation_tracker.format_answer_with_citations(
        recommendation.content,
        results
    )