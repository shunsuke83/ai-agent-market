from g2b.alerts import prespec_item
from g2b.classify import apply_summary_labels
from g2b.normalize import exclude_reason_summary, list_exclude_reason, list_excluded
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


def test_list_exclude_reason_labels_and_summary():
    gpu = {"title": "AI 학습용 GPU 서버 구매", "biz": "servc"}
    its = {"title": "지능형교통 시스템 유지", "biz": "servc"}
    edu = {"title": "AI 교육 과정 운영 용역", "biz": "servc", "nature": "연구·교육·행사"}
    keep = {"title": "생성형 AI 민원 상담 플랫폼 구축", "biz": "servc"}
    assert list_exclude_reason(gpu) == "GPU"
    assert list_exclude_reason(its) == "교통·ITS"
    assert list_exclude_reason(edu) == "교육·행사·감리"
    assert list_exclude_reason(keep) is None
    summary = exclude_reason_summary([gpu, gpu, its, edu])
    assert "GPU 2건" in summary
    assert "교통·ITS 1건" in summary
    assert "교육·행사·감리 1건" in summary


def test_budget_share_uses_amount_over_budget():
    notice = {"budget_eok": 10}
    assert budget_share({"amount_eok": 8.5}, notice) == 85
    assert budget_share({"amount_eok": 1}, notice) is None


def test_prespec_alert_links_to_row():
    item = prespec_item({"prespec_no": "R26BD1", "title": "AI"}, "https://x/")
    assert item["url"] == "https://x/prespecs.html#p-R26BD1"


def test_page_og_url_canonical_skip_link_and_noindex():
    from g2b.site import SITE_URL, page, write_sitemap

    html = page("밴드", "<p>x</p>", path="band.html")
    assert f'og:url" content="{SITE_URL}band.html"' in html
    assert f'rel="canonical" href="{SITE_URL}band.html"' in html
    assert 'class="skip-link"' in html and 'href="#main"' in html
    assert 'id="main"' in html
    stub = page("없음", "<h1>이 공고 페이지는 더 이상 없습니다</h1>", path="bids/OLD-000.html", noindex=True)
    assert 'name="robots" content="noindex,follow"' in stub


def test_sitemap_skips_stub_detail_pages(tmp_path):
    from g2b.site import SITE_URL, write_sitemap

    bids = tmp_path / "bids"
    bids.mkdir()
    (bids / "LIVE-000.html").write_text("<html>live</html>", encoding="utf-8")
    (bids / "GONE-000.html").write_text(
        "<html><h1>이 공고 페이지는 더 이상 없습니다</h1></html>", encoding="utf-8"
    )
    (tmp_path / "index.html").write_text("<html/>", encoding="utf-8")
    write_sitemap(tmp_path)
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert f"{SITE_URL}bids/LIVE-000.html" in xml
    assert "GONE-000" not in xml


def test_plans_stamp_uses_file_generated_at():
    from g2b.plans import _stamp

    status = {"stages": {"plans": {"last_success_at": "2026-11-21T12:00:00Z", "last_outcome": "failure"}}}
    text = _stamp(status, "plans", "발주계획", as_of="2026-11-18T10:07:25Z")
    assert "발주계획 기준 2026-11-18" in text
    assert "최근 수집 실패" in text
