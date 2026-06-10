from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools import (
    search_flights,
    update_ticket_to_new_flight,
    cancel_ticket,
)
from customer_support_chat.app.services.assistants.assistant_base import Assistant, CompleteOrEscalate, llm

# Flight booking assistant prompt
flight_booking_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门处理航班改签和取消的助手。"
            "当用户需要更新预订时，主助手会把任务委派给你。"
            "请与客户确认更新后的航班详情，并告知任何额外费用。"
            "搜索时要保持耐心；如果第一次搜索没有结果，请扩大查询范围。"
            "如果你需要更多信息，或客户改变主意，请将任务升级回主助手。"
            "请记住：只有相关工具成功执行后，预订才算完成。"
            "\n\n当前用户航班信息：\n<Flights>\n{user_info}\n</Flights>"
            "\n当前时间：{time}."
            "\n\n如果用户需要的帮助不适合你当前任何工具处理，请调用 "
            '"CompleteOrEscalate" 将对话交还给主助手。不要浪费用户时间，不要编造不存在的工具或函数。',
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Flight booking tools
update_flight_safe_tools = [search_flights, CompleteOrEscalate]
update_flight_sensitive_tools = [update_ticket_to_new_flight, cancel_ticket]
update_flight_tools = update_flight_safe_tools + update_flight_sensitive_tools

# Create the flight booking assistant runnable
update_flight_runnable = flight_booking_prompt | llm.bind_tools(
    update_flight_tools
)

# Instantiate the flight booking assistant
flight_booking_assistant = Assistant(update_flight_runnable)