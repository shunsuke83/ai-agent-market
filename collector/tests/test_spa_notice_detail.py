"""SPA notice slim keeps win rate / g2b / bidders for detail UI."""

from __future__ import annotations

import json
from pathlib import Path


def test_slim_notice_fills_g2b_win_rate_and_bidders(tmp_path: Path, monkeypatch):
    from g2b import spa_export

    root = tmp_path
    (root / "data").mkdir()
    (root / "data" / "notices.json").write_text(
        json.dumps(
            {
                "notices": [
                    {
                        "bid_no": "R25BK01123269",
                        "bid_ord": "000",
                        "title": "가스안전 AI",
                        "org": "한국가스안전공사",
                        "budget_eok": 8.1,
                        "notice_date": "2025-10-30",
                        "open_date": "2025-11-25",
                        "winner": "코난테크놀로지",
                        "award_amount_eok": 7.93,
                        "award_to_budget_pct": 97.9,
                        "second": "와이즈넛",
                        "status": "낙찰",
                        "bid_count": 6,
                        "bidders": [
                            {"rank": 1, "name": "코난테크놀로지", "amount_eok": 7.93, "rate_pct": 8.5},
                            {"rank": 2, "name": "와이즈넛", "amount_eok": 8.0, "rate_pct": 8.0},
                        ],
                        "source": "bootstrap",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "data" / "seed").mkdir()
    (root / "data" / "seed" / "editorial-2026-10-28.json").write_text(
        json.dumps(
            {
                "band_notices": [
                    {
                        "bid_no": "R25BK01123269",
                        "bid_ord": "000",
                        "g2b_url": "https://www.g2b.go.kr/seed-url",
                        "win_rate_pct": 98.0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Empty run status / profile / summaries so scoring stays optional.
    (root / "data" / "run_status.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(spa_export, "load_profile", lambda: None)
    monkeypatch.setattr(spa_export, "load_summaries", lambda _root: {})
    monkeypatch.setattr(spa_export, "load_keywords", lambda: {})

    payload = spa_export.build_spa_payload(root)
    row = payload["notices"]["notices"][0]
    assert row["id"] == "R25BK01123269-000"
    assert row["g2b_url"] == "https://www.g2b.go.kr/seed-url"
    assert row["win_rate_pct"] == 98.0
    assert row["award_to_budget_pct"] == 97.9
    assert row["second"] == "와이즈넛"
    assert row["status"] == "낙찰"
    assert len(row["bidders"]) == 2


def test_g2b_url_synthesized_without_seed():
    from g2b.spa_export import _g2b_url, _win_rate_pct

    assert _g2b_url({"bid_no": "R1", "bid_ord": "1"}).endswith("bidPbancNo=R1&bidPbancOrd=001")
    assert _win_rate_pct({"award_to_budget_pct": 97.9}) == 97.9
    assert _win_rate_pct({"win_rate_pct": 88, "award_to_budget_pct": 97.9}) == 88.0
