"""Finding a team radio clip inside the broadcast's audio."""

import numpy as np

from services import radio_air

SR = radio_air.SR
rng = np.random.default_rng(7)


def speechlike(seconds: float) -> np.ndarray:
    """Noise shaped into syllables, roughly like a voice on the radio."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    envelope = (np.sin(2 * np.pi * 3.5 * t) > 0).astype(np.float32)
    return (rng.standard_normal(n).astype(np.float32) * envelope)


def broadcast_with(clip: np.ndarray, at_s: float, seconds: float, gain: float = 0.6) -> np.ndarray:
    """Commentary-like speech plus engine hum, with the clip mixed in at at_s."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    bed = 0.5 * speechlike(seconds) + 0.4 * np.sin(2 * np.pi * 180 * t).astype(np.float32)
    i = int(at_s * SR)
    bed[i:i + len(clip)] += gain * clip
    return bed


def test_finds_the_clip_where_the_broadcast_plays_it():
    clip = speechlike(4.0)
    found = radio_air.find(clip, broadcast_with(clip, at_s=37.25, seconds=90))
    index, score, prominence = found
    assert abs(index / SR - 37.25) < 0.02
    assert score >= radio_air.MIN_SCORE and prominence >= radio_air.MIN_PROMINENCE


def test_no_match_when_the_broadcast_never_plays_it():
    clip = speechlike(4.0)
    other = speechlike(4.0)
    index, score, prominence = radio_air.find(clip, broadcast_with(other, at_s=20, seconds=90))
    assert not (score >= radio_air.MIN_SCORE and prominence >= radio_air.MIN_PROMINENCE)


def test_chunks_merge_close_clips():
    chunks = radio_air._chunks([100.0, 130.0, 2000.0], offset=10.0)
    assert len(chunks) == 2
    assert chunks[0][0] == 100.0 + 10 - radio_air.LOOK_BEFORE_S
    assert chunks[0][1] == 130.0 + 10 + radio_air.LOOK_AFTER_S


def test_clip_key():
    assert radio_air.clip_key({"t": 1234.5, "racing_number": "44"}) == "1234.5_44"
