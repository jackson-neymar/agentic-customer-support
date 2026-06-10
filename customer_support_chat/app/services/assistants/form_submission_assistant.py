# customer_support_chat/app/services/assistants/form_submission_assistant.py

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools.forms import submit_form
from customer_support_chat.app.services.assistants.assistant_base import Assistant, llm, CompleteOrEscalate
from pydantic import BaseModel, Field
from typing import Dict, Any

# Define task delegation tool for Form Submission
class ToFormSubmission(BaseModel):
    """Transfers work to a specialized assistant to handle user form submissions."""
    form_data: Dict[str, Any] = Field(description="A dictionary containing form field names as keys and user inputs as values.")

# Form submission assistant prompt
form_submission_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门处理用户表单提交的助手。"
            "你的主要职责是向用户收集必要信息，然后使用 submit_form 工具"
            "将数据发送到指定 API 端点。"
            "表单需要以下必填字段："
            "- 'your-name'：用户全名 "
            "- 'your-email'：用户邮箱地址 "
            "- 'your-subject'：咨询主题 "
            "此外，表单始终包含固定参数 '_wpcf7': 942。"
            "提交表单前，你必须先收集齐这三个必填字段。"
            "如果用户没有提供全部必需信息，请礼貌地询问缺失字段。"
            "提交表单前始终先向用户确认。"
            "如果用户请求与表单提交无关，"
            "请使用 CompleteOrEscalate 工具将控制权交还给主助手。"
            "当前时间：{time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Form submission assistant tools
form_submission_assistant_tools = [
    submit_form,
    CompleteOrEscalate,
]

# Create the form submission assistant runnable
form_submission_assistant_runnable = form_submission_assistant_prompt | llm.bind_tools(form_submission_assistant_tools)

# Instantiate the form submission assistant
form_submission_assistant = Assistant(form_submission_assistant_runnable)