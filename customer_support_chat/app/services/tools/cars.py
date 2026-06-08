from vectorizer.app.vectordb.vectordb import VectorDB
from customer_support_chat.app.core.settings import get_settings
from customer_support_chat.app.services.gds import get_gds_adapter
from langchain_core.tools import tool

import logging
import sqlite3
from typing import List, Dict, Optional, Union
from datetime import datetime, date

logger = logging.getLogger(__name__)

settings = get_settings()
db = settings.SQLITE_DB_PATH

cars_vectordb = VectorDB(table_name="car_rentals", collection_name="car_rentals_collection")

@tool
def search_car_rentals(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """Search for car rentals based on a natural language query."""
    search_results = cars_vectordb.search(query, limit=limit)

    rentals = []
    for result in search_results:
        payload = result.payload
        rentals.append({
            "id": payload["id"],
            "name": payload["name"],
            "location": payload["location"],
            "price_tier": payload["price_tier"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "booked": payload["booked"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return rentals

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def book_car_rental(rental_id: int, approval_result=None) -> str:
    """Book a car rental by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.

    try:
        adapter = get_gds_adapter()
        result = await adapter.book_car_rental(
            rental_id=str(rental_id),
            driver_info={},
        )
        return result.get(
            "message",
            f"Car rental {rental_id} book result: {result}",
        )
    except Exception as exc:
        logger.exception("book_car_rental 调用 GDS 适配器失败: %s", exc)
        return f"Failed to book car rental {rental_id}: {exc}"

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
    approval_result=None
) -> str:
    """Update a car rental's start and end dates by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    if start_date:
        cursor.execute(
            "UPDATE car_rentals SET start_date = ? WHERE id = ?",
            (start_date.strftime('%Y-%m-%d'), rental_id),
        )
    if end_date:
        cursor.execute(
            "UPDATE car_rentals SET end_date = ? WHERE id = ?",
            (end_date.strftime('%Y-%m-%d'), rental_id),
        )

    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Car rental {rental_id} successfully updated."
    else:
        conn.close()
        return f"No car rental found with ID {rental_id}."

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
    approval_result=None
) -> str:
    """Update a car rental's start and end dates by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    if start_date:
        cursor.execute(
            "UPDATE car_rentals SET start_date = ? WHERE id = ?",
            (start_date.strftime('%Y-%m-%d'), rental_id),
        )
    if end_date:
        cursor.execute(
            "UPDATE car_rentals SET end_date = ? WHERE id = ?",
            (end_date.strftime('%Y-%m-%d'), rental_id),
        )

    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Car rental {rental_id} successfully updated."
    else:
        conn.close()
        return f"No car rental found with ID {rental_id}."

@tool
# @humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_car_rental(rental_id: int, approval_result=None) -> str:
    """Cancel a car rental by its ID."""
    # If approval is rejected, this function body won't execute.
    # If approval is granted, approval_result will contain the approval details.

    try:
        adapter = get_gds_adapter()
        result = await adapter.cancel_car_rental(
            booking_id=str(rental_id),
        )
        return result.get(
            "message",
            f"Car rental {rental_id} cancel result: {result}",
        )
    except Exception as exc:
        logger.exception("cancel_car_rental 调用 GDS 适配器失败: %s", exc)
        return f"Failed to cancel car rental {rental_id}: {exc}"
