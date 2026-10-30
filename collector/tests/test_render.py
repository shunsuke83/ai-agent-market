import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.render import (
    infer_status,
    load_large_awards,
    load_merged_band,
    load_needs_confirm,
    render_large_award_row,
    render_notice_row,
    replace_awards_table,
    replace_band_results_table,
    update_stamp,
)

ROOT = Path(__file__).resolve().parents[2]


def test_infer_status_upcoming():
    assert infer_status({"open_date": "2099-01-01"}, today=date(2026, 10, 29)) == "개찰 예정"


def test_infer_status_keeps_existing():
    assert infer_status({"status": "낙찰", "open_date": "2020-01-01"}) == "낙찰"


def test_merged_band_not_empty():
    rows = load_merged_band(ROOT)
    assert len(rows) >= 429


def test_render_row_contains_link():
    row = render_notice_row(
        {
            "notice_date": "2026-10-28",
            "scope": "AI SW 확대",
            "org": "테스트",
            "title": "AI 구축",
            "fields": ["AI 일반"],
            "budget_eok": 10.5,
            "open_date": "2026-11-01",
            "bid_no": "R26BK00000001",
            "bid_ord": "000",
            "status": "개찰 예정",
        }
    )
    assert "R26BK00000001" in row
    assert 'class="num">10.5</td>' in row


def test_replace_table_and_stamp_roundtrip():
    band = (ROOT / "band.html").read_text(encoding="utf-8")
    updated = replace_band_results_table(
        band, "<tr><td>x</td></tr>", 1, meta_html='<p class="meta">개찰 예정 1건</p>'
    )
    assert "공고별 결과 (1건)" in updated
    assert '<p class="meta">개찰 예정 1건</p>' in updated
    assert 'class="band-results"' in updated
    assert "<tr><td>x</td></tr>" in updated
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    stamped = update_stamp(idx, "데이터 기준 2026-10-29")
    assert '<div class="stamp">데이터 기준 2026-10-29</div>' in stamped


def test_load_large_awards():
    rows = load_large_awards(ROOT)
    assert len(rows) >= 50
    assert rows[0].get("winner")
    assert rows[0].get("budget_eok") is not None


def test_render_large_award_row():
    row = render_large_award_row(
        {
            "open_date": "2026-04-30",
            "org": "테스트",
            "title": "AI 구축",
            "budget_eok": 30.0,
            "award_amount_eok": 29.5,
            "winner": "테스트사",
            "bid_count": 3,
            "second": "2순위사",
            "bid_no": "R26BK00000001",
            "bid_ord": "000",
        }
    )
    assert "테스트사" in row
    assert 'class="num">30.0</td>' in row


def test_needs_confirm_total_is_live_count():
    rows, total = load_needs_confirm(ROOT, limit=30)
    assert 1 <= len(rows) <= 30
    assert total >= len(rows)
    assert total < 849  # the old editorial count is no longer a floor


def test_replace_awards_large_table():
    awards = (ROOT / "awards.html").read_text(encoding="utf-8")
    updated = replace_awards_table(
        awards,
        h2="예산 30억 원 이상 사업 낙찰 결과",
        rows_html="<tr><td>x</td></tr>",
        table_class="notices",
    )
    assert "<tr><td>x</td></tr>" in updated
    assert 'class="notices"' in updated
