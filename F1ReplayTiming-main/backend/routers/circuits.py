"""Circuit names and outlines for the session picker."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Response

from app_config import MAX_YEAR, MIN_YEAR, set_cache
from services.circuits import season_circuits
from services.f1_data import get_season_events

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["circuits"])


@router.get("/seasons/{year}/circuits")
async def circuits(year: int, response: Response):
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise HTTPException(status_code=400, detail=f"Ano sem suporte: {year}")
    events = await get_season_events(year)
    try:
        data = await asyncio.to_thread(season_circuits, year, events)
    except Exception as e:
        logger.warning(f"Circuits for {year} unavailable: {e}")
        raise HTTPException(status_code=503, detail="Os circuitos estão indisponíveis no momento.")
    set_cache(response, 3600)
    return data
