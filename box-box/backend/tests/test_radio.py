import json

import pytest

from services import gemini_captions, openf1_radio, team_radio


# -- Gemini ---------------------------------------------------------------

def test_parse_reply():
    c = gemini_captions.parse_reply('```json\n{"en": "Box, box.", "pt": "Box, box."}\n```')
    assert (c.en, c.pt) == ("Box, box.", "Box, box.")
    assert gemini_captions.parse_reply('{"en": null, "pt": null}') == gemini_captions.Caption(None, None)
    # No English, no Portuguese either
    assert gemini_captions.parse_reply('{"en": "", "pt": "algo"}') == gemini_captions.Caption(None, None)
    assert gemini_captions.parse_reply("not json") is None
    assert gemini_captions.parse_reply("[1, 2]") is None


def test_parse_reply_split_by_speaker():
    c = gemini_captions.parse_reply(json.dumps({"lines": [
        {"who": "team", "en": "Box this lap.", "pt": "Box nesta volta."},
        {"who": "driver", "en": "Copy.", "pt": "Entendido."},
    ]}))
    assert c.en == "Box this lap. Copy." and c.pt == "Box nesta volta. Entendido."
    assert [l["who"] for l in c.lines] == ["team", "driver"]
    # Same voice twice in a row is one line; unknown "who" counts as the team
    c = gemini_captions.parse_reply(json.dumps({"lines": [
        {"who": "Engineer", "en": "Gap is 2.", "pt": "Diferença de 2."},
        {"who": "team", "en": "Push.", "pt": "Acelera."},
        {"who": "driver", "en": "", "pt": "x"},
    ]}))
    assert c.lines == [{"who": "team", "en": "Gap is 2. Push.", "pt": "Diferença de 2. Acelera."}]
    assert gemini_captions.parse_reply('{"lines": []}') == gemini_captions.Caption(None, None)


def test_backfill_redoes_clips_without_lines(monkeypatch):
    from services import radio_backfill
    monkeypatch.setattr(team_radio, "captions_enabled", lambda: True)
    monkeypatch.setattr(gemini_captions, "enabled", lambda: True)
    clips = [
        {"transcript": "a", "transcript_pt": "a"},  # Portuguese but not split: redo
        {"transcript": "b", "transcript_pt": "b", "lines": [{"who": "team", "en": "b", "pt": "b"}]},
        {"no_speech": True},
        {"transcript": "c", "lines_tried": True},
    ]
    assert radio_backfill.needs_work(clips) == 1


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


def _reply(text):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_S", "0")
    monkeypatch.setattr(gemini_captions, "RETRY_WAIT_S", 0)
    calls = []

    def install(*responses):
        queue = list(responses)

        def post(url, json=None, headers=None, timeout=None):
            calls.append({"url": url, "json": json, "headers": headers})
            return queue.pop(0)
        monkeypatch.setattr(gemini_captions.httpx, "post", post)
        return calls
    return install


def test_caption_sends_audio_and_key(gemini):
    calls = gemini(_reply('{"en": "Copy, box this lap.", "pt": "Entendido, box nesta volta."}'))
    c = gemini_captions.caption(b"ID3audio", {"speaker": "Lando Norris (NOR, McLaren)", "year": 2026}, draft="copy box")
    assert c.pt == "Entendido, box nesta volta."
    assert calls[0]["headers"] == {"x-goog-api-key": "test-key"}
    assert "gemini-flash-lite-latest:generateContent" in calls[0]["url"]
    parts = calls[0]["json"]["contents"][0]["parts"]
    assert "Lando Norris" in parts[0]["text"] and "copy box" in parts[0]["text"]
    assert parts[1]["inline_data"]["mime_type"] == "audio/mp3"


def test_caption_retries_once_on_rate_limit(gemini):
    gemini(FakeResponse(429), _reply('{"en": "Push now.", "pt": "Acelera agora."}'))
    assert gemini_captions.caption(b"x").en == "Push now."


def test_caption_failure_is_none(gemini):
    gemini(FakeResponse(500))
    assert gemini_captions.caption(b"x") is None


def test_no_key_no_caption(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini_captions.caption(b"x") is None
    assert not gemini_captions.enabled()


def test_caption_both_prefers_gemini(gemini, monkeypatch):
    gemini(_reply('{"en": "Good job.", "pt": "Bom trabalho."}'))
    monkeypatch.setattr(team_radio, "whisper_available", lambda: False)
    monkeypatch.delenv("TEAM_RADIO_CAPTIONS", raising=False)
    assert team_radio.caption_both(b"x", "Lando", 2026) == ("Good job.", "Bom trabalho.")


def test_caption_full_returns_lines(gemini, monkeypatch):
    gemini(_reply('{"lines": [{"who": "driver", "en": "Tyres are gone.", "pt": "Os pneus acabaram."}]}'))
    monkeypatch.setattr(team_radio, "whisper_available", lambda: False)
    monkeypatch.delenv("TEAM_RADIO_CAPTIONS", raising=False)
    en, pt, lines = team_radio.caption_full(b"x", "Lando", 2026)
    assert (en, pt) == ("Tyres are gone.", "Os pneus acabaram.")
    assert lines == [{"who": "driver", "en": "Tyres are gone.", "pt": "Os pneus acabaram."}]


def test_caption_both_without_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(team_radio, "captions_enabled", lambda: True)
    monkeypatch.setattr(team_radio, "caption", lambda *a, **k: "Whisper text")
    assert team_radio.caption_both(b"x", None, 2026) == ("Whisper text", None)


# -- OpenF1 ---------------------------------------------------------------

def test_recorded_time_comes_from_the_file_name():
    url = "https://livetiming.formula1.com/static/2026/x/TeamRadio/VER_3_20261108_154416.mp3"
    # Published 50 s later; São Paulo is UTC-3
    assert openf1_radio.recorded_utc(url, "2026-11-08T18:45:06.477000+00:00", "-03:00:00") == "2026-11-08T18:44:16Z"
    # East of UTC
    assert openf1_radio.recorded_utc(url.replace("154416", "200000"), None, "08:00:00") == "2026-11-08T12:00:00Z"


def test_recorded_time_falls_back_to_published():
    assert openf1_radio.recorded_utc("https://x/clip.mp3", "2026-11-08T18:45:06+00:00", "-03:00:00") == "2026-11-08T18:45:06Z"
    # A file name far from the publish time (wrong offset): the publish time wins
    url = "https://x/VER_3_20261108_010000.mp3"
    assert openf1_radio.recorded_utc(url, "2026-11-08T18:45:06+00:00", "-03:00:00") == "2026-11-08T18:45:06Z"


def test_build_clips_uses_full_url_from_openf1(monkeypatch):
    monkeypatch.setattr(team_radio, "captions_enabled", lambda: False)
    from datetime import datetime
    caps = [{"Utc": "2026-11-08T17:00:30Z", "RacingNumber": "3", "Path": "VER_3_x.mp3", "Url": "https://f1/VER_3_x.mp3"}]
    clips = team_radio.build_clips(caps, "", datetime(2026, 11, 8, 17, 0, 0), {"3": {"abbr": "VER"}}, with_captions=False)
    assert clips[0]["url"] == "https://f1/VER_3_x.mp3"
    assert clips[0]["t"] == 30.0 and clips[0]["driver"] == "VER"
