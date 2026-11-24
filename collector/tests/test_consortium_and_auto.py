"""Phase-1: consortium edges + competitor auto-admit."""

from __future__ import annotations

import json
from pathlib import Path


def test_consortium_payload_multi_firm_and_xenon(tmp_path: Path, monkeypatch):
    from g2b import spa_export

    root = tmp_path
    (root / "data").mkdir()
    (root / "data" / "contracts.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {
                        "contract_no": "C1",
                        "title": "대형 SI 공동",
                        "org": "기관",
                        "amount_eok": 100.0,
                        "signed_date": "2026-01-01",
                        "firms": [
                            {"name": "삼성SDS", "role": "주계약업체", "share": 70, "bizno": "9999999999"},
                            {
                                "name": "엠티데이타",
                                "role": "도급업체",
                                "share": 30,
                                "bizno": "2118698485",  # listed (와이즈넛 bizno reused for listed flag)
                            },
                        ],
                    },
                    {
                        "contract_no": "C2",
                        "title": "제논 단독",
                        "org": "기관",
                        "amount_eok": 9.0,
                        "signed_date": "2026-02-01",
                        "firms": [
                            {
                                "name": "주식회사 제논",
                                "role": "주계약업체",
                                "share": 100,
                                "bizno": "7638101040",
                            }
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "data" / "run_status.json").write_text("{}", encoding="utf-8")
    # Minimal competitors config so listed bizno matches member
    cfg = root / "collector" / "config"
    cfg.mkdir(parents=True)
    # Point load_competitors_config at real config via monkeypatch of CONFIG path used inside.
    monkeypatch.setattr(
        "g2b.competitors.load_competitors_config",
        lambda path=None: [{"name": "와이즈넛", "bizno": "2118698485"}],
    )

    payload = spa_export._consortium_payload(root)
    assert payload["summary"]["multi_firm"] == 1
    assert payload["summary"]["large_joint"] == 1
    assert payload["summary"]["xenon_lead"] == 1
    assert payload["summary"]["xenon_member"] == 0
    assert payload["summary"]["external_lead_to_listed"] == 1
    assert any(e["lead_name"] == "삼성SDS" for e in payload["edges"])


def test_auto_admit_includes_high_award_winners(tmp_path: Path, monkeypatch):
    from g2b import competitors as comp

    root = tmp_path
    (root / "data").mkdir()
    (root / "data" / "notices.json").write_text(
        json.dumps(
            {
                "notices": [
                    {
                        "bid_no": "R1",
                        "bid_ord": "000",
                        "title": "A",
                        "org": "O",
                        "winner": "삼성에스디에스",
                        "award_amount_eok": 200.0,
                        "open_date": "2026-01-01",
                        "budget_eok": 220.0,
                        "bidders": [
                            {"rank": 1, "name": "삼성에스디에스", "bizno": "1010101010", "amount_eok": 200}
                        ],
                    },
                    {
                        "bid_no": "R2",
                        "bid_ord": "000",
                        "title": "B",
                        "org": "O",
                        "winner": "삼성에스디에스",
                        "award_amount_eok": 250.0,
                        "open_date": "2026-02-01",
                        "budget_eok": 260.0,
                        "bidders": [
                            {"rank": 1, "name": "삼성에스디에스", "bizno": "1010101010", "amount_eok": 250}
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "data" / "seed").mkdir()
    (root / "data" / "seed" / "editorial-2026-10-28.json").write_text("{}", encoding="utf-8")
    (root / "data" / "firms.json").write_text("{}", encoding="utf-8")
    (root / "data" / "run_status.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(comp, "load_competitors_config", lambda path=None: [])
    monkeypatch.setattr(comp, "load_competitors_analysis", lambda: {})
    monkeypatch.setattr(comp, "load_firms", lambda _r: {})
    monkeypatch.setattr(
        "g2b.render.load_run_status",
        lambda _r: {},
    )
    monkeypatch.setattr("g2b.render.stamp_text", lambda *_a, **_k: "stamp")

    payload = comp.build_spa_competitors(root)
    names = {f["name"] for f in payload["firms"]}
    assert any("삼성" in n for n in names)
    auto = [f for f in payload["firms"] if f.get("group") == "auto"]
    assert auto
    assert payload["summary"]["auto"] >= 1


def test_normalize_bidder_keeps_price_and_tech_scores():
    from g2b.normalize import normalize_bidder_item

    row = normalize_bidder_item(
        {
            "prcbdrNm": "제논",
            "opengRank": "1",
            "bidprcAmt": "100000000",
            "bidprcrt": "",
            "bidPrceEvlVal": "9.25",
            "techEvlVal": "88.5",
            "totalEvlAmtVal": "97.75",
            "prcbdrBizno": "7638101040",
        }
    )
    assert row is not None
    assert row["price_score"] == 9.25
    assert row["tech_score"] == 88.5
    assert row["total_score"] == 97.75
    assert row["rate_pct"] == 9.25  # legacy fill when bidprcrt empty
