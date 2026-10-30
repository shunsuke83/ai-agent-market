import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.client import G2BClient, G2BError


def _ok_payload():
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "정상"},
            "body": {"items": {"item": []}, "totalCount": 0},
        }
    }


def test_get_retries_connect_timeout_then_succeeds():
    client = G2BClient(key="testkey", sleep_s=0, timeout=1, max_attempts=3)
    ok = MagicMock(status_code=200)
    ok.raise_for_status = MagicMock()
    ok.json = MagicMock(return_value=_ok_payload())
    with patch.object(
        client.session,
        "get",
        side_effect=[
            requests.exceptions.ConnectTimeout("connect timed out"),
            ok,
        ],
    ) as get:
        data = client._get("https://example.test/api", {"inqryDiv": "1"})
    assert data["response"]["header"]["resultCode"] == "00"
    assert get.call_count == 2


def _ok_response():
    ok = MagicMock(status_code=200)
    ok.raise_for_status = MagicMock()
    ok.json = MagicMock(return_value=_ok_payload())
    return ok


def test_get_passes_split_connect_read_timeout():
    client = G2BClient(key="testkey", sleep_s=0, timeout=90, connect_timeout=15, max_attempts=1)
    with patch.object(client.session, "get", return_value=_ok_response()) as get:
        client._get("https://example.test/api", {})
    assert get.call_args.kwargs["timeout"] == (15, 90)


def test_transport_error_redacts_pre_encoded_key():
    key = "abc%2Bsecret%3D%3D"
    client = G2BClient(key=key, sleep_s=0, timeout=1, max_attempts=1)
    err = requests.exceptions.ConnectTimeout(
        f"Max retries exceeded with url: /api?serviceKey={key}&type=json (Caused by timeout)"
    )
    with patch.object(client.session, "get", side_effect=err):
        with pytest.raises(G2BError) as exc:
            client._get("https://example.test/api", {})
    assert "secret" not in str(exc.value)
    assert "serviceKey=***" in str(exc.value)


def test_invalid_env_falls_back_to_defaults(monkeypatch):
    monkeypatch.setenv("G2B_HTTP_RETRIES", "many")
    monkeypatch.setenv("G2B_TIMEOUT", "slow")
    monkeypatch.setenv("G2B_CONNECT_TIMEOUT", "")
    client = G2BClient(key="testkey")
    assert client.max_attempts == 8
    assert client.timeout == 90.0
    assert client.connect_timeout == 15.0


def test_non_json_response_is_retried():
    bad = MagicMock(status_code=200, text="<html>gateway busy</html>")
    bad.raise_for_status = MagicMock()
    bad.json = MagicMock(side_effect=ValueError("not json"))
    client = G2BClient(key="testkey", sleep_s=0, timeout=1, max_attempts=3)
    with patch.object(client.session, "get", side_effect=[bad, _ok_response()]) as get:
        data = client._get("https://example.test/api", {})
    assert data["response"]["header"]["resultCode"] == "00"
    assert get.call_count == 2


def test_exhausted_error_keeps_429_status_after_mixed_failures():
    rate = MagicMock(status_code=429)
    client = G2BClient(key="testkey", sleep_s=0, timeout=1, max_attempts=2)
    with patch.object(
        client.session,
        "get",
        side_effect=[rate, requests.exceptions.ReadTimeout("read timed out")],
    ):
        with pytest.raises(G2BError) as exc:
            client._get("https://example.test/api", {})
    assert exc.value.status_code == 429


def test_get_exhausts_transport_retries():
    client = G2BClient(key="testkey", sleep_s=0, timeout=1, max_attempts=3)
    with patch.object(
        client.session,
        "get",
        side_effect=requests.exceptions.ConnectTimeout("connect timed out"),
    ):
        with pytest.raises(G2BError, match="retries exhausted"):
            client._get("https://example.test/api", {"inqryDiv": "1"})
