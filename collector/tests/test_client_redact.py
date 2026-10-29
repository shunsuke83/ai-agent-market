import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.client import redact_secrets


def test_redact_service_key_in_url():
    raw = (
        "https://apis.data.go.kr/x?inqryDiv=1&serviceKey=abc123secret&type=json"
    )
    out = redact_secrets(raw)
    assert "abc123secret" not in out
    assert "serviceKey=***" in out


def test_redact_empty():
    assert redact_secrets(None) == ""
    assert redact_secrets("") == ""
