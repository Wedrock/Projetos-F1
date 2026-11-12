"""Insights ported from f1-race-replay: tyre degradation, tyre strategy and
championship standings."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Response

from app_config import set_cache, validate_session
from services import storage
from services.standings import StandingsUnavailable, standings_before
from services.storage import aget_json
from services.tyre_model import build_strategy, build_tyre_model

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["insights"])

TYRE_MODEL_VERSION = 1


async def _laps(year: int, round_num: int, session_type: str) -> list[dict]:
    data = await aget_json(f"sessions/{year}/{round_num}/{session_type}/laps.json")
    if not data:
        raise HTTPException(status_code=404, detail="Os dados de voltas não estão disponíveis para esta sessão.")
    return data


@router.get("/sessions/{year}/{round_num}/tyre-model")
async def tyre_model(
    year: int,
    round_num: int,
    response: Response,
    type: str = Query("R", description="Session type"),
):
    validate_session(year, round_num, type)
    path = f"sessions/{year}/{round_num}/{type}/tyre_model.json"
    data = await aget_json(path)
    if not data or data.get("version") != TYRE_MODEL_VERSION:
        laps = await _laps(year, round_num, type)
        data = await asyncio.to_thread(build_tyre_model, laps)
        try:
            await asyncio.to_thread(storage.put_json, path, data)
        except Exception as e:  # read-only storage still gets an answer
            logger.warning(f"Couldn't store tyre model for {year} R{round_num} {type}: {e}")
    set_cache(response, 300)
    return data


@router.get("/sessions/{year}/{round_num}/strategy")
async def tyre_strategy(
    year: int,
    round_num: int,
    response: Response,
    type: str = Query("R", description="Session type"),
):
    validate_session(year, round_num, type)
    laps = await _laps(year, round_num, type)
    data = await asyncio.to_thread(build_strategy, laps)
    set_cache(response, 300)
    return data


@router.get("/sessions/{year}/{round_num}/standings")
async def standings(
    year: int,
    round_num: int,
    response: Response,
    type: str = Query("R", description="Session type"),
):
    validate_session(year, round_num, type)
    path = f"standings/{year}/{round_num}_{type}.json"
    data = await aget_json(path)
    if data is None:
        try:
            data = await standings_before(year, round_num, type)
        except StandingsUnavailable:
            raise HTTPException(status_code=503, detail="A classificação do campeonato está indisponível no momento.")
        # Only keep standings once the round before is in the books
        if data["drivers"] or round_num == 1:
            try:
                await asyncio.to_thread(storage.put_json, path, data)
            except Exception as e:
                logger.warning(f"Couldn't store standings for {year} R{round_num}: {e}")
    set_cache(response, 3600)
    return data
