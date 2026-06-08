# tests/test_load_documents.py

import asyncio
from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.types import KnowledgeSource

async def test_load_single_file():
    """测试加载单个文档"""
    print("="*80)
    print("🧪 测试从文件加载文档")
    print("="*80)
    
    # 1. 创建检索器
    retriever = HybridRetriever()
    
    # 2. 从文件加载（支持 .pdf, .docx, .md, .txt）
    retriever.load_documents_from_file(
        file_path="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/faq_documents/test_faq.md",  # 你的文档路径
        source=KnowledgeSource.POLICY_DOCS,
        enable_chunking=True  # 自动分块
    )
    
    # 3. 测试检索
    query = "如何联系客服？"
    results = await retriever._bm25_search(query, KnowledgeSource.POLICY_DOCS, k=3)
    
    print(f"\n📝 查询: {query}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Content: {result.content}...")
        print(f"   Source: {result.metadata.get('filename', 'unknown')}")
        print(f"   Chunk: {result.metadata.get('chunk_index', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(test_load_single_file())