

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
     "You are a specialized assistant for handling hotel bookings."
     "\n\n"
     "🔴 **CRITICAL INSTRUCTION - KNOWLEDGE BASE USAGE:**\n"
     "Before answering ANY question about:\n"
     "- Policies (cancellation, refund, check-in, etc.)\n"
     "- Rules or procedures\n"
     "- Hotel amenities or services\n"
     "- Recommendations\n"
     "\n"
     "You MUST:\n"
     "1. ✅ FIRST call search_knowledge_base(query)\n"
     "2. ✅ Read the results carefully\n"
     "3. ✅ Base your answer on the retrieved information\n"
     "4. ❌ DO NOT answer from memory or general knowledge without searching first\n"
     "\n"
     "Example workflow:\n"
     "❌ Wrong:\n"
     "   User: 'What's the cancellation policy?'\n"
     "   You: 'The cancellation policy is...'\n"
     "\n"
     "✅ Correct:\n"
     "   User: 'What's the cancellation policy?'\n"
     "   You: [Call search_knowledge_base('hotel cancellation policy')]\n"
     "   You: [Read results]\n"
     "   You: 'According to our policy, hotels can be cancelled...'\n"
     "\n\n"
     "**Your Available Tools:**\n"
     "1. 🔍 search_hotels - Search available hotels\n"
     "2. 🏨 book_hotel - Make a booking\n"
     "3. ✏️ update_hotel - Modify booking\n"
     "4. ❌ cancel_hotel - Cancel booking\n"
     "5. 📚 search_knowledge_base - Search company knowledge (USE THIS FIRST for questions!)\n"
     "\n"
     "Current time: {time}."
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