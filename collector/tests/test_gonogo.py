from datetime import date, datetime

import yaml

from g2b.gonogo import GO, NO_GO, REVIEW, IncumbentIndex, candidates, score_notice, similarity, slack_text
from g2b.render import KST
from g2b.gonogo import PROFILE_LOCAL

NOW = datetime(2026, 11, 1, 13, 0, tzinfo=KST)
PROFILE = yaml.safe_load((PROFILE_LOCAL.parent / "profile.example.yaml").read_text(encoding="utf-8"))

NOTICE = {
    "bid_no": "R26BK00000001",
    "bid_ord": "000",
    "title": "생성형 AI 기반 민원 상담 챗봇 구축",
    "org": "테스트청",
    "scope": "생성형·Agent",
    "nature": "시스템 구축·고도화",
    "budget_eok": 9.0,
    "notice_date": "2026-11-01",
    "close_at": "2026-11-20 10:00",
    "tech_rate": 90.0,
    "price_rate": 10.0,
}


def test_good_fit_is_go():
    s = score_notice(NOTICE, PROFILE, NOW, {"basis": "같은 기관", "median_bids": 3, "regulars": []})
    assert s["verdict"] == GO and s["score"] >= 85
    assert any("챗봇" in r for r in s["reasons"])


def test_hard_stops():
    assert score_notice({**NOTICE, "title": "지능형 CCTV 구축"}, PROFILE, NOW)["verdict"] == NO_GO
    assert score_notice({**NOTICE, "nature": "인프라"}, PROFILE, NOW)["verdict"] == NO_GO
    assert score_notice({**NOTICE, "budget_eok": 80.0}, PROFILE, NOW)["verdict"] == NO_GO
    s = score_notice({**NOTICE, "close_at": "2026-11-01 10:00"}, PROFILE, NOW)
    assert s["verdict"] == NO_GO and "입찰 마감 지남" in s["reasons"]


def test_weaker_fit_scores_lower():
    base = score_notice(NOTICE, PROFILE, NOW)["score"]
    crowded = score_notice(NOTICE, PROFILE, NOW, {"basis": "같은 기관", "median_bids": 25, "regulars": []})
    rushed = score_notice({**NOTICE, "close_at": "2026-11-04 10:00"}, PROFILE, NOW)
    upkeep = score_notice({**NOTICE, "title": "민원 시스템 유지보수", "nature": "운영·유지보수"}, PROFILE, NOW)
    assert crowded["score"] < base and rushed["score"] < base and upkeep["score"] < base
    assert upkeep["verdict"] in (REVIEW, NO_GO)


def test_rival_and_incumbent_signals():
    profile = {**PROFILE, "rivals": ["(주)경쟁사"], "name": "우리회사"}
    ctx = {"basis": "같은 기관", "median_bids": 3, "regulars": [("주식회사 경쟁사", 3)]}
    base = score_notice(NOTICE, profile, NOW, {**ctx, "regulars": []})["score"]
    assert score_notice(NOTICE, profile, NOW, ctx)["score"] < base
    other = {"firms": [{"name": "남의회사"}], "signed_date": "2025-03-01"}
    ours = {"firms": [{"name": "우리회사 주식회사"}], "signed_date": "2025-03-01"}
    assert score_notice(NOTICE, profile, NOW, None, other)["score"] < score_notice(NOTICE, profile, NOW, None, ours)["score"]


def test_incumbent_index_matches_similar_titles_only():
    contracts = [
        {"org": "테스트청", "title": "2025년 민원 상담 챗봇 고도화", "signed_date": "2025-04-01", "firms": []},
        {"org": "테스트청", "title": "청사 보안 관제 용역", "signed_date": "2025-04-01", "firms": []},
        {"org": "다른청", "title": "민원 상담 챗봇", "signed_date": "2025-04-01", "firms": []},
    ]
    found = IncumbentIndex(contracts, date(2026, 11, 1)).find(NOTICE)
    assert found["title"] == "2025년 민원 상담 챗봇 고도화"
    assert similarity("2026년 A 챗봇 구축", "2027년 A 챗봇 구축") == 1.0


def test_candidates_open_recent_latest_ord():
    rows = [
        NOTICE,
        {**NOTICE, "bid_ord": "001"},
        {**NOTICE, "bid_no": "OLD", "notice_date": "2026-10-20"},
        {**NOTICE, "bid_no": "CLOSED", "close_at": "2026-11-01 10:00"},
        {**NOTICE, "bid_no": "CANCEL", "ntce_kind": "취소공고"},
    ]
    got = candidates(rows, NOW, 1)
    assert [(n["bid_no"], n["bid_ord"]) for n in got] == [("R26BK00000001", "001")]


def test_slack_text_links_detail_page():
    s = score_notice(NOTICE, PROFILE, NOW)
    text = slack_text([(NOTICE, s)], NOW.date(), "https://x/", 5)
    assert "https://x/bids/R26BK00000001-000.html" in text and f"{s['score']}점" in text


def test_pipeline_bids_are_skipped(tmp_path):
    import json

    from g2b.gonogo import run_gonogo

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "notices.json").write_text(json.dumps({"notices": [NOTICE]}), encoding="utf-8")
    base = run_gonogo(tmp_path, days=3, now=NOW, webhook="", profile=PROFILE)
    assert base["candidates"] == 1
    busy = {**PROFILE, "pipeline": [{"bid_no": NOTICE["bid_no"] + "-000", "status": "제안서 작성 중"}]}
    assert run_gonogo(tmp_path, days=3, now=NOW, webhook="", profile=busy)["candidates"] == 0


def test_missing_summaries_are_made_for_slack_only(tmp_path, monkeypatch):
    import json

    from g2b import gonogo, rfp

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "notices.json").write_text(json.dumps({"notices": [NOTICE]}), encoding="utf-8")
    calls = []

    def fake(n, prespecs, key, session=None):
        calls.append(n["bid_no"])
        return {"bid_no": n["bid_no"], "status": "ok", "summary": {"overview": "온디맨드 개요"}, "fields": {}}

    monkeypatch.setattr(rfp, "summarize_notice", fake)
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a))))
    out = gonogo.run_gonogo(tmp_path, days=3, now=NOW, dry_run=True, profile=PROFILE, gemini_key="K")
    assert calls == [NOTICE["bid_no"]] and out["summarized"] == 1
    assert "요약: 온디맨드 개요" in printed[0]
    assert not (tmp_path / "data" / "rfp_summaries.json").exists()
    assert gonogo.run_gonogo(tmp_path, days=3, now=NOW, dry_run=True, profile=PROFILE, gemini_key="")["summarized"] == 0
