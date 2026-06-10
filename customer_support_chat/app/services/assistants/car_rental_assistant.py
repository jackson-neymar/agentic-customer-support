from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from customer_support_chat.app.services.tools import (
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
)
from customer_support_chat.app.services.assistants.assistant_base import Assistant, CompleteOrEscalate, llm

# Car rental assistant prompt
car_rental_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是专门处理租车预订的助手。"
            "当用户需要租车预订帮助时，主助手会把任务委派给你。"
            "请根据用户偏好搜索可用车辆，并与客户确认预订详情。"
            "搜索时要保持耐心；如果第一次搜索没有结果，请扩大查询范围。"
            "如果你需要更多信息，或客户改变主意，请将任务升级回主助手。"
            "请记住：只有相关工具成功执行后，预订才算完成。"
            "\n当前时间：{time}."
            "\n\n如果用户需要的帮助不适合你当前任何工具处理，请调用 "
            '"CompleteOrEscalate" 将对话交还给主助手。不要浪费用户时间，不要编造不存在的工具或函数。'
            "\n\n以下情况应调用 CompleteOrEscalate：\n"
            " - '这个季节天气怎么样？'\n"
            " - '有哪些航班可选？'\n"
            " - '算了，我想单独预订'\n"
            " - '等等，我还没订机票，我先去订机票'\n"
            " - '租车预订已确认'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Car rental tools
book_car_rental_safe_tools = [search_car_rentals, CompleteOrEscalate]
book_car_rental_sensitive_tools = [book_car_rental, update_car_rental, cancel_car_rental]
book_car_rental_tools = book_car_rental_safe_tools + book_car_rental_sensitive_tools

# Create the car rental assistant runnable
book_car_rental_runnable = car_rental_prompt | llm.bind_tools(
    book_car_rental_tools
)

# Instantiate the car rental assistant
car_rental_assistant = Assistant(book_car_rental_runnable)