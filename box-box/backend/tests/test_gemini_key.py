"""Gemini key pasted in the app (Settings > Team Radio)."""

import pytest

from services import caption_settings, gemini_captions

KEY = "AIzaSyTESTKEY-1234567890abcdefWXYZ"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    checked = []
    monkeypatch.setattr(gemini_captions, "check_key", lambda k: checked.append(k))
    return checked


def test_saved_key_turns_gemini_on_and_is_never_sent_back(settings):
    assert not gemini_captions.enabled()
    out = caption_settings.save(gemini=f"  {KEY} ")
    assert settings == [KEY]
    assert gemini_captions.api_key() == KEY and gemini_captions.enabled()
    assert out["gemini_enabled"] and out["gemini_key_hint"] == "WXYZ"
    assert KEY not in str(out)


def test_empty_key_removes_it(settings):
    caption_settings.save(gemini=KEY)
    out = caption_settings.save(gemini="")
    assert not out["gemini_enabled"] and not gemini_captions.enabled()


def test_env_key_wins_and_locks(settings, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-0123456789abcdefgh")
    assert caption_settings.describe()["gemini_key_locked"]
    with pytest.raises(caption_settings.CaptionSettingsError):
        caption_settings.save(gemini=KEY)
    assert gemini_captions.api_key() == "env-key-0123456789abcdefgh"


def test_check_key_rejects_obviously_wrong_text(monkeypatch):
    monkeypatch.setattr(gemini_captions.httpx, "get", lambda *a, **k: pytest.fail("no request expected"))
    with pytest.raises(caption_settings.CaptionSettingsError):
        gemini_captions.check_key("abc")
    with pytest.raises(caption_settings.CaptionSettingsError):
        gemini_captions.check_key("AIza " + "x" * 30)


def test_check_key_reports_a_refused_key(monkeypatch):
    class Resp:
        status_code = 400
    monkeypatch.setattr(gemini_captions.httpx, "get", lambda *a, **k: Resp())
    with pytest.raises(caption_settings.CaptionSettingsError, match="recusou"):
        gemini_captions.check_key(KEY)
