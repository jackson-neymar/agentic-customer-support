# customer_support_chat/main.py

import asyncio
from pathlib import Path
from customer_support_chat.app.core.logger import logger

from customer_support_chat.app.services.tools.hotels import (
    book_hotel,
    update_hotel,
    cancel_hotel
)
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.types import KnowledgeSource
from customer_support_chat.config.rag_config import (
    KNOWLEDGE_BASE_PATHS,
    RAG_CONFIG,
    INIT_RAG_ON_STARTUP,
    CONTINUE_WITHOUT_RAG
)

# customer_support_chat/main.py

import uuid
import asyncio
from pathlib import Path
from typing import Set


from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

from customer_support_chat.app.graph import multi_agentic_graph
from customer_support_chat.app.services.utils import download_and_prepare_db
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.types import KnowledgeSource


# ============================================================================
# 全局实例
# ============================================================================

# RAG 服务实例（单例）
rag_service = RAGService()


# ============================================================================
# RAG 初始化
# ============================================================================

def initialize_rag_system():
    """
    初始化 RAG 知识库系统
    """
    try:
        logger.info("="*100)
        logger.info("🚀 Initializing RAG System...")
        logger.info("="*100)
        
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent
        knowledge_base_root = project_root / "knowledge_base"
        
        # 定义知识库路径
        knowledge_base_paths = {
            KnowledgeSource.POLICY_DOCS: str(knowledge_base_root / "hotel_policies"),
            KnowledgeSource.FAQ: str(knowledge_base_root / "hotel_faq"),
            KnowledgeSource.PRODUCT_MANUAL: str(knowledge_base_root / "hotel_guides"),
        }
        
        # 检查路径
        logger.info("\n📂 Checking knowledge base paths...")
        for source, path in knowledge_base_paths.items():
            exists = "✅" if Path(path).exists() else "⚠️"
            logger.info(f"   {exists} {source.value}: {path}")
        
        # 初始化 RAG 服务
        rag_service.initialize(
            knowledge_base_paths=knowledge_base_paths,
            enable_chunking=RAG_CONFIG.get("enable_chunking", True),
            chunk_size=RAG_CONFIG.get("chunk_size", 500),
            chunk_overlap=RAG_CONFIG.get("chunk_overlap", 100),
        )
        
        # 检查初始化结果
        if rag_service.is_initialized():
            available = rag_service.get_available_sources()
            logger.info("\n" + "="*100)
            logger.info("✅ RAG System initialized successfully!")
            logger.info(f"   Available sources: {[s.value for s in available]}")
            logger.info("="*100 + "\n")
        else:
            logger.warning("\n⚠️  RAG System initialized but no sources loaded\n")
            
    except Exception as e:
        logger.error(f"\n❌ RAG initialization failed: {str(e)}")
        logger.exception(e)
        
        if not CONTINUE_WITHOUT_RAG:
            logger.error("System will exit due to RAG initialization failure")
            raise
        else:
            logger.warning("Continuing without RAG system...")


# ============================================================================
# 主程序
# ============================================================================

async def main():
    """
    主函数：初始化系统并运行对话循环
    """
    
    # -------------------------------------------------------------------------
    # 1. 初始化数据库
    # -------------------------------------------------------------------------
    logger.info("="*100)
    logger.info("🗄️  Initializing Database...")
    logger.info("="*100)
    download_and_prepare_db()
    logger.info("✅ Database ready\n")
    
    # -------------------------------------------------------------------------
    # 2. 初始化 RAG 系统（可选）
    # -------------------------------------------------------------------------
    if INIT_RAG_ON_STARTUP:
        initialize_rag_system()
    else:
        logger.info("⚠️  RAG system initialization skipped (INIT_RAG_ON_STARTUP=False)\n")
    
    # -------------------------------------------------------------------------
    # 3. 系统就绪提示
    # -------------------------------------------------------------------------
    logger.info("="*100)
    logger.info("✨ Hotel Booking Assistant Ready!")
    logger.info("="*100)
    logger.info("📝 Commands:")
    logger.info("   - Type 'quit', 'exit', or 'q' to exit")
    logger.info("   - Type 'rag <query>' to test RAG retrieval")
    logger.info("   - Type any message to chat with the assistant")
    logger.info("="*100 + "\n")
    
    # -------------------------------------------------------------------------
    # 4. 初始化会话配置
    # -------------------------------------------------------------------------
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": "5102 899977",  # 示例用户 ID
            "thread_id": thread_id,
        }
    }
    
    printed_message_ids: Set[str] = set()
    
    # -------------------------------------------------------------------------
    # 5. 主对话循环
    # -------------------------------------------------------------------------
    while True:
        try:
            # 获取用户输入
            user_input = input("👤 User: ").strip()
            
            # 退出命令
            if user_input.lower() in ["quit", "exit", "q"]:
                logger.info("👋 Goodbye!")
                break
            
            # 空输入处理
            if not user_input:
                continue
            
            # ----------------------------------------------------------------
            # 特殊命令：测试 RAG 检索
            # ----------------------------------------------------------------
            if user_input.lower().startswith("rag "):
                query = user_input[4:].strip()
                if rag_service.is_initialized():
                    logger.info(f"\n🔍 Searching for: {query}")
                    results = await rag_service.search(
                        query=query,
                        method=RAG_CONFIG.get("default_method", "hybrid_rerank"),
                        top_k=RAG_CONFIG.get("default_top_k", 5)
                    )
                    
                    if results:
                        logger.info(f"📚 Found {len(results)} relevant documents:\n")
                        for i, result in enumerate(results, 1):
                            logger.info(f"   {i}. [{result.source.value}] Score: {result.score:.3f}")
                            logger.info(f"      {result.content[:150]}...\n")
                    else:
                        logger.info("❌ No relevant documents found\n")
                else:
                    logger.warning("⚠️  RAG system not initialized\n")
                continue
            
            # ----------------------------------------------------------------
            # 正常对话流程：发送消息到 multi-agent 系统
            # ----------------------------------------------------------------
            logger.info("")  # 空行分隔
            
            # 使用 astream 流式处理
            events = multi_agentic_graph.astream(
                {"messages": [("user", user_input)]}, 
                config, 
                stream_mode="values"
            )
            
            # 处理流式输出
            async for event in events:
                messages = event.get("messages", [])
                for message in messages:
                    if message.id not in printed_message_ids:
                        message.pretty_print()
                        printed_message_ids.add(message.id)
            
            # ----------------------------------------------------------------
            # 人工确认循环（如果需要）
            # ----------------------------------------------------------------
            snapshot = multi_agentic_graph.get_state(config)
            
            while snapshot.next:
                # 询问用户是否批准操作
                approval_input = input(
                    "\n⚠️  Do you approve of the above actions? Type 'y' to continue; "
                    "otherwise, explain your requested changes.\n\n"
                    "👤 Your decision: "
                ).strip()
                
                if approval_input.lower() == "y":
                    # 用户批准：继续执行
                    result = await multi_agentic_graph.ainvoke(None, config)
                else:
                    # 用户拒绝：发送反馈
                    tool_call_id = snapshot.values["messages"][-1].tool_calls[0]["id"]
                    result = await multi_agentic_graph.ainvoke(
                        {
                            "messages": [
                                ToolMessage(
                                    tool_call_id=tool_call_id,
                                    content=f"API call denied by user. Reasoning: '{approval_input}'. "
                                           f"Continue assisting, accounting for the user's input.",
                                )
                            ]
                        },
                        config,
                    )
                
                # 打印新消息
                messages = result.get("messages", [])
                for message in messages:
                    if message.id not in printed_message_ids:
                        message.pretty_print()
                        printed_message_ids.add(message.id)
                
                # 更新状态
                snapshot = multi_agentic_graph.get_state(config)
            
            logger.info("")  # 空行分隔
            
        except KeyboardInterrupt:
            logger.info("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            logger.exception(e)


# ============================================================================
# 程序入口
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Program terminated by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}")
        logger.exception(e)
        raise