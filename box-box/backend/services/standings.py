"""Championship standings before a session, from the Jolpica (Ergast) API.

Ported from f1-race-replay (_get_current_championship_standings, MIT licence).
The frontend adds the points each driver would score from their current
position, giving live standings as the session plays.

Jolpica is a free, public API and isn't behind F1's paywall.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

API = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = 15.0

RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]


class StandingsUnavailable(Exception):
    pass


async def _get(client: httpx.AsyncClient, path: str) -> dict:
    r = await client.get(f"{API}/{path}", params={"limit": 100})
    r.raise_for_status()
    return r.json()["MRData"]


async def _standings_after(client: httpx.AsyncClient, year: int, round_num: int) -> tuple[list[dict], list[dict]]:
    """Driver and constructor standings after a round (empty before round 1)."""
    if round_num < 1:
        return [], []
    d = await _get(client, f"{year}/{round_num}/driverStandings.json")
    c = await _get(client, f"{year}/{round_num}/constructorStandings.json")
    d_lists = d.get("StandingsTable", {}).get("StandingsLists", [])
    c_lists = c.get("StandingsTable", {}).get("StandingsLists", [])
    drivers = []
    for row in (d_lists[0]["DriverStandings"] if d_lists else []):
        drv = row.get("Driver", {})
        cons = row.get("Constructors") or [{}]
        drivers.append({
            "code": drv.get("code") or drv.get("familyName", "")[:3].upper(),
            "name": f"{drv.get('givenName', '')} {drv.get('familyName', '')}".strip(),
            "points": float(row.get("points", 0)),
            "constructor_id": cons[-1].get("constructorId"),
        })
    constructors = []
    for row in (c_lists[0]["ConstructorStandings"] if c_lists else []):
        con = row.get("Constructor", {})
        constructors.append({
            "id": con.get("constructorId"),
            "name": con.get("name"),
            "points": float(row.get("points", 0)),
        })
    return drivers, constructors


async def _sprint_points(client: httpx.AsyncClient, year: int, round_num: int) -> dict[str, tuple[float, str | None]]:
    """Points scored in a round's sprint: code -> (points, constructor_id)."""
    data = await _get(client, f"{year}/{round_num}/sprint.json")
    races = data.get("RaceTable", {}).get("Races", [])
    out = {}
    for row in (races[0].get("SprintResults", []) if races else []):
        code = row.get("Driver", {}).get("code")
        if code:
            out[code] = (float(row.get("points", 0)), row.get("Constructor", {}).get("constructorId"))
    return out


async def standings_before(year: int, round_num: int, session_type: str) -> dict:
    """Standings going into a session.

    Races and sprints score points; a race on a sprint weekend starts from the
    previous round's standings plus that weekend's sprint.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            drivers, constructors = await _standings_after(client, year, round_num - 1)
            if session_type == "R":
                sprint = await _sprint_points(client, year, round_num)
                if sprint:
                    by_code = {d["code"]: d for d in drivers}
                    by_con = {c["id"]: c for c in constructors}
                    for code, (pts, con_id) in sprint.items():
                        if code in by_code:
                            by_code[code]["points"] += pts
                        else:
                            drivers.append({"code": code, "name": code, "points": pts, "constructor_id": con_id})
                        if con_id in by_con:
                            by_con[con_id]["points"] += pts
                        elif con_id:
                            by_con[con_id] = {"id": con_id, "name": con_id, "points": pts}
                            constructors.append(by_con[con_id])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Standings unavailable for {year} R{round_num}: {e}")
            raise StandingsUnavailable(str(e)) from e

    drivers.sort(key=lambda d: -d["points"])
    constructors.sort(key=lambda c: -c["points"])
    scoring = session_type in ("R", "S")
    return {
        "year": year,
        "round": round_num,
        "session_type": session_type,
        "scoring": scoring,
        "points": RACE_POINTS if session_type == "R" else SPRINT_POINTS if session_type == "S" else [],
        "drivers": drivers,
        "constructors": constructors,
    }
