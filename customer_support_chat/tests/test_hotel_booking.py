# customer_support_chat/tests/test_hotel_booking.py

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from customer_support_chat.app.services.tools.hotels import (
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel
)

async def test_hotel_workflow():
    """测试完整的酒店预订流程"""
    
    print("=" * 60)
    print("🧪 Hotel Booking Workflow Test")
    print("=" * 60)
    
    # 1. 搜索酒店
    print("\n1️⃣ Searching for hotels in Beijing...")
    search_result = search_hotels.invoke({"query": "luxury hotel in Beijing", "limit": 3})
    print(f"Search results: {len(search_result)} hotels found")
    
    if not search_result or "error" in search_result[0]:
        print("❌ Search failed or no results")
        return
    
    # 显示搜索结果
    for i, hotel in enumerate(search_result, 1):
        print(f"\n   Hotel {i}:")
        print(f"   ID: {hotel.get('id')}")
        print(f"   Name: {hotel.get('name')}")
        print(f"   Location: {hotel.get('location')}")
        print(f"   Price Tier: {hotel.get('price_tier')}")
        print(f"   Booked: {hotel.get('booked')}")
        print(f"   Similarity: {hotel.get('similarity')}")
    
    # 2. 预订第一个酒店
    hotel_id = search_result[0]['id']
    print(f"\n2️⃣ Booking hotel ID {hotel_id}...")
    
    booking_result = await book_hotel.ainvoke({
        "hotel_id": hotel_id,
        "approval_result": {"approved": True, "approver": "Test System"}
    })
    print(f"Booking result: {booking_result}")
    
    # 3. 更新预订日期
    print(f"\n3️⃣ Updating hotel ID {hotel_id} dates...")
    
    update_result = await update_hotel.ainvoke({
        "hotel_id": hotel_id,
        "checkin_date": "2026-04-01",
        "checkout_date": "2026-04-05",
        "approval_result": {"approved": True, "approver": "Test System"}
    })
    print(f"Update result: {update_result}")
    
    # 4. 取消预订
    print(f"\n4️⃣ Cancelling hotel ID {hotel_id}...")
    
    cancel_result = await cancel_hotel.ainvoke({
        "hotel_id": hotel_id,
        "approval_result": {"approved": True, "approver": "Test System"}
    })
    print(f"Cancel result: {cancel_result}")
    
    print("\n" + "=" * 60)
    print("✅ Workflow test completed!")
    print("=" * 60)

async def test_error_cases():
    """测试错误情况"""
    
    print("\n" + "=" * 60)
    print("🧪 Error Cases Test")
    print("=" * 60)
    
    # 测试不存在的酒店
    print("\n1️⃣ Testing non-existent hotel...")
    result = await book_hotel.ainvoke({
        "hotel_id": 99999,
        "approval_result": {"approved": True}
    })
    print(f"Result: {result}")
    
    # 测试重复预订
    print("\n2️⃣ Testing double booking...")
    # 首先预订一个酒店
    search_result = search_hotels.invoke({"query": "hotel", "limit": 1})
    if search_result and "id" in search_result[0]:
        hotel_id = search_result[0]["id"]
        
        # 第一次预订
        result1 = await book_hotel.ainvoke({
            "hotel_id": hotel_id,
            "approval_result": {"approved": True}
        })
        print(f"First booking: {result1}")
        
        # 第二次预订同一酒店
        result2 = await book_hotel.ainvoke({
            "hotel_id": hotel_id,
            "approval_result": {"approved": True}
        })
        print(f"Second booking (should fail): {result2}")
        
        # 清理：取消预订
        await cancel_hotel.ainvoke({
            "hotel_id": hotel_id,
            "approval_result": {"approved": True}
        })
    
    print("\n" + "=" * 60)
    print("✅ Error cases test completed!")
    print("=" * 60)

async def main():
    """运行所有测试"""
    await test_hotel_workflow()
    await test_error_cases()

if __name__ == "__main__":
    asyncio.run(main())