# tests/test_bm25_retrieval.py

import asyncio
from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.types import KnowledgeSource, RetrievalResult

async def test_bm25_retrieval():
    """测试BM25检索功能"""
    
    print("="*80)
    print("🧪 Testing BM25 Retrieval")
    print("="*80)
    print()
    
    # 创建检索器
    retriever = HybridRetriever()
    
    # 准备测试文档（✅ 不要预先设置 score）
    test_docs = [
        RetrievalResult(
            content="Our cancellation policy allows free cancellation up to 24 hours before check-in. After that, a fee of $50 applies.",
            source=KnowledgeSource.POLICY_DOCS,
            metadata={'title': 'Cancellation Policy', 'section': 'refunds'}
            # ✅ 不设置 score，使用默认值 0.0
        ),
        RetrievalResult(
            content="Check-in time is 3:00 PM and check-out time is 11:00 AM. Early check-in is subject to availability.",
            source=KnowledgeSource.POLICY_DOCS,
            metadata={'title': 'Check-in Policy', 'section': 'timing'}
        ),
        RetrievalResult(
            content="We accept all major credit cards including Visa, MasterCard, and American Express. Cash payments are also accepted at the front desk.",
            source=KnowledgeSource.POLICY_DOCS,
            metadata={'title': 'Payment Policy', 'section': 'payment'}
        ),
        RetrievalResult(
            content="Pets are welcome! We charge a pet fee of $50 per stay. Maximum 2 pets per room.",
            source=KnowledgeSource.POLICY_DOCS,
            metadata={'title': 'Pet Policy', 'section': 'pets'}
        )
    ]
    
    # 添加文档并构建BM25索引
    retriever.add_documents(KnowledgeSource.POLICY_DOCS, test_docs)
    
    # 测试查询
    test_queries = [
        "What's your cancellation policy?",
        "Can I bring my dog?",
        "What time is check-in?",
        "Do you accept credit cards?"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 80)
        print()
        
        # 执行检索
        results = await retriever._bm25_search(
            query, 
            KnowledgeSource.POLICY_DOCS, 
            k=3
        )
        
        # 显示结果
        for i, result in enumerate(results, 1):
            print(f"{i}. Score: {result.score:.4f}")  # ✅ 显示归一化后的分数
            print(f"   Content: {result.content[:100]}...")
            print(f"   Metadata: {result.metadata}")
            print()
    
    print("="*80)
    print("✅ BM25 retrieval test completed!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_bm25_retrieval())