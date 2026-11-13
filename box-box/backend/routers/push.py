"""Turn race alerts (push notifications) on and off for a device.

Auth, when enabled, is enforced by the /api middleware in main.py.
"""

import asyncio

from fastapi import APIRouter, Body, HTTPException

from services import push

router = APIRouter(prefix="/api/push", tags=["push"])


def _require_enabled() -> None:
    if not push.push_enabled():
        raise HTTPException(status_code=404, detail="Alertas desligados neste servidor")


@router.get("/key")
async def vapid_key():
    _require_enabled()
    return {"public_key": await asyncio.to_thread(push.public_key)}


@router.post("/subscribe")
async def subscribe(subscription: dict = Body(...)):
    _require_enabled()
    if not push.valid_subscription(subscription):
        raise HTTPException(status_code=400, detail="Inscrição inválida")
    await asyncio.to_thread(push.add_subscription, subscription)
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(endpoint: str = Body(..., embed=True)):
    _require_enabled()
    await asyncio.to_thread(push.remove_subscription, endpoint)
    return {"ok": True}


@router.post("/status")
async def status(endpoint: str = Body(..., embed=True)):
    """Whether this device is still subscribed on the server, and the
    drivers whose radio it follows."""
    _require_enabled()
    sub = await asyncio.to_thread(push.get_subscription, endpoint)
    return {"subscribed": sub is not None, "radio_drivers": (sub or {}).get("radio_drivers", [])}


@router.post("/radio-drivers")
async def radio_drivers(endpoint: str = Body(...), drivers: list[str] = Body(...)):
    """Choose the drivers whose team radio this device is alerted to."""
    _require_enabled()
    saved = await asyncio.to_thread(push.set_radio_drivers, endpoint, drivers)
    if saved is None:
        raise HTTPException(status_code=404, detail="Este aparelho não está inscrito")
    return {"radio_drivers": saved}


def _latest_roster() -> list[dict]:
    """Drivers of the most recent session downloaded on this server."""
    import re
    from datetime import datetime, timezone

    from services.storage import get_json, list_keys

    order = {"R": 7, "S": 6, "SQ": 5, "Q": 4, "FP3": 3, "FP2": 2, "FP1": 1}
    year = datetime.now(timezone.utc).year
    for y in (year, year - 1):
        found = []
        for key in list_keys(f"sessions/{y}/"):
            m = re.match(rf"sessions/{y}/(\d+)/([A-Z0-9]+)/info\.json$", key)
            if m:
                found.append((int(m.group(1)), order.get(m.group(2), 0), key))
        for _, _, key in sorted(found, reverse=True):
            info = get_json(key) or {}
            drivers = [
                {"abbr": d.get("abbreviation"), "name": d.get("full_name"), "color": d.get("team_color"), "team": d.get("team_name")}
                for d in info.get("drivers") or [] if d.get("abbreviation")
            ]
            if drivers:
                return sorted(drivers, key=lambda d: (d.get("team") or "", d["abbr"]))
    return []


@router.get("/drivers")
async def drivers():
    """Drivers to choose from for team radio alerts."""
    _require_enabled()
    return {"drivers": await asyncio.to_thread(_latest_roster)}


@router.post("/test")
async def test(endpoint: str = Body(..., embed=True)):
    _require_enabled()
    ok = await asyncio.to_thread(
        push.send_to, endpoint, "🏎️ Box Box", "Alertas ligados! Você vai receber a largada, Safety Car, bandeiras e o resultado.",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Este aparelho não está inscrito")
    return {"ok": True}
