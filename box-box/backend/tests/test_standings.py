"""Tests for the pre-session championship standings (Jolpica/Ergast)."""

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import standings  # noqa: E402


def _mrdata(**kw):
    return {"MRData": kw}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/2025/4/driverStandings.json"):
        return httpx.Response(200, json=_mrdata(StandingsTable={"StandingsLists": [{"DriverStandings": [
            {"points": "50", "Driver": {"code": "AAA", "givenName": "A", "familyName": "Aa"}, "Constructors": [{"constructorId": "red"}]},
            {"points": "40", "Driver": {"code": "BBB", "givenName": "B", "familyName": "Bb"}, "Constructors": [{"constructorId": "blue"}]},
        ]}]}))
    if path.endswith("/2025/4/constructorStandings.json"):
        return httpx.Response(200, json=_mrdata(StandingsTable={"StandingsLists": [{"ConstructorStandings": [
            {"points": "60", "Constructor": {"constructorId": "red", "name": "Red"}},
            {"points": "45", "Constructor": {"constructorId": "blue", "name": "Blue"}},
        ]}]}))
    if path.endswith("/2025/5/sprint.json"):
        return httpx.Response(200, json=_mrdata(RaceTable={"Races": [{"SprintResults": [
            {"points": "8", "Driver": {"code": "BBB"}, "Constructor": {"constructorId": "blue"}},
            {"points": "7", "Driver": {"code": "AAA"}, "Constructor": {"constructorId": "red"}},
        ]}]}))
    return httpx.Response(404)


def _run(monkeypatch, *args):
    real = httpx.AsyncClient

    def client(*a, **kw):
        kw["transport"] = httpx.MockTransport(_handler)
        return real(*a, **kw)

    monkeypatch.setattr(standings.httpx, "AsyncClient", client)
    return asyncio.run(standings.standings_before(*args))


def test_race_on_sprint_weekend_adds_sprint_points(monkeypatch):
    data = _run(monkeypatch, 2025, 5, "R")
    pts = {d["code"]: d["points"] for d in data["drivers"]}
    assert pts == {"AAA": 57, "BBB": 48}
    cons = {c["id"]: c["points"] for c in data["constructors"]}
    assert cons == {"red": 67, "blue": 53}
    assert data["scoring"] and data["points"][0] == 25


def test_sprint_starts_from_previous_round(monkeypatch):
    data = _run(monkeypatch, 2025, 5, "S")
    assert {d["code"]: d["points"] for d in data["drivers"]} == {"AAA": 50, "BBB": 40}
    assert data["points"][0] == 8


def test_round_one_is_empty(monkeypatch):
    data = _run(monkeypatch, 2025, 1, "Q")
    assert data["drivers"] == [] and not data["scoring"]
