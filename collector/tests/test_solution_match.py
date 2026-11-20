from g2b.solution_match import classify_engagement, match_solutions, notice_match_text


def test_match_ax_dev_environment():
    m = match_solutions("한국남동발전 AX서비스 개발환경 구축 용역")
    assert m["priority"] == "S"
    assert m["name"] in ("GenOS", "Code Assistant", "AI Agent 개발환경")


def test_ax_alone_does_not_match_s( ):
    # N-04
    m = match_solutions("AX-Ready 서버 및 서버보안 솔루션 구매")
    assert m["priority"] != "S"
    m2 = match_solutions("광주 AX 현장 전기안전 계측장치 구매")
    assert m2.get("priority") not in ("S", "A") or "AX" not in (m2.get("hits") or [])


def test_fields_label_not_in_match_text():
    # N-04: field label alone must not create a hit
    text = notice_match_text({"title": "일반 업무지원 시스템", "fields": ["AX·전략"], "nature": "ISP·전략"})
    assert "AX·전략" not in text
    assert match_solutions(text).get("priority") is None


def test_match_kotra_ops_has_weak_or_no_sa_build():
    title = "2027년 AI 무역지원센터 운영 용역"
    eng = classify_engagement(title, "운영·유지보수")
    assert eng["engagement"] == "ops"
    assert eng["ops_exception"] is None


def test_ops_with_platform_not_strong_build():
    # N-03: 플랫폼/유지보수 alone is not a strong ops exception
    eng = classify_engagement(
        "경기 생성형 AI 플랫폼 운영 및 유지보수 용역",
        "운영·유지보수",
    )
    assert eng["engagement"] == "ops"
    assert eng["ops_exception"] in (None, "weak")


def test_ops_with_summary_build_exception():
    summary = {
        "summary": {
            "requirements": ["신규 챗봇 시스템 구축 및 고도화"],
            "cautions": [],
            "evaluation": "",
        }
    }
    eng = classify_engagement("OO센터 운영 용역", "운영·유지보수", summary)
    assert eng["engagement"] == "ops"
    assert eng["ops_exception"] == "strong"


def test_infra_gpu_not_build():
    eng = classify_engagement("초고용량 GPU 서버 2TB 도입", "인프라")
    assert eng["engagement"] == "other"


def test_build_title_wins():
    eng = classify_engagement("생성형 AI 상담 플랫폼 구축", "시스템 구축·고도화")
    assert eng["engagement"] == "build"


def test_notice_match_text_title_and_summary_only():
    text = notice_match_text(
        {"title": "A", "nature": "B", "fields": ["생성형·LLM"]},
        {"summary": {"requirements": ["구축"], "cautions": [], "evaluation": ""}},
    )
    assert "생성형·LLM" not in text
    assert "구축" in text
