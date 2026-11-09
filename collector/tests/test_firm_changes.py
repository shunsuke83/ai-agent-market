from g2b.alerts import firm_change_items, firm_change_text
from g2b.bidders import build_bidder_index
from g2b.firms import firm_changes, merge_firm_record, public_change_text

OLD = {"corp_name": "에이", "ceo": "김대표", "region": "서울특별시 강남구", "employees": 100, "biz_div": "용역",
       "changes": [{"date": "2026-10-01", "field": "hq_div", "label": "본사 구분", "from": "지사", "to": "본사"}]}


def test_firm_changes_tracks_fields_and_large_employee_moves():
    new = {**OLD, "ceo": "이대표", "region": "", "employees": 105, "biz_div": "용역,공사"}
    got = firm_changes(OLD, new, "2026-11-16")
    assert [c["field"] for c in got] == ["ceo", "biz_div"]  # blank region and +5명 ignored
    assert firm_changes(None, new, "2026-11-16") == []
    assert firm_changes(OLD, {**OLD, "employees": 130}, "d")[0]["label"] == "종업원 수"

    merged = merge_firm_record(OLD, new, "2026-11-16")
    assert [c["date"] for c in merged["changes"]] == ["2026-11-16", "2026-11-16", "2026-10-01"]
    assert merged["region"] == "서울특별시 강남구"
    assert "changes" not in merge_firm_record(None, new, "2026-11-16")


def test_public_text_hides_ceo_names_and_slack_shows_them():
    ceo = {"date": "2026-11-16", "field": "ceo", "label": "대표자", "from": "김대표", "to": "이대표"}
    assert public_change_text(ceo) == "대표자 변경"
    firms = {"1111111111": {"corp_name": "에이", "changes": [ceo, OLD["changes"][0]]}}
    items = firm_change_items(firms, {}, "2026-11-10")
    assert [i["field"] for i in items] == ["ceo"]
    assert firm_change_items(firms, {items[0]["key"]: "2026-11-16"}, "2026-11-10") == []
    text = firm_change_text(items, "https://x/", 15)
    assert "bidders.html#1111111111|에이" in text and "김대표 → 이대표" in text

    idx = build_bidder_index(
        [{"bid_no": "R1", "open_date": "2026-11-01", "bidders": [{"rank": 1, "name": "에이", "bizno": "1111111111"}]}],
        firms,
    )
    assert idx["firms"]["1111111111"][3][0] == ["2026-11-16", "대표자 변경"]
    assert "김대표" not in str(idx)
