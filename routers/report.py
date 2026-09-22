from fastapi import APIRouter, HTTPException

from models import DailyReport
from services.report_card import get_daily_report


router = APIRouter(prefix="/report")


@router.get("/daily", response_model=DailyReport)
async def daily_report():
    report = await get_daily_report()
    if report is None:
        # Same 503 contract as /history/*: no database configured, or no completed
        # day recorded yet. The card hides itself rather than erroring.
        raise HTTPException(
            status_code=503, detail="No daily report available yet"
        )
    return report
