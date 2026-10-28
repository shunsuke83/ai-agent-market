import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.extract_html import bootstrap_all, extract_band_notices, extract_large_awards

ROOT = Path(__file__).resolve().parents[2]


def test_extract_band_has_rows():
    rows = extract_band_notices(ROOT)
    assert len(rows) >= 400
    sample = next(r for r in rows if r.get("bid_no"))
    assert sample["title"]
    assert sample["scope"] in ("생성형·Agent", "AI SW 확대")
    assert sample["budget_eok"] is not None


def test_extract_awards():
    rows = extract_large_awards(ROOT)
    assert len(rows) >= 50
    assert rows[0]["winner"]


def test_bootstrap_payload():
    payload = bootstrap_all(ROOT)
    assert payload["schema_version"] == 1
    assert len(payload["competitors_overview"]) == 23
