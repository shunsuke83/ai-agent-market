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


def test_get_exhausts_transport_retries():
    client = G2BClient(key="testkey", sleep_s=0, timeout=1, max_attempts=3)
    with patch.object(
        client.session,
        "get",
        side_effect=requests.exceptions.ConnectTimeout("connect timed out"),
    ):
        with pytest.raises(G2BError, match="retries exhausted"):
            client._get("https://example.test/api", {"inqryDiv": "1"})
