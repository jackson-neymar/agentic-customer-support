

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools import (
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel,
)
from customer_support_chat.app.services.assistants.assistant_base import (
    Assistant, 
    CompleteOrEscalate, 
    llm
)

# ✅ 导入通用 RAG 工具
RAG_TOOLS = []
HAS_RAG = False

try:
    from customer_support_chat.app.services.rag.rag_tools import search_knowledge_base
    RAG_TOOLS = [search_knowledge_base]
    HAS_RAG = True
    print("✅ RAG tools loaded for Hotel Booking Assistant")
except ImportError as e:
    print(f"⚠️ RAG tools not available: {e}")

# Hotel booking assistant prompt
# customer_support_chat/app/services/assistants/hotel_booking_assistant.py

hotel_booking_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "你是专门处理酒店预订的助手。"
     "\n\n"
     "🔴 **重要指令 - 知识库使用：**\n"
     "在回答以下任何问题之前：\n"
     "- 政策（取消、退款、入住等）\n"
     "- 规则或流程\n"
     "- 酒店设施或服务\n"
     "- 推荐\n"
     "\n"
     "请先：\n"
     "1. ✅ 调用 search_knowledge_base(query)\n"
     "2. ✅ 仔细阅读检索结果\n"
     "3. ✅ 基于检索到的信息回答\n"
     "4. ❌ 不要在未检索的情况下凭记忆或通用知识回答\n"
     "\n"
     "示例流程：\n"
     "❌ 错误：\n"
     "   用户：'取消政策是什么？'\n"
     "   你：'取消政策是...'\n"
     "\n"
     "✅ 正确：\n"
     "   用户：'取消政策是什么？'\n"
     "   你：[调用 search_knowledge_base('酒店取消政策')]\n"
     "   你：[阅读结果]\n"
     "   你：'根据我们的政策，酒店可以取消...'\n"
     "\n\n"
     "**你可用的工具：**\n"
     "1. 🔍 search_hotels - 搜索可用酒店\n"
     "2. 🏨 book_hotel - 创建预订\n"
     "3. ✏️ update_hotel - 修改预订\n"
     "4. ❌ cancel_hotel - 取消预订\n"
     "5. 📚 search_knowledge_base - 搜索公司知识（回答问题前优先使用）\n"
     "\n"
     "当前时间：{time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now())

# ✅ 整合所有工具
book_hotel_safe_tools = [search_hotels] + RAG_TOOLS
book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]
book_hotel_tools = book_hotel_safe_tools + book_hotel_sensitive_tools

# Create the hotel booking assistant runnable
book_hotel_runnable = hotel_booking_prompt | llm.bind_tools(
    book_hotel_tools + [CompleteOrEscalate]
)

# ✅ 测试工具加载
print("\n" + "="*80)
print("🧪 Hotel Booking Assistant Tools:")
print(f"   Safe tools: {len(book_hotel_safe_tools)}")
print(f"   Sensitive tools: {len(book_hotel_sensitive_tools)}")
print(f"   RAG enabled: {HAS_RAG}")
print("="*80 + "\n")

# Instantiate the hotel booking assistant
hotel_booking_assistant = Assistant(book_hotel_runnable)
hotel_booking_assistant.name = "Hotel Booking Assistant"

print(f"✅ {hotel_booking_assistant.name} initialized successfully!\n")