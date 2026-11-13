"""Circuit outlines follow calendar changes (rounds renumbered)."""

import pytest

from services import circuits, storage

MEETINGS = [
    {"meeting_name": "Australian Grand Prix", "date_start": "2026-03-06", "date_end": "2026-03-08",
     "circuit_short_name": "Melbourne", "circuit_key": 10, "location": "Melbourne"},
    {"meeting_name": "Bahrain Grand Prix", "date_start": "2026-04-10", "date_end": "2026-04-12",
     "circuit_short_name": "Sakhir", "circuit_key": 63, "location": "Sakhir"},
    {"meeting_name": "Miami Grand Prix", "date_start": "2026-05-01", "date_end": "2026-05-03",
     "circuit_short_name": "Miami", "circuit_key": 151, "location": "Miami"},
]


@pytest.fixture
def fake_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_MODE", "local")

    def get_json(url, params=None):
        if url.endswith("/meetings"):
            return MEETINGS
        key = int(url.rstrip("/").split("/")[-2])
        return {"x": [0, key, key, 0], "y": [0, 0, 1, 1], "rotation": 0, "corners": [1] * key}
    monkeypatch.setattr(circuits, "_get_json", get_json)


def ev(rnd, name, day):
    return {"round_number": rnd, "event_name": name, "event_date": day}


def test_rounds_follow_a_renumbered_calendar(fake_sources):
    old = [ev(1, "Australian Grand Prix", "2026-03-08"), ev(2, "Bahrain Grand Prix", "2026-04-12"),
           ev(3, "Miami Grand Prix", "2026-05-03")]
    first = circuits.season_circuits(2026, old)
    assert first["rounds"]["2"]["short_name"] == "Sakhir"

    # Bahrain dropped: Miami is round 2 now
    new = [ev(1, "Australian Grand Prix", "2026-03-08"), ev(2, "Miami Grand Prix", "2026-05-03")]
    again = circuits.season_circuits(2026, new)
    assert again["rounds"]["2"]["short_name"] == "Miami"
    assert again["rounds"]["2"]["corners"] == 151
    assert "3" not in again["rounds"]
    assert again["rounds"]["1"]["short_name"] == "Melbourne"


def test_old_cache_without_dates_is_rebuilt(fake_sources):
    storage.put_json("circuits/2026.json", {
        "version": 1, "year": 2026, "built": 9e12,
        "rounds": {"1": {"short_name": "Sakhir", "points": [[0, 0]], "corners": 15}},
    })
    out = circuits.season_circuits(2026, [ev(1, "Australian Grand Prix", "2026-03-08")])
    assert out["rounds"]["1"]["short_name"] == "Melbourne"
