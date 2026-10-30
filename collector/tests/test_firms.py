from g2b.client import G2BClient, G2BError
from g2b.competitors import (
    build_alias_index,
    build_bizno_index,
    count_live_bids,
    outside_rivals,
    update_rivals_line,
)
from g2b.firms import bidder_stats, fmt_bizno, normalize_corp_item, short_region, winner_bizno


def test_short_region():
    assert short_region("서울특별시 영등포구 당산동3가") == "서울 영등포구"
    assert short_region("경기도 성남시 분당구") == "경기 성남시"
    assert short_region("경상북도 포항시") == "경북 포항시"
    assert short_region("세종특별자치시") == "세종"

COMPS = [
    {"name": "가회사", "bizno": "111-11-11111", "aliases": ["가회사"]},
    {"name": "나회사", "bizno": "2222222222", "aliases": ["나회사"]},
]


def _notice(no, bidders, winner=None):
    return {
        "bid_no": no,
        "bid_ord": "000",
        "open_date": "2026-05-01",
        "winner": winner,
        "bidders": [
            {"name": n, "bizno": b, "rank": r} for n, b, r in bidders
        ],
    }


NOTICES = [
    _notice("A", [("(주)가회사", "1111111111", 1), ("나회사", "2222222222", 2), ("다회사", "3333333333", 3)], "가회사"),
    _notice("B", [("나회사", "2222222222", 1), ("다회사", "3333333333", 2), ("가회사", "1111111111", 3)]),
]


def test_bidder_stats_head_to_head():
    s = bidder_stats(NOTICES)
    a = s["1111111111"]
    assert len(a.bids) == 2 and a.wins == {"A-000"} and not a.firsts
    assert a.faced["2222222222"] == 2
    assert (a.beat["2222222222"], a.lost["2222222222"]) == (1, 1)
    assert s["2222222222"].firsts == {"B-000"}
    assert winner_bizno(NOTICES[0]) == "1111111111"


def test_bizno_match_ignores_same_named_firm():
    rows = [_notice("C", [("가회사", "9999999999", 1)])]
    idx = build_bizno_index(COMPS)
    bids = count_live_bids(rows, [], build_alias_index(COMPS), {"가회사", "나회사"}, idx)
    assert bids["가회사"] == set()
    legacy = [{"bid_no": "D", "bidders": [{"name": "가회사"}]}]
    bids = count_live_bids(legacy, [], build_alias_index(COMPS), {"가회사", "나회사"}, idx)
    assert bids["가회사"] == {"D-000"}


def test_outside_rivals_lists_unlisted_bidders():
    rows = outside_rivals(bidder_stats(NOTICES), build_bizno_index(COMPS))
    assert [s.bizno for s, _ in rows] == ["3333333333"]
    assert rows[0][1] == {"가회사": 2, "나회사": 2}


PAGE = (
    '<details class="co" id="c-가회사"><summary><b>가회사</b></summary>'
    "<div><h4>나라장터 실적 (AI 사업 공고)</h4><p>수집 확인: 투찰 2건</p>\n"
    '<p class="meta">자주 맞붙은 업체: 옛회사</p><ul class="plain"></ul></div></details>'
    '<details class="co" id="c-라회사"><summary><b>라회사</b></summary>'
    "<div><h4>나라장터 실적 (AI 사업 공고)</h4><p>수집 확인</p>\n"
    '<p class="meta">자주 맞붙은 업체: 옛상대</p><ul class="plain"></ul></div></details>'
)


def test_rivals_line_replaces_editorial_and_is_idempotent():
    stats = bidder_stats(NOTICES)
    firms = {"1111111111": {"region": "서울", "employees": 120, "opened": "2001-03-02"}}
    idx = build_bizno_index(COMPS)
    once = update_rivals_line(PAGE, "가회사", "1111111111", stats, firms, idx)
    assert "사업자번호 111-11-11111 · 서울 · 종업원 120명 · 개업 2001" in once
    assert "나회사 2회(앞섬 1·뒤짐 1)" in once
    assert "옛회사" not in once
    assert update_rivals_line(once, "가회사", "1111111111", stats, firms, idx) == once
    # No bidder data: keep the editorial rivals, add the bizno.
    other = update_rivals_line(once, "라회사", "4444444444", stats, {}, idx)
    assert "사업자번호 444-44-44444<br>자주 맞붙은 업체: 옛상대" in other
    assert update_rivals_line(other, "라회사", "4444444444", stats, {}, idx) == other


def test_normalize_corp_item():
    r = normalize_corp_item(
        {"bizno": "229-81-37316", "corpNm": "(주)코난테크놀로지", "rgnNm": "서울특별시",
         "opbizDt": "19990801", "emplyeNum": "194"}
    )
    assert r["bizno"] == "2298137316" and r["opened"] == "1999-08-01" and r["employees"] == 194
    assert fmt_bizno("2298137316") == "229-81-37316"


def test_fetch_corp_basic_falls_back_to_inqrydiv_1(monkeypatch):
    client = G2BClient.__new__(G2BClient)
    calls = []

    def fake_get(url, params):
        calls.append(params["inqryDiv"])
        if params["inqryDiv"] == "3":
            raise G2BError("API error 08: bad inqryDiv")
        return {"response": {"body": {"items": [{"bizno": "2298137316", "corpNm": "코난"}]}}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert client.fetch_corp_basic("2298137316")["corpNm"] == "코난"
    assert calls == ["3", "1"]
