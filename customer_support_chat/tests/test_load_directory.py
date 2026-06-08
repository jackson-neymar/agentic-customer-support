# tests/test_load_directory.py

import asyncio
from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.types import KnowledgeSource

async def test_load_directory():
    """测试批量加载目录"""
    print("="*80)
    print("🧪 测试从目录批量加载文档")
    print("="*80)
    
    retriever = HybridRetriever()
    
    # 批量加载整个目录（支持多种格式混合）
    retriever.load_documents_from_directory(
        dir_path="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/faq_documents",  # 你的文档目录
        source=KnowledgeSource.POLICY_DOCS,
        enable_chunking=True,
        recursive=True  # 递归加载子目录
    )
    
    # 测试多个查询
    queries = [
        "你的退款政策是什么?",
        "【ACP】的报名方式是什么",
        " 如何重置密码？"
    ]
    
    for query in queries:
        print(f"\n📝 查询: {query}")
        print("-" * 80)
        
        results = await retriever._bm25_search(query, KnowledgeSource.POLICY_DOCS, k=2)
        
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result.score:.4f}] {result.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_load_directory())