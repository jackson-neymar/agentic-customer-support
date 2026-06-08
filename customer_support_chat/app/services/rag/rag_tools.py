# customer_support_chat/app/services/rag/rag_tools.py

from typing import List, Optional
from langchain_core.tools import tool
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.types import KnowledgeSource, RetrievalResult

# 全局 RAG 服务实例
rag_service = RAGService()


def format_rag_results(
    results: List[RetrievalResult],
    max_results: int = 3,
    min_score: float = 0.3
) -> str:
    """
    格式化 RAG 检索结果，使其易于 LLM 理解
    
    Args:
        results: 检索结果列表（已按 score 降序排列）
        max_results: 最多返回的结果数
        min_score: 最低相似度分数阈值
    
    Returns:
        格式化后的字符串
    """
    if not results:
        return "ℹ️ No relevant information found in the knowledge base."
    
    # 过滤低分结果并限制数量
    filtered_results = [r for r in results if r.score >= min_score][:max_results]
    
    if not filtered_results:
        return "ℹ️ No highly relevant information found (all results below confidence threshold)."
    
    # 构建格式化输出
    formatted = "📚 **Knowledge Base Results** (sorted by relevance):\n\n"
    
    for i, result in enumerate(filtered_results, 1):
        # 信心等级
        if result.score > 0.7:
            confidence = "🟢 High"
        elif result.score > 0.5:
            confidence = "🟡 Medium"
        else:
            confidence = "🟠 Low"
        
        formatted += f"**Result {i}** [{result.source.value}] {confidence} (Score: {result.score:.1%})\n"
        formatted += f"{result.content}\n\n"
        formatted += "---\n"
    
    formatted += "\n💡 **Instructions:** Use the above information to answer the user's question. "
    formatted += "Prioritize higher-scored results. If the information is insufficient, supplement with your general knowledge.\n"
    
    return formatted


@tool
async def search_knowledge_base(query: str) -> str:
    """
    Search the comprehensive company knowledge base for relevant information.
    
    This tool searches across ALL knowledge sources (policies, FAQs, manuals, guides)
    and returns the most relevant documents sorted by relevance score.
    
    Use this tool when:
    - User asks about company policies (cancellation, refund, check-in rules, etc.)
    - User has questions about services (hotel amenities, flight changes, car insurance, etc.)
    - User needs recommendations or guidance
    - You need to verify information before providing an answer
    
    Args:
        query: The search query in natural language
               Examples:
               - "What is the hotel cancellation policy?"
               - "Can I change my flight?"
               - "What car insurance options are available?"
               - "Best hotels for families in Beijing"
    
    Returns:
        Formatted search results with the most relevant documents (top 3-5)
        Each result includes:
        - Source type (policy_docs, faq, product_manual, etc.)
        - Relevance score (High/Medium/Low)
        - Content snippet
    
    Important:
        - ALWAYS use this tool before saying "I don't know"
        - If first search returns no results, try rephrasing the query
        - Results are automatically sorted by relevance (highest score first)
    """
    
    # 检查 RAG 服务是否可用
    if not rag_service.is_initialized():
        return "⚠️ Knowledge base is currently unavailable. Please try again later or contact support."
    
    try:
        # 调用 RAG 服务搜索
        results = await rag_service.search(
            query=query,
            sources=None,  # 搜索所有知识源
            method="hybrid_rerank",  # 使用最佳检索方法
            top_k=5  # 获取 top 5 结果
        )
        
        # 格式化结果
        return format_rag_results(
            results,
            max_results=3,  # 只返回前 3 个给 LLM
            min_score=0.3   # 过滤掉相关性太低的结果
        )
    
    except Exception as e:
        return f"⚠️ Error searching knowledge base: {str(e)}\nPlease try rephrasing your query or contact support."


# 导出工具列表
RAG_TOOLS = [search_knowledge_base]