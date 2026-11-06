from datetime import datetime

from g2b import gonogo_policy as gp
from g2b.render import KST

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=KST)  # Monday

PROFILE = {
    "version": 1,
    "company": {
        "name": "주식회사 테스트",
        "aliases": ["테스트"],
        "bizno": "1234567890",
        "hq_region": "서울특별시 중구",
        "products": [{"name": "TestOS (테스토스)"}],
        "certifications": [{"name": "GS인증 1등급"}],
        "todo_qualifications": {"sw_business_registration": True, "sme_certificate": None, "csap": None},
    },
    "capabilities": {
        "core_fields": ["생성형·LLM"],
        "adjacent_fields": ["데이터·예측"],
        "other_fields": ["비전·영상"],
        "title_keywords": {"strong": ["LLM", "챗봇"], "medium": ["예측 모델"]},
    },
    "track_record": {
        "largest_g2b_contract_eok": 9.8,
        "non_g2b_amounts_eok": None,
        "own_customers": ["한국남동발전"],
        "observations": ["관측 메모"],
    },
    "policy": {
        "budget": {
            "min_eok": 3,
            "tiers": [
                {"range": [3, 8], "label": "소규모", "default": "REVIEW"},
                {"range": [8, 15], "label": "주력", "default": "GO 후보"},
                {"range": [15, 30], "label": "도전", "default": "REVIEW"},
                {"range": [30, None], "label": "대형", "default": "REVIEW"},
            ],
        },
        "avoid": [
            {"id": "hw", "desc": "HW 중심", "signals": {"nature": ["인프라"], "title_keywords": ["GPU", "서버 구매"]},
             "exception": "SW가 주 과업이면 REVIEW"},
            {"id": "maint", "desc": "타사 유지보수", "signals": {"nature": ["운영·유지보수"]},
             "exception": "기존 고객이거나 고도화면 REVIEW"},
        ],
        "isp_strategy": {"required_checks": ["후속 사업 참여 제한 조항"]},
    },
    "hard_gates": [
        {"id": "region"}, {"id": "eligibility"}, {"id": "track_record_amount"}, {"id": "certification"},
        {"id": "schedule", "min_business_days_to_deadline": None}, {"id": "capacity", "max_concurrent_builds": None},
    ],
    "scoring": {
        "weights": {"tech_fit": 30, "similar_track_record": 25, "staffing_schedule": 20, "budget_fit": 15, "domain_org": 10},
        "thresholds": {"go": {"min_score": 70, "min_evidence_ratio": 0.8}, "no_go": {"max_score": 40}},
    },
}


def _notice(**kw):
    n = {"bid_no": "R26BK1", "title": "생성형 AI LLM 챗봇 구축", "org": "한국가스공사", "budget_eok": 10.0,
         "fields": ["생성형·LLM"], "nature": "시스템 구축·고도화", "close_at": "2026-11-20 10:00"}
    n.update(kw)
    return n


def _summary(*requirements):
    return {"summary": {"requirements": list(requirements), "cautions": [], "evaluation": ""}}


def test_detects_policy_profile():
    assert gp.is_policy_profile(PROFILE)
    assert not gp.is_policy_profile({"name": "x", "natures": {}})


def test_go_in_core_tier_with_enough_evidence():
    s = gp.score_policy(_notice(), PROFILE, NOW)
    assert s["verdict"] == gp.GO
    assert s["evidence"] == 0.8  # staffing_schedule left out (todo values are null)
    assert s["score"] >= 70


def test_budget_tier_default_review_and_min_budget():
    assert gp.score_policy(_notice(budget_eok=5.0), PROFILE, NOW)["verdict"] == gp.REVIEW
    assert gp.score_policy(_notice(budget_eok=2.0), PROFILE, NOW)["verdict"] == gp.NO_GO
    own = gp.score_policy(_notice(budget_eok=2.0, org="한국남동발전(주)"), PROFILE, NOW)
    assert own["verdict"] == gp.REVIEW
    unknown = gp.score_policy(_notice(budget_eok=None), PROFILE, NOW)
    assert unknown["verdict"] == gp.REVIEW and unknown["evidence"] < 0.8
    assert unknown["reasons"][0].startswith("추가 확인 필요")


def test_avoid_rules_and_exceptions():
    hw = gp.score_policy(_notice(title="AI 감사시스템 구축 GPU 서버 구매", nature="인프라"), PROFILE, NOW)
    assert hw["verdict"] == gp.NO_GO
    maint = gp.score_policy(_notice(title="AI 챗봇 운영 및 유지보수", nature="운영·유지보수"), PROFILE, NOW)
    assert maint["verdict"] == gp.NO_GO
    upgrade = gp.score_policy(_notice(title="AI 챗봇 고도화 및 유지보수", nature="운영·유지보수"), PROFILE, NOW)
    assert upgrade["verdict"] == gp.REVIEW
    own = gp.score_policy(_notice(title="AI 챗봇 운영", nature="운영·유지보수", org="한국남동발전(주)"), PROFILE, NOW)
    assert own["verdict"] == gp.REVIEW
    audit = gp.score_policy(_notice(title="AI 챗봇 구축 사업 위탁감리"), PROFILE, NOW)
    assert audit["verdict"] == gp.NO_GO


def test_gates_from_rfp_summary():
    seoul = gp.judge_gates(_notice(), PROFILE, NOW, _summary("서울특별시 소재 업체"))
    assert ("지역", gp.PASS, "서울 소재 제한") in seoul
    busan = gp.score_policy(_notice(), PROFILE, NOW, summary=_summary("부산광역시에 소재한 업체"))
    assert busan["verdict"] == gp.NO_GO
    sme = gp.score_policy(_notice(), PROFILE, NOW, summary=_summary("소프트웨어사업자", "중소기업 확인서 소지"))
    assert ("자격", gp.UNKNOWN, "중소기업 확인서") in sme["gates"]
    assert sme["verdict"] == gp.REVIEW
    record = gp.judge_gates(_notice(), PROFILE, NOW, _summary("최근 3년 단일 실적 15억 이상"))
    assert record == [("실적 금액", gp.UNKNOWN, "요건 15억 > 나라장터 실적 9.8억")]
    cert = gp.judge_gates(_notice(), PROFILE, NOW, _summary("GS인증 제품", "CSAP 인증 필요"))
    assert ("인증", gp.UNKNOWN, "CSAP") in cert and ("인증", gp.PASS, "GS인증") in cert
    assert gp.judge_gates(_notice(industry_limit=True), PROFILE, NOW, None) == [
        ("자격", gp.UNKNOWN, "업종 제한 — 공고서 확인")
    ]


def test_industry_codes_direct_production_and_credit():
    company = {
        **PROFILE["company"],
        "g2b_industry_codes": ["1468", "1426"],
        "g2b_items_without_direct_production": ["정보시스템개발서비스"],
        "todo_qualifications": {"direct_production_cert": {"빅데이터분석서비스": "2027-03-09",
                                                           "정보시스템유지관리서비스": "2026-01-31"}},
        "credit_rating": {"valid_until": "2026-04-13"},
    }
    profile = {**PROFILE, "company": company}

    def gate(*reqs):
        return [g for g in gp.judge_gates(_notice(), profile, NOW, _summary(*reqs)) if g[0] == "자격"]

    assert gate("업종코드 1468 또는 1426 등록 업체")[0][1] == gp.PASS
    assert gate("학술연구용역(업종코드 1169) 등록, 2025년 기준")[0][1] == gp.FAIL
    assert gate("소프트웨어사업자(업종코드 1468) 등록", "정보통신공사업자 등록 업체")[0] == ("자격", gp.FAIL, "업종 0036")
    assert gate("정보통신공사업(0036) 및 소프트웨어사업자(1468) 등록업체")[0] == ("자격", gp.FAIL, "업종 0036")
    assert gate("정보통신공사업(0036) 또는 소프트웨어사업자(1468) 등록업체")[0][1] == gp.PASS
    assert gate("정보통신공사업법에 따른 시공 기준 등록 준수") == []
    profile["company"] = {**company, "g2b_registrable_codes": ["0036"]}
    assert gate("정보통신공사업(0036) 및 소프트웨어사업자(1468) 등록업체")[0] == (
        "자격", gp.UNKNOWN, "업종 0036 — 면허 보유, 나라장터 업종 등록 필요")
    assert gate("직접생산확인증명서(빅데이터 분석 서비스) 소지")[0][1] == gp.PASS
    assert gate("직접생산확인증명서(정보시스템유지관리서비스) 소지")[0][1] == gp.FAIL
    assert gate("직접생산확인(정보시스템개발서비스) 필수")[0] == ("자격", gp.FAIL, "직접생산확인 없음(정보시스템개발서비스)")
    assert gate("직접생산확인증명서 소지")[0][1] == gp.UNKNOWN
    assert "갱신 필요" in gp.credit_warning(profile, NOW.date())
    assert gp.credit_warning(PROFILE, NOW.date()) == ""


def test_schedule_gate_when_configured():
    profile = {**PROFILE, "hard_gates": [{"id": "schedule", "min_business_days_to_deadline": 10}]}
    gates = gp.judge_gates(_notice(close_at="2026-11-06 10:00"), profile, NOW, None)
    assert gates == [("일정", gp.FAIL, "마감까지 영업일 4일")]
    assert gp.business_days_until(NOW, "2026-11-09 10:00") == 5


def test_incumbent_by_bizno_and_org_kind():
    inc = {"firms": [{"name": "다른이름", "bizno": "123-45-67890"}], "signed_date": "2025-01-01"}
    assert "자사 기존 수행" in gp.score_policy(_notice(), PROFILE, NOW, incumbent=inc)["reasons"]
    assert gp.org_kind("서울특별시") == "지자체·교육"
    assert gp.org_kind("한국가스공사") == "공기업·준정부기관"
    assert gp.org_kind("행정안전부") == "중앙부처"


def test_slack_text_policy_has_no_probability_wording():
    n = _notice()
    s = gp.score_policy(n, PROFILE, NOW)
    text = gp.slack_text_policy([(n, s)], NOW.date(), "https://x/", 3, PROFILE, {})
    assert "GO" in text and "근거 80%" in text and "관측 메모" in text
    assert "수주 확률이 아닙니다" in text and "확률:" not in text
