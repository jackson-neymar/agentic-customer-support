# customer_support_chat/app/services/rag/hotel_rag_tools.py

"""
酒店相关的 RAG 检索工具
"""

from typing import Optional, List
from langchain_core.tools import tool
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.types import KnowledgeSource

@tool
async def search_hotel_policies(query: str, top_k: int = 3) -> str:
    """
    搜索酒店政策文档（退款、取消、入住规则等）
    
    Args:
        query: 查询问题，例如 "酒店取消政策是什么", "可以退款吗"
        top_k: 返回结果数量，默认3条
        
    Returns:
        相关政策信息的文本
        
    Examples:
        - "酒店的取消政策是什么？"
        - "入住时需要带什么证件？"
        - "可以提前多久取消预订？"
    """
    try:
        rag_service = RAGService()
        
        if not rag_service.is_initialized():
            return "❌ 知识库系统未初始化，无法查询政策信息。"
        
        # 只搜索政策文档
        results = await rag_service.search(
            query=query,
            sources=[KnowledgeSource.POLICY_DOCS],
            method="hybrid_rerank",
            top_k=top_k
        )
        
        if not results:
            return "未找到相关的酒店政策信息。建议联系客服获取最新政策。"
        
        # 格式化结果
        response_parts = ["📋 根据公司政策文档，相关信息如下：\n"]
        
        for i, result in enumerate(results, 1):
            response_parts.append(f"\n【信息 {i}】（相关度: {result.score:.2f}）")
            response_parts.append(f"{result.content}")
            
            # 添加来源信息
            if result.metadata.get('filename'):
                response_parts.append(f"📄 来源: {result.metadata['filename']}")
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"❌ 查询政策信息时出错: {str(e)}"


@tool
async def search_hotel_faqs(query: str, top_k: int = 3) -> str:
    """
    搜索酒店常见问题（FAQ）
    
    Args:
        query: 查询问题，例如 "酒店有wifi吗", "可以带宠物吗"
        top_k: 返回结果数量，默认3条
        
    Returns:
        相关FAQ的文本
        
    Examples:
        - "酒店提供早餐吗？"
        - "可以带宠物入住吗？"
        - "房间有吹风机吗？"
    """
    try:
        rag_service = RAGService()
        
        if not rag_service.is_initialized():
            return "❌ 知识库系统未初始化，无法查询FAQ。"
        
        # 只搜索FAQ
        results = await rag_service.search(
            query=query,
            sources=[KnowledgeSource.FAQ],
            method="hybrid_rerank",
            top_k=top_k
        )
        
        if not results:
            return "未找到相关的常见问题解答。如有疑问请联系客服。"
        
        # 格式化结果
        response_parts = ["💡 常见问题解答：\n"]
        
        for i, result in enumerate(results, 1):
            response_parts.append(f"\n【Q&A {i}】")
            response_parts.append(f"{result.content}")
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"❌ 查询FAQ时出错: {str(e)}"


@tool
async def search_hotel_knowledge(query: str, top_k: int = 5) -> str:
    """
    搜索所有酒店相关知识（政策、FAQ、指南等综合搜索）
    
    Args:
        query: 查询问题
        top_k: 返回结果数量，默认5条
        
    Returns:
        相关知识的综合文本
        
    Examples:
        - "酒店的所有规定"
        - "入住和退房须知"
        - "酒店服务和设施"
    """
    try:
        rag_service = RAGService()
        
        if not rag_service.is_initialized():
            return "❌ 知识库系统未初始化。"
        
        # 搜索所有酒店相关知识源
        results = await rag_service.search(
            query=query,
            sources=[
                KnowledgeSource.POLICY_DOCS,
                KnowledgeSource.FAQ,
                KnowledgeSource.PRODUCT_MANUAL  # 如果有酒店服务手册
            ],
            method="hybrid_rerank",
            top_k=top_k
        )
        
        if not results:
            return "未找到相关信息。"
        
        # 按来源分组
        by_source = {}
        for result in results:
            source = result.source.value
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(result)
        
        # 格式化结果
        response_parts = ["📚 找到以下相关信息：\n"]
        
        for source, source_results in by_source.items():
            response_parts.append(f"\n【{source}】")
            for i, result in enumerate(source_results, 1):
                response_parts.append(f"\n{i}. {result.content}")
                if result.metadata.get('filename'):
                    response_parts.append(f"   📄 {result.metadata['filename']}")
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"❌ 查询知识库时出错: {str(e)}"


@tool
async def search_hotel_recommendations(
    query: str,
    location: Optional[str] = None,
    top_k: int = 3
) -> str:
    """
    根据用户需求搜索酒店推荐和建议
    
    Args:
        query: 用户需求描述，例如 "适合家庭的酒店", "商务出差酒店推荐"
        location: 地点（可选）
        top_k: 返回结果数量
        
    Returns:
        酒店推荐信息
        
    Examples:
        - "北京适合家庭出游的酒店"
        - "商务出差推荐什么酒店"
        - "有泳池的度假酒店"
    """
    try:
        rag_service = RAGService()
        
        if not rag_service.is_initialized():
            return "❌ 推荐系统未初始化。"
        
        # 构建增强查询
        enhanced_query = query
        if location:
            enhanced_query = f"{location} {query}"
        
        # 搜索产品手册和FAQ中的推荐信息
        results = await rag_service.search(
            query=enhanced_query,
            sources=[
                KnowledgeSource.PRODUCT_MANUAL,
                KnowledgeSource.FAQ
            ],
            method="hybrid_rerank",
            top_k=top_k
        )
        
        if not results:
            return "暂无相关推荐信息。建议使用 search_hotels 工具直接搜索可用酒店。"
        
        response_parts = ["🏨 酒店推荐：\n"]
        
        for i, result in enumerate(results, 1):
            response_parts.append(f"\n推荐 {i}:")
            response_parts.append(f"{result.content}")
        
        response_parts.append("\n\n💡 您可以使用 search_hotels 工具查看这些酒店的详细信息和可预订性。")
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"❌ 获取推荐时出错: {str(e)}"