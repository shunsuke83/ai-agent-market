import json
import shutil
from datetime import date
from pathlib import Path

from g2b.reports import render_reports

ROOT = Path(__file__).resolve().parents[2]


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    shutil.copy(ROOT / "data" / "notices.json", tmp_path / "data" / "notices.json")
    reports = tmp_path / "reports"
    reports.mkdir()
    for name in ("weekly-2026-W43.html", "monthly-2026-10.html"):
        (reports / name).write_text("<html></html>", encoding="utf-8")
    return tmp_path


def test_past_reports_get_summaries_and_keep_saved_ones(tmp_path):
    repo = _repo(tmp_path)
    render_reports(repo, week=(2026, 45), month=(2026, 11), today=date(2026, 11, 12))
    index = (repo / "reports" / "index.html").read_text(encoding="utf-8")
    assert "?건" not in index and "?억" not in index

    meta = json.loads((repo / "data" / "reports.json").read_text(encoding="utf-8"))
    oct_ = next(m for m in meta["monthly"] if m["slug"] == "monthly-2026-10")
    assert oct_["core_count"] > 0 and oct_["in_progress"] is False

    w43 = next(m for m in meta["weekly"] if m["slug"] == "weekly-2026-W43")
    w43["core_count"] = 12345
    (repo / "data" / "reports.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    render_reports(repo, week=(2026, 45), month=(2026, 11), today=date(2026, 11, 12))
    assert "신규 핵심 공고 12345건" in (repo / "reports" / "index.html").read_text(encoding="utf-8")
