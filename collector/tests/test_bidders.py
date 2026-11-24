import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.normalize import apply_bidders_to_notice, normalize_bidder_item
from g2b.render import aggregate_frequent_bidders, render_frequent_bidder_row


def test_normalize_bidder_item():
    row = normalize_bidder_item(
        {
            "opengRank": "2",
            "prcbdrNm": "(주)테스트소프트",
            "bidprcAmt": "19150000",
            "bidprcrt": "94.641",
            "prcbdrBizno": "123",
        }
    )
    assert row is not None
    assert row["rank"] == 2
    assert row["name"] == "테스트소프트"
    assert row["amount_eok"] == 0.1915
    assert abs(row["rate_pct"] - 94.641) < 0.01


def test_apply_bidders_sets_second():
    notice = {"bid_no": "R1", "bid_ord": "000", "title": "AI 구축"}
    raw = [
        {"opengRank": "1", "prcbdrNm": "일등", "bidprcAmt": "100000000"},
        {"opengRank": "2", "prcbdrNm": "이등", "bidprcAmt": "110000000"},
    ]
    merged = apply_bidders_to_notice(notice, raw)
    assert len(merged["bidders"]) == 2
    assert merged["second"] == "이등"
    assert merged.get("winner") is None  # 개찰 1순위 is not a confirmed award
    assert merged["first_rank"] == "일등"
    assert merged["bid_count"] == 2


def test_aggregate_frequent_bidders():
    notices = []
    for i in range(3):
        notices.append(
            {
                "bid_no": f"R{i}",
                "bid_ord": "000",
                "title": "생성형 AI 플랫폼 구축",
                "winner": "알파" if i == 0 else "베타",
                "bidders": [
                    {"rank": 1, "name": "알파"},
                    {"rank": 2, "name": "감마"},
                ],
            }
        )
    # 알파 bids 3, wins 1; 감마 bids 3, wins 0
    ranked = aggregate_frequent_bidders(notices, min_bids=3, limit=10, build_only=True)
    by = {n: (b, w, r) for n, b, w, r in ranked}
    assert by["알파"][0] == 3
    assert by["알파"][1] == 1
    assert by["감마"][0] == 3
    assert by["감마"][1] == 0


def test_render_frequent_row():
    html = render_frequent_bidder_row("테스트", 5, 2, 40.0)
    assert "테스트" in html
    assert 'class="num">5</td>' in html
    assert "40%" in html


def test_spa_bidders_index_counts_wins_by_notice_winner(tmp_path: Path):
    """hist[0] is notice index, not a win flag — wins follow notice[5] == bizno."""
    from g2b.spa_export import _bidders_index

    root = tmp_path
    (root / "data").mkdir()
    payload = {
        "notices": [
            # [open_date, org, title, budget, href, winner_bizno, status]
            ["2026-01-01", "기관", "A", 10.0, "bids/a.html", "1111111111", "낙찰"],
            ["2026-01-02", "기관", "B", 20.0, "bids/b.html", "2222222222", "낙찰"],
            ["2026-01-03", "기관", "C", 3.0, "bids/c.html", "", "1순위"],
        ],
        "firms": {
            # rate 9.5 is price-score noise; avg_win_rate must use amount/budget → 95%
            "1111111111": ["알파", "서울", [[0, 1, 9.5, 9.5], [1, 2, 90.0, 1.8], [2, 1, 88.0, None]]],
            "2222222222": ["베타", "부산", [[1, 1, 92.0, 18.4]]],
        },
    }
    (root / "data" / "bidders.json").write_text(
        __import__("json").dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    rows = {r["bizno"]: r for r in _bidders_index(root)}
    assert rows["1111111111"]["bids"] == 3
    assert rows["1111111111"]["wins"] == 1
    assert rows["1111111111"]["avg_win_rate"] == 95.0
    assert rows["2222222222"]["wins"] == 1
    assert rows["2222222222"]["avg_win_rate"] == 92.0
