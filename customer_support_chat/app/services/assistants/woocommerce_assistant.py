# customer_support_chat/app/services/assistants/woocommerce_assistant.py

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools.woocommerce import (
    search_products,
    search_orders,
)
from customer_support_chat.app.services.assistants.assistant_base import Assistant, llm, CompleteOrEscalate
from customer_support_chat.app.core.logger import logger
from pydantic import BaseModel, Field

# Define task delegation tools for WooCommerce
class ToWooCommerceProducts(BaseModel):
    """Transfers work to a specialized assistant to handle WooCommerce product searches."""
    query: str = Field(description="The search query for products (e.g., product name, category).")

class ToWooCommerceOrders(BaseModel):
    """Transfers work to a specialized assistant to handle WooCommerce order searches."""
    search_type: str = Field(description="The type of search to perform. Must be one of: 'email', 'name', or 'id'.")
    search_value: str = Field(description="The value to search for. For email searches, provide the customer's email address. For name searches, provide the customer's full name. For ID searches, provide the order ID.")

# WooCommerce assistant prompt
woocommerce_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门处理 WooCommerce 操作的助手。"
            "你的主要职责是使用提供的工具搜索产品和订单。"
            "当用户要求搜索产品时，立即使用 search_products 工具。"
            "当用户要求搜索订单时，你必须先要求用户提供邮箱地址或完整姓名以验证身份，然后再搜索订单。"
            "绝不要在没有适当验证信息（邮箱或姓名）的情况下搜索订单。"
            "如果用户只说'查找订单'或类似内容但没有提供验证信息，请礼貌地要求其提供邮箱地址或完整姓名。"
            "如果用户提供邮箱，使用 search_orders 工具，并设置 search_type='email'、search_value 为该邮箱。"
            "如果用户提供姓名，使用 search_orders 工具，并设置 search_type='name'、search_value 为完整姓名。"
            "如果用户提供订单 ID，使用 search_orders 工具，并设置 search_type='id'、search_value 为该 ID。"
            "如果搜索没有结果，请说明没有找到匹配项，并建议尝试其他搜索方式。"
            "如果工具调用因超时或连接错误失败，请告诉用户服务器可能繁忙，并建议稍后重试。"
            "始终根据工具结果向用户提供清晰、简洁的信息。"
            "如果用户请求超出产品或订单搜索范围，"
            "请使用 CompleteOrEscalate 工具将控制权交还给主助手。"
            "当前时间：{time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# WooCommerce assistant tools
woocommerce_assistant_tools = [
    search_products,
    search_orders,
    CompleteOrEscalate,
]

# Create the WooCommerce assistant runnable
woocommerce_assistant_runnable = woocommerce_assistant_prompt | llm.bind_tools(woocommerce_assistant_tools)

# Instantiate the WooCommerce assistant
woocommerce_assistant = Assistant(woocommerce_assistant_runnable)