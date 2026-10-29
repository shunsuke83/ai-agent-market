import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.render import (
    infer_status,
    load_merged_band,
    render_notice_row,
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
    assert "<tr><td>x</td></tr>" in updated
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    stamped = update_stamp(idx, date(2026, 10, 29))
    assert "최종 갱신 2026-10-29" in stamped
