from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools import (
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion,
)
from customer_support_chat.app.services.assistants.assistant_base import Assistant, CompleteOrEscalate, llm

# Excursion assistant prompt
excursion_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门处理旅行推荐和短途活动预订的助手。"
            "当用户需要预订推荐行程时，主助手会把任务委派给你。"
            "请根据用户偏好搜索可用的行程推荐，并与客户确认预订详情。"
            "如果你需要更多信息，或客户改变主意，请将任务升级回主助手。"
            "搜索时要保持耐心；如果第一次搜索没有结果，请扩大查询范围。"
            "请记住：只有相关工具成功执行后，预订才算完成。"
            "\n当前时间：{time}."
            '\n\n如果用户需要的帮助不适合你当前任何工具处理，请调用 "CompleteOrEscalate" 将对话交还给主助手。不要浪费用户时间，不要编造不存在的工具或函数。'
            "\n\n以下情况应调用 CompleteOrEscalate：\n"
            " - '算了，我想单独预订'\n"
            " - '我还得先搞清楚当地交通'\n"
            " - '等等，我还没订机票，我先去订机票'\n"
            " - '短途活动预订已确认！'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Excursion tools
book_excursion_safe_tools = [search_trip_recommendations, CompleteOrEscalate]
book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]
book_excursion_tools = book_excursion_safe_tools + book_excursion_sensitive_tools

# Create the excursion assistant runnable
book_excursion_runnable = excursion_prompt | llm.bind_tools(
    book_excursion_tools
)

# Instantiate the excursion assistant
excursion_assistant = Assistant(book_excursion_runnable)