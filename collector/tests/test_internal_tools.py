from g2b.alerts import prespec_item
from g2b.classify import apply_summary_labels
from g2b.normalize import list_excluded
from g2b.pricing import budget_share


def test_summary_upgrades_title_only_ai_build():
    notice = {"title": "해양환경공단 KOEM AI 구축", "scope": "AI SW 확대", "fields": ["AI 일반"]}
    entry = {
        "status": "ok",
        "summary": {
            "overview": "LLMOps와 Agentic AI, 가드레일을 포함한 구축",
            "tasks": ["에이전트 운영"],
            "tech": ["LLMOps", "가드레일"],
        },
    }
    apply_summary_labels(notice, entry)
    assert notice["scope"] == "생성형·Agent"
    assert "AI 일반" not in notice["fields"]
    assert "생성형·LLM" in notice["fields"]
    assert "AI 에이전트" in notice["fields"]


def test_list_excludes_purchase_lease_and_its_maintenance():
    assert list_excluded({"title": "AI 학습용 GPU 서버 구매", "biz": "servc"})
    assert list_excluded({"title": "전산실 스토리지 도입", "biz": "servc"})
    assert list_excluded({"title": "ITS 유지관리 용역", "biz": "servc"})
    assert list_excluded({"title": "ChatGPT 라이선스 구매", "biz": "servc"})
    assert not list_excluded({"title": "생성형 AI 민원 상담 플랫폼 구축", "biz": "servc"})


def test_budget_share_uses_amount_over_budget():
    notice = {"budget_eok": 10}
    assert budget_share({"amount_eok": 8.5}, notice) == 85
    assert budget_share({"amount_eok": 1}, notice) is None


def test_prespec_alert_links_to_row():
    item = prespec_item({"prespec_no": "R26BD1", "title": "AI"}, "https://x/")
    assert item["url"] == "https://x/prespecs.html#p-R26BD1"
