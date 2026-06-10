# customer_support_chat/app/services/assistants/blog_search_assistant.py

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools.blog import search_blog_posts
from customer_support_chat.app.services.assistants.assistant_base import Assistant, llm, CompleteOrEscalate
from pydantic import BaseModel, Field

# Define task delegation tool for Blog Search
class ToBlogSearch(BaseModel):
    """Transfers work to a specialized assistant to handle blog post searches."""
    keyword: str = Field(description="The keyword to search for in blog posts.")

# Blog search assistant prompt
blog_search_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门搜索博客文章的助手。"
            "你的主要职责是使用 search_blog_posts 工具，根据用户关键词查找相关文章。"
            "请用清晰易读的格式展示搜索结果，包括标题、摘要和链接。"
            "如果用户请求与博客搜索无关，"
            "请使用 CompleteOrEscalate 工具将控制权交还给主助手。"
            "当前时间：{time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Blog search assistant tools
blog_search_assistant_tools = [
    search_blog_posts,
    CompleteOrEscalate,
]

# Create the blog search assistant runnable
blog_search_assistant_runnable = blog_search_assistant_prompt | llm.bind_tools(blog_search_assistant_tools)

# Instantiate the blog search assistant
blog_search_assistant = Assistant(blog_search_assistant_runnable)