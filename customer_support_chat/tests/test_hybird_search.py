# tests/test_hybrid_search.py

import asyncio
from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.types import KnowledgeSource

async def test_different_methods():
    """测试不同检索方法"""
    
    print("="*100)
    print("🧪 测试混合检索系统 - 对比不同方法")
    print("="*100)
    
    # 1. 创建检索器
    retriever = HybridRetriever()
    
    # 2. 加载文档
    retriever.load_documents_from_directory(
        dir_path="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/faq_documents",
        source=KnowledgeSource.POLICY_DOCS,
        enable_chunking=True,
        recursive=True
    )
    
    # 3. 测试查询
    query = "【ACP】的报名方式是什么"
    
    print(f"\n{'='*100}")
    print(f"📝 测试查询: {query}")
    print(f"{'='*100}")
    
    # 4. 测试不同方法
    methods = [
        ("bm25", "BM25 关键词检索"),
        ("vector", "向量语义检索"),
        ("hybrid", "混合检索 (默认权重)"),
        ("hybrid_rerank", "混合检索 + 重排序"),
    ]
    
    for method, description in methods:
        print(f"\n{'🔍 ' + description:^100}")
        print("-" * 100)
        
        try:
            results = await retriever.retrieve(
                query=query,
                sources=[KnowledgeSource.POLICY_DOCS],
                method=method,
                top_k=3
            )
            
            if not results:
                print("   ⚠️ 无检索结果")
                continue
            
            for i, result in enumerate(results, 1):
                score_bar = "█" * int(result.score * 50)
                print(f"\n   {i}. Score: {result.score:.4f} {score_bar}")
                print(f"      File: {result.metadata.get('filename', 'unknown')}")
                print(f"      Content: {result.content[:150]}...")
        
        except Exception as e:
            print(f"   ❌ 错误: {e}")

async def test_parameter_tuning():
    """测试参数调优"""
    
    print("\n" + "="*100)
    print("🎛️ 参数调优测试 - 不同权重配置")
    print("="*100)
    
    retriever = HybridRetriever()
    
    # 加载文档
    retriever.load_documents_from_directory(
        dir_path="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/faq_documents",
        source=KnowledgeSource.POLICY_DOCS,
        enable_chunking=True
    )
    
    query = "退款政策是什么"
    
    # 测试不同权重组合
    weight_configs = [
        (1.0, 0.0, "100% BM25"),
        (0.7, 0.3, "70% BM25 + 30% Vector"),
        (0.5, 0.5, "50% BM25 + 50% Vector"),
        (0.3, 0.7, "30% BM25 + 70% Vector"),
        (0.0, 1.0, "100% Vector"),
    ]
    
    print(f"\n📝 查询: {query}")
    print("-" * 100)
    
    for bm25_w, vector_w, desc in weight_configs:
        print(f"\n⚖️ {desc}")
        
        results = await retriever.retrieve(
            query=query,
            sources=[KnowledgeSource.POLICY_DOCS],
            method="hybrid",
            top_k=3,
            bm25_weight=bm25_w,
            vector_weight=vector_w
        )
        
        for i, result in enumerate(results, 1):
            print(f"   {i}. Score: {result.score:.4f} | {result.content[:80]}...")

async def test_rerank_comparison():
    """对比重排序效果"""
    
    print("\n" + "="*100)
    print("🎯 重排序效果对比")
    print("="*100)
    
    retriever = HybridRetriever()
    
    # 加载文档
    retriever.load_documents_from_directory(
        dir_path="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/faq_documents",
        source=KnowledgeSource.POLICY_DOCS,
        enable_chunking=True
    )
    
    query = "产品出现问题怎么办"
    
    print(f"\n📝 查询: {query}\n")
    
    # 不使用重排序
    print("=" * 100)
    print("🔍 混合检索（无重排序）")
    print("-" * 100)
    
    results_no_rerank = await retriever.retrieve(
        query=query,
        method="hybrid",
        top_k=5,
        rerank=False
    )
    
    for i, result in enumerate(results_no_rerank, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Content: {result.content[:120]}...")
    
    # 使用重排序
    print("\n" + "=" * 100)
    print("🎯 混合检索（重排序后）")
    print("-" * 100)
    
    results_rerank = await retriever.retrieve(
        query=query,
        method="hybrid_rerank",
        top_k=5
    )
    
    for i, result in enumerate(results_rerank, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Content: {result.content[:120]}...")

async def main():
    # 测试1: 不同方法对比
    await test_different_methods()
    
    # 测试2: 参数调优
    # await test_parameter_tuning()
    
    # 测试3: 重排序对比
    # await test_rerank_comparison()

if __name__ == "__main__":
    asyncio.run(main())