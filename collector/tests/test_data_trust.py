"""P0 data-trust rules: 1순위 ≠ 낙찰, no budget stand-in amounts, no seed floor, honest stamp."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.collect import cmd_mark_run
from g2b.competitors import aggregate_competitor_kpis, load_win_pool
from g2b.normalize import apply_bidders_to_notice, split_derived_rate, split_first_rank
from g2b.render import _award_amount, render_notice_row, stamp_text
from g2b.seed import SEED_REL

COMP = [{"name": "알파", "aliases": ["알파"]}]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_opening_rank1_is_not_a_winner():
    n = apply_bidders_to_notice(
        {"bid_no": "X", "status": "낙찰 미수집"},
        [{"prcbdrNm": "알파", "opengRank": "1"}, {"prcbdrNm": "베타", "opengRank": "2"}],
    )
    assert n.get("winner") is None
    assert n["first_rank"] == "알파"
    assert n["status"] == "1순위"


def test_split_first_rank_migrates_unconfirmed_winners_only():
    moved, changed = split_first_rank({"winner": "알파", "status": "낙찰 미수집"})
    assert changed and moved["winner"] is None and moved["first_rank"] == "알파"
    marked, changed = split_first_rank({"winner": "알파 (1순위)", "award_amount_eok": 1.0})
    assert changed and marked["first_rank"] == "알파"
    for keep in (
        {"winner": "알파", "status": "낙찰"},
        {"winner": "알파", "award_amount_eok": 3.0},  # editorial award row, no status
    ):
        assert split_first_rank(keep) == (keep, False)


def test_split_derived_rate_only_moves_computed_ratio():
    n, changed = split_derived_rate({"win_rate_pct": 98.0, "award_amount_eok": 9.8, "budget_eok": 10})
    assert changed and "win_rate_pct" not in n and n["award_to_budget_pct"] == 98.0
    api = {"win_rate_pct": 87.745, "award_amount_eok": 9.8, "budget_eok": 10}
    assert split_derived_rate(api) == (api, False)


def test_award_amount_never_falls_back_to_budget():
    assert _award_amount({"budget_eok": 10, "win_rate_pct": 90}) is None
    assert _award_amount({"budget_eok": 10}) is None
    assert _award_amount({"award_amount_eok": 7.5, "budget_eok": 10}) == 7.5


def test_band_row_marks_first_rank():
    row = render_notice_row({"first_rank": "알파", "status": "1순위", "open_date": "2026-01-01"})
    assert "알파 <span" in row and "(1순위)" in row


def test_competitor_kpis_can_drop_below_seed(tmp_path):
    _write(
        tmp_path / SEED_REL,
        {
            "band_notices": [],
            "competitors_overview": [{"name": "알파", "wins": 9, "bids": 20, "award_amount_eok": 99.0}],
        },
    )
    _write(
        tmp_path / "data" / "notices.json",
        {
            "notices": [
                {"bid_no": "A", "bid_ord": "000", "winner": "알파", "status": "낙찰", "award_amount_eok": 2.0},
                {"bid_no": "B", "bid_ord": "000", "winner": "알파", "status": "낙찰", "budget_eok": 50},
                {"bid_no": "C", "bid_ord": "000", "first_rank": "알파", "status": "1순위", "budget_eok": 30},
            ]
        },
    )
    assert {r["bid_no"] for r in load_win_pool(tmp_path)} == {"A", "B"}
    (row,) = aggregate_competitor_kpis(tmp_path, COMP)
    assert (row["wins"], row["award_amount_eok"], row["amount_known"]) == (2, 2.0, 1)
    assert (row["seed_wins"], row["seed_amount_eok"]) == (9, 99.0)


def test_failed_collect_keeps_last_success(tmp_path):
    out = tmp_path / "run_status.json"

    def mark(**kw):
        ns = argparse.Namespace(out=str(out), collect=None, awards=None, bidders=None)
        for k, v in kw.items():
            setattr(ns, k, v)
        assert cmd_mark_run(ns) == 0
        return json.loads(out.read_text(encoding="utf-8"))

    first = mark(collect="success", bidders="success")
    ok_at = first["stages"]["collect"]["last_success_at"]
    status = mark(collect="failure", bidders="success")
    c = status["stages"]["collect"]
    assert c["last_success_at"] == ok_at
    assert c["last_outcome"] == "failure"
    assert "최근 수집 실패" in stamp_text(status)
    assert stamp_text(first).startswith("데이터 기준 ")
    assert "실패" not in stamp_text(first)
