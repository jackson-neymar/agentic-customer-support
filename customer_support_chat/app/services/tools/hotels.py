from vectorizer.app.vectordb.vectordb import VectorDB
from customer_support_chat.app.core.settings import get_settings
from customer_support_chat.app.services.gds import get_gds_adapter
from langchain_core.tools import tool
# from customer_support_chat.app.core.humanloop_manager import humanloop_adapter # Import the adapter
import logging
import sqlite3
from typing import Optional, Union, List, Dict
from datetime import datetime, date

logger = logging.getLogger(__name__)

settings = get_settings()
db = settings.SQLITE_DB_PATH
hotels_vectordb = VectorDB(table_name="hotels", collection_name="hotels_collection")

@tool
def search_hotels(
    query: str,
    limit: int = 2,
) -> str:
    """Search for hotels based on a natural language query."""
    search_results = hotels_vectordb.search(query, limit=limit)

    hotels = []
    for result in search_results:
        payload = result.payload
        hotels.append({
            "id": payload["id"],
            "name": payload["name"],
            "location": payload["location"],
            "price_tier": payload["price_tier"],
            "checkin_date": payload["checkin_date"],
            "checkout_date": payload["checkout_date"],
            "booked": payload["booked"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return hotels

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def book_hotel(hotel_id: int, approval_result=None) -> str:
    """Book a hotel by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.

    try:
        adapter = get_gds_adapter()
        result = await adapter.book_hotel(
            hotel_id=str(hotel_id),
            guest_info={},
        )
        return result.get(
            "message",
            f"Hotel {hotel_id} book result: {result}",
        )
    except Exception as exc:
        logger.exception("book_hotel 调用 GDS 适配器失败: %s", exc)
        return f"Failed to book hotel {hotel_id}: {exc}"

import sqlite3
from datetime import datetime, date
from typing import Optional, Union

# @tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
    name: Optional[str] = None,
    location: Optional[str] = None,
    approval_result=None
) -> str:
    """Update a hotel's fields (dates/name/location) by its ID and mark it as booked."""

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # 1) 先确认酒店存在（避免 rowcount/未命中时的歧义）
    cursor.execute("SELECT 1 FROM hotels WHERE id = ?", (hotel_id,))
    if cursor.fetchone() is None:
        conn.close()
        return f"No hotel found with ID {hotel_id}."

    # 2) 组装要更新的字段：只更新传入的参数
    set_clauses = ["booked = 1"]  # 按你原规则：更新就标记 booked=1
    params = []

    if checkin_date is not None:
        set_clauses.append("checkin_date = ?")
        params.append(checkin_date.strftime("%Y-%m-%d"))

    if checkout_date is not None:
        set_clauses.append("checkout_date = ?")
        params.append(checkout_date.strftime("%Y-%m-%d"))

    if name is not None:
        set_clauses.append("name = ?")
        params.append(name.strip())

    if location is not None:
        set_clauses.append("location = ?")
        params.append(location.strip())

    # 3) 没有任何可更新字段时，也至少会更新 booked=1（符合你当前行为）
    sql = f"UPDATE hotels SET {', '.join(set_clauses)} WHERE id = ?"
    params.append(hotel_id)

    cursor.execute(sql, tuple(params))
    conn.commit()
    conn.close()

    return f"Hotel {hotel_id} successfully updated and booked."

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_hotel(hotel_id: int, approval_result=None) -> str:
    """Cancel a hotel by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.

    try:
        adapter = get_gds_adapter()
        result = await adapter.cancel_hotel_booking(
            booking_id=str(hotel_id),
        )
        return result.get(
            "message",
            f"Hotel {hotel_id} cancel result: {result}",
        )
    except Exception as exc:
        logger.exception("cancel_hotel 调用 GDS 适配器失败: %s", exc)
        return f"Failed to cancel hotel {hotel_id}: {exc}"
