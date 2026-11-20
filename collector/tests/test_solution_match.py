from g2b.solution_match import classify_engagement, match_solutions, notice_match_text


def test_match_ax_dev_environment():
    m = match_solutions("한국남동발전 AX서비스 개발환경 구축 용역")
    assert m["priority"] == "S"
    assert m["name"] in ("GenOS", "Code Assistant", "AI Agent 개발환경")


def test_match_kotra_ops_has_weak_or_no_sa_build():
    title = "2027년 AI 무역지원센터 운영 용역"
    eng = classify_engagement(title, "운영·유지보수")
    assert eng["engagement"] == "ops"
    assert eng["ops_exception"] is None


def test_ops_with_summary_build_exception():
    summary = {"summary": {"requirements": ["신규 챗봇 시스템 구축 및 고도화"], "cautions": [], "evaluation": ""}}
    eng = classify_engagement("OO센터 운영 용역", "운영·유지보수", summary)
    assert eng["engagement"] == "ops"
    assert eng["ops_exception"] == "strong"


def test_build_title_wins():
    eng = classify_engagement("생성형 AI 상담 플랫폼 구축", "시스템 구축·고도화")
    assert eng["engagement"] == "build"


def test_notice_match_text_includes_fields():
    text = notice_match_text({"title": "A", "nature": "B", "fields": ["생성형·LLM"]})
    assert "생성형·LLM" in text
