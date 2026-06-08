from langchain_community.chat_models import ChatZhipuAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
import os
from datetime import datetime, timedelta
import re

@tool
def search_weather_posts(city: str, date: str = "today") -> str:
    """Search for weather based on a city and date.
    
    Args:
        city: The city to search for the weather (e.g., "北京", "上海", "New York")
        date: The date to search for weather. Supports formats like:
              - "today", "tomorrow", "yesterday"
              - "2024-03-15", "2024/03/15"
              - "March 15", "3月15日"
              - "+1", "-1" (days from today)
        
    Returns:
        Formatted weather information ready for display.
    """
    try:
        # 输入验证
        if not city.strip():
            return "❌ 错误：城市名称不能为空"
        
        # 解析日期
        target_date = _parse_date(date)
        if target_date is None:
            return f"❌ 错误：无法解析日期格式 '{date}'"
        
        # 检查日期范围（限制在30天内）
        days_diff = (target_date - datetime.now().date()).days
        if abs(days_diff) > 30:
            return "❌ 错误：日期范围限制在30天以内"
        
        # 初始化 ZhipuAI 客户端
        client_llm = ChatZhipuAI(
            api_key=os.getenv("ZHIPUAI_API_KEY"),
            model="glm-4",
            temperature=0.1
        )
        
        # 格式化日期
        date_str = target_date.strftime("%Y年%m月%d日")
        weekday = target_date.strftime("%A")
        
        # 构建查询提示词
        weather_query = f"""
        请查询{city}在{date_str}({weekday})的天气情况，并按以下格式返回：
        
        🌤️ **{city} 天气预报 - {date_str}**
        
        📍 **地点**: {city}
        🌡️ **温度**: [最低]°C - [最高]°C
        ☁️ **天气**: [天气状况]
        💧 **湿度**: [湿度]%
        🌪️ **风况**: [风力风向]
        🏭 **空气质量**: [AQI和等级]
        
        📝 **详情**: [详细天气描述和建议]
        
        请直接返回格式化后的文本，不要包含markdown代码块标记。
        如果无法获取某项数据，请显示"暂无数据"。
        """
        
        # 调用 ZhipuAI
        response = client_llm.invoke([HumanMessage(content=weather_query)])
        
        return response.content.strip()
        
    except Exception as e:
        return f"❌ 获取{city}天气信息时出错：{str(e)}\n请稍后重试或检查网络连接。"


def _parse_date(date_str: str) -> datetime.date:
    """解析各种日期格式"""
    date_str = date_str.strip().lower()
    today = datetime.now().date()
    
    # 相对日期
    if date_str in ["today", "今天"]:
        return today
    elif date_str in ["tomorrow", "明天"]:
        return today + timedelta(days=1)
    elif date_str in ["yesterday", "昨天"]:
        return today - timedelta(days=1)
    
    # 相对天数格式 (+1, -1, +2, -2等)
    if re.match(r'^[+-]\d+$', date_str):
        days = int(date_str)
        return today + timedelta(days=days)
    
    # 数字格式 (1, 2, -1, -2等，兼容原来的int格式)
    if re.match(r'^-?\d+$', date_str):
        days = int(date_str)
        return today + timedelta(days=days)
    
    # 标准日期格式
    date_formats = [
        "%Y-%m-%d",      # 2024-03-15
        "%Y/%m/%d",      # 2024/03/15
        "%m-%d",         # 03-15 (当年)
        "%m/%d",         # 03/15 (当年)
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            # 如果只有月日，补充当前年份
            if fmt in ["%m-%d", "%m/%d"]:
                parsed_date = parsed_date.replace(year=today.year)
            return parsed_date
        except ValueError:
            continue
    
    # 中文日期格式
    try:
        # 匹配格式：3月15日, 03月15日
        chinese_match = re.match(r'(\d{1,2})月(\d{1,2})日', date_str)
        if chinese_match:
            month, day = map(int, chinese_match.groups())
            return datetime(today.year, month, day).date()
    except ValueError:
        pass
    
    # 英文月份格式
    try:
        # 匹配格式：March 15, Mar 15
        english_formats = [
            "%B %d",     # March 15
            "%b %d",     # Mar 15
        ]
        for fmt in english_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                return parsed_date.replace(year=today.year)
            except ValueError:
                continue
    except:
        pass
    
    return None