from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools import (
    search_flights,
    lookup_policy,
)
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
from customer_support_chat.app.services.assistants.assistant_base import Assistant, llm
from customer_support_chat.app.core.state import State
from pydantic import BaseModel, Field

# Import new delegation models
from customer_support_chat.app.services.assistants.woocommerce_assistant import ToWooCommerceProducts, ToWooCommerceOrders
from customer_support_chat.app.services.assistants.form_submission_assistant import ToFormSubmission
from customer_support_chat.app.services.assistants.blog_search_assistant import ToBlogSearch

# Define task delegation tools
class ToFlightBookingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle flight updates and cancellations."""
    request: str = Field(description="Any necessary follow-up questions the update flight assistant should clarify before proceeding.")

class ToBookCarRental(BaseModel):
    """Transfers work to a specialized assistant to handle car rental bookings."""
    location: str = Field(description="The location where the user wants to rent a car.")
    start_date: str = Field(description="The start date of the car rental.")
    end_date: str = Field(description="The end date of the car rental.")
    request: str = Field(description="Any additional information or requests from the user regarding the car rental.")

class ToHotelBookingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle hotel bookings, modifications, and cancellations."""
    location: str = Field(description="The location where the user wants to book a hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    checkin_date: str = Field(description="The check-in date for the hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    checkout_date: str = Field(description="The check-out date for the hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    request: str = Field(description="Any additional information or requests from the user regarding the hotel operation (booking, cancellation, modification).")

class ToBookExcursion(BaseModel):
    """Transfers work to a specialized assistant to handle trip recommendation and other excursion bookings."""
    location: str = Field(description="The location where the user wants to book a recommended trip.")
    request: str = Field(description="Any additional information or requests from the user regarding the trip recommendation.")

class ToWeatherSearch(BaseModel):
    """Transfers work to a specialized assistant to handle weather searches."""
    city: str = Field(description="The city to search for the weather.")
    date: str = Field(description="The date to search for the weather")
    request: str = Field(description="Any additional information or requests from the user regarding the weather search.")

from customer_support_chat.app.services.tools import (
    search_flights,
    lookup_policy,
)
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults

# ✅ 导入通用 RAG 工具
try:
    from customer_support_chat.app.services.rag.rag_tools import search_knowledge_base
    HAS_RAG = True
except ImportError:
    search_knowledge_base = None
    HAS_RAG = False

# Primary assistant prompt
primary_assistant_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful customer support assistant for Swiss Airlines. "
     "\n**Your Tools:**\n"
     "- search_flights: Search flight information\n"
     "- lookup_policy: Check company policies\n"
     "- DuckDuckGoSearchResults: Web search\n"
     + ("- search_knowledge_base: Search comprehensive company knowledge base\n"
        "\n**IMPORTANT:** ALWAYS use search_knowledge_base before web search or saying 'I don't know'\n"
        if HAS_RAG else "") +
     "\n**Delegation Rules:**\n"
     "- Flight updates/cancellations → ToFlightBookingAssistant\n"
     "- Car rental → ToBookCarRental\n"
     "- Hotel → ToHotelBookingAssistant\n"
     "- Excursions → ToBookExcursion\n"
     "...\n"
     "\nCurrent user info:\n<Flights>\n{user_info}\n</Flights>"
     "\nCurrent time: {time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now())

# Primary assistant tools
primary_assistant_tools = [
    DuckDuckGoSearchResults(max_results=10),
    search_flights,
    lookup_policy,
]

# ✅ 添加 RAG 工具（如果可用）
if HAS_RAG:
    primary_assistant_tools.append(search_knowledge_base)

# 添加委托工具
primary_assistant_tools.extend([
    ToFlightBookingAssistant,
    ToBookCarRental,
    ToHotelBookingAssistant,
    ToBookExcursion,
    ToWooCommerceProducts,
    ToWooCommerceOrders,
    ToFormSubmission,
    ToBlogSearch,
    ToWeatherSearch,
])

primary_assistant_runnable = primary_assistant_prompt | llm.bind_tools(primary_assistant_tools)
primary_assistant = Assistant(primary_assistant_runnable)