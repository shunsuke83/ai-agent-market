from g2b.detail import _bidder_table


def test_negotiated_scores_are_not_shown_as_rates():
    html = _bidder_table({"tech_rate": 90.0, "price_rate": 10.0, "bidders": [
        {"rank": 1, "name": "에이", "amount_eok": 9.8, "rate_pct": 9.253},
        {"rank": 2, "name": "비", "amount_eok": 9.3, "rate_pct": 9.739},
    ]})
    assert "가격점수 (10점 만점)" in html and "9.253<" in html
    assert "%" not in html.split("<tbody>")[1].split("</tbody>")[0]
    assert ">투찰률<" not in html and "예정가격 대비" not in html
    assert "기술평가 90점과 가격평가 10점" in html


def test_price_bids_keep_rate_column():
    html = _bidder_table({"bidders": [{"rank": 1, "name": "에이", "amount_eok": 1.0, "rate_pct": 88.123}]})
    assert ">투찰률<" in html and "88.123%" in html and "가격점수" not in html
    assert _bidder_table({"bidders": []}) == ""
