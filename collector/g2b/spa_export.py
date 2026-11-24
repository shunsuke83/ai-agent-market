"""Export SPA-ready JSON under data/spa/ (and into a stage dest).

Public React app reads:
  /data/spa/summary.json
  /data/spa/notices.json
  /data/spa/notices/<id>.json  (optional; list payload is enough for most detail fields)

Fit scoring matches sync-d1 / public HTML render (score_policy + COMPANY_PROFILE).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .classify import load_keywords
from .gonogo import load_profile
from .gonogo_policy import GO, NO_GO, REVIEW, score_policy
from .normalize import list_exclude_reason, list_excluded, read_notices, sort_notices
from .render import KST, load_run_status, stamp_text
from .rfp import load_summaries

DEADLINE_DAYS = 14
NEW_DAYS = 7
LIMIT = 12
BAND_MIN = 8.0
BAND_MAX = 30.0


def _now() -> datetime:
    return datetime.now(KST)


def _now_s(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M")


def _slim_notice(
    n: dict[str, Any],
    *,
    rules: dict[str, Any],
    scored: dict[str, Any] | None,
) -> dict[str, Any]:
    bid = n.get("bid_no") or ""
    ord_ = str(n.get("bid_ord") or "000").zfill(3)
    soft = list_excluded(n, rules)
    row: dict[str, Any] = {
        "id": f"{bid}-{ord_}",
        "bid_no": bid,
        "bid_ord": ord_,
        "title": n.get("title"),
        "org": n.get("org"),
        "scope": n.get("scope"),
        "nature": n.get("nature"),
        "fields": list(n.get("fields") or []),
        "budget_eok": n.get("budget_eok"),
        "notice_date": n.get("notice_date"),
        "close_at": (n.get("close_at") or "")[:16] or None,
        "open_date": n.get("open_date"),
        "open_at": n.get("open_at"),
        "contract_method": n.get("contract_method"),
        "ntce_kind": n.get("ntce_kind"),
        "winner": n.get("winner"),
        "first_rank": n.get("first_rank"),
        "bid_count": n.get("bid_count"),
        "award_amount_eok": n.get("award_amount_eok"),
        "win_rate_pct": n.get("win_rate_pct"),
        "g2b_url": n.get("g2b_url"),
        "soft_excluded": soft,
        "exclude_reason": list_exclude_reason(n, rules) if soft else None,
        "fit_verdict": None,
        "fit_score": None,
        "fit_reasons": [],
    }
    if scored:
        row["fit_verdict"] = scored.get("verdict")
        row["fit_score"] = scored.get("score")
        row["fit_reasons"] = list(scored.get("reasons") or [])
        if scored.get("stops"):
            row["fit_stops"] = list(scored["stops"])
    return row


def _detail(n: dict[str, Any], slim: dict[str, Any]) -> dict[str, Any]:
    """Detail payload = slim + optional raw extras (notice files, bidders)."""
    out = dict(slim)
    extras = {
        k: n.get(k)
        for k in (
            "notice_files",
            "bidders",
            "price_rate",
            "tech_rate",
            "award_method",
            "industry_limit",
            "participation_limit",
            "record_limit",
            "joint_method",
            "prespec_no",
            "plan_no",
            "biz",
            "source",
        )
        if n.get(k) is not None
    }
    if extras:
        out["payload"] = extras
    return out


def build_spa_payload(repo_root: Path) -> dict[str, Any]:
    rules = load_keywords()
    notices = sort_notices(read_notices(repo_root / "data" / "notices.json", collapse=True))
    summaries = load_summaries(repo_root)
    profile = load_profile()
    now = _now()
    now_s = _now_s(now)
    today = now.date()
    deadline_s = (now + timedelta(days=DEADLINE_DAYS)).strftime("%Y-%m-%d %H:%M")
    new_since = (today - timedelta(days=NEW_DAYS - 1)).isoformat()

    scored_by_id: dict[str, dict[str, Any]] = {}
    slim_rows: list[dict[str, Any]] = []
    details: dict[str, dict[str, Any]] = {}

    for n in notices:
        scored = None
        if profile:
            entry = summaries.get(n.get("bid_no") or "")
            scored = score_policy(n, profile, now, summary=entry, rules=rules)
        slim = _slim_notice(n, rules=rules, scored=scored)
        slim_rows.append(slim)
        details[slim["id"]] = _detail(n, slim)
        if scored:
            scored_by_id[slim["id"]] = scored

    live = [r for r in slim_rows if not r.get("soft_excluded")]
    open_now = [r for r in live if (r.get("close_at") or "") >= now_s]
    closing = sorted(
        (r for r in open_now if (r.get("close_at") or "") <= deadline_s),
        key=lambda r: r.get("close_at") or "",
    )
    new = sorted(
        (r for r in live if (r.get("notice_date") or "") >= new_since),
        key=lambda r: -(r.get("budget_eok") or 0),
    )
    band = [
        r
        for r in open_now
        if r.get("budget_eok") is not None and BAND_MIN <= float(r["budget_eok"]) <= BAND_MAX
    ]

    fit_pool: list[dict[str, Any]] = []
    go_count = review_count = 0
    for r in open_now:
        v = r.get("fit_verdict")
        if v == GO:
            go_count += 1
        elif v == REVIEW:
            review_count += 1
        if not v:
            continue
        if v == NO_GO and (r.get("fit_score") or 0) < 50:
            continue
        fit_pool.append(r)
    order = {GO: 0, REVIEW: 1, NO_GO: 2}
    fit_pool.sort(key=lambda r: (order.get(r.get("fit_verdict") or "", 9), -(r.get("fit_score") or 0)))

    run_status = load_run_status(repo_root)
    summary = {
        "generated_at": stamp_text(run_status),
        "generated_at_iso": now.isoformat(),
        "has_fit": bool(profile),
        "total_notices": len(live),
        "open_notices": len(open_now),
        "new_notices": len(new),
        "go_count": go_count,
        "review_count": review_count,
        "closing_soon": len(closing),
        "band_count": len(band),
        "new": new[:LIMIT],
        "fit": fit_pool[:LIMIT],
        "closing": closing[:LIMIT],
    }

    return {
        "summary": summary,
        "notices": {"generated_at": summary["generated_at"], "notices": slim_rows},
        "details": details,
    }


def _bidders_index(repo_root: Path) -> list[dict[str, Any]]:
    """Compact firm list for SPA. hist entries are [notice_idx, rank, rate_pct, amount].

    Wins = notices where notice[5] (winner 사업자번호) equals this firm — same rule as
    assets/bidder-search.js. Do not treat hist[0]==0 as a win (that is a notice index).
    """
    path = repo_root / "data" / "bidders.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    firms = raw.get("firms") if isinstance(raw, dict) else None
    notices = raw.get("notices") if isinstance(raw, dict) else None
    if not isinstance(firms, dict):
        return []
    if not isinstance(notices, list):
        notices = []
    rows: list[dict[str, Any]] = []
    for bizno, v in firms.items():
        row = v if isinstance(v, list) else []
        hist = row[2] if len(row) > 2 and isinstance(row[2], list) else []
        wins = 0
        win_rates: list[float] = []
        for h in hist:
            if not isinstance(h, list) or not h:
                continue
            try:
                idx = int(h[0])
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(notices):
                continue
            notice = notices[idx]
            winner_bz = notice[5] if isinstance(notice, list) and len(notice) > 5 else None
            if str(winner_bz or "") != str(bizno):
                continue
            wins += 1
            # Prefer amount/budget (true 낙찰률). hist rate_pct is often a 10-pt price score
            # on negotiated contracts, not award-to-budget %.
            budget = notice[3] if isinstance(notice, list) and len(notice) > 3 else None
            amount = h[3] if len(h) > 3 else None
            rate = None
            try:
                if amount not in (None, "") and budget not in (None, "") and float(budget) > 0:
                    rate = float(amount) / float(budget) * 100.0
                elif len(h) > 2 and h[2] not in (None, ""):
                    candidate = float(h[2])
                    if candidate >= 50:  # looks like 낙찰률, not 가격평가 점수
                        rate = candidate
            except (TypeError, ValueError):
                rate = None
            if rate is not None:
                win_rates.append(rate)
        entry: dict[str, Any] = {
            "bizno": bizno,
            "name": row[0] if row else bizno,
            "region": row[1] if len(row) > 1 else "",
            "bids": len(hist),
            "wins": wins,
        }
        if win_rates:
            entry["avg_win_rate"] = round(sum(win_rates) / len(win_rates), 1)
        rows.append(entry)
    rows.sort(key=lambda r: (-int(r["wins"]), -int(r["bids"]), str(r["name"])))
    return rows


def _agencies_payload(repo_root: Path) -> dict[str, Any]:
    """SPA agencies search: org rollups + notice rows (same shape as agency-search.js)."""
    from .render import load_run_status, stamp_text

    path = repo_root / "data" / "agencies.json"
    if not path.is_file():
        return {
            "generated_at": stamp_text(load_run_status(repo_root)),
            "summary": {"orgs": 0, "notices": 0, "wins": 0},
            "agencies": [],
            "notices": [],
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows_raw = raw.get("notices") if isinstance(raw, dict) else raw
    if not isinstance(rows_raw, list):
        rows_raw = []

    notices: list[dict[str, Any]] = []
    by_org: dict[str, dict[str, Any]] = {}

    def _firm_key(name: str, bizno: str) -> str:
        if bizno:
            return f"b:{bizno}"
        cleaned = (
            str(name or "")
            .replace("(주)", "")
            .replace("㈜", "")
            .replace("주식회사", "")
            .replace("유한회사", "")
        )
        return "n:" + "".join(ch for ch in cleaned.casefold() if ch.isalnum())

    for row in rows_raw:
        if not isinstance(row, list) or len(row) < 2:
            continue
        org = str(row[1] or "").strip()
        if not org:
            continue
        href = str(row[4] or "")
        nid = ""
        if href:
            base = href.rsplit("/", 1)[-1]
            nid = base.replace(".html", "")
        try:
            budget = float(row[3]) if row[3] not in (None, "") else None
        except (TypeError, ValueError):
            budget = None
        try:
            award = float(row[7]) if len(row) > 7 and row[7] not in (None, "") else None
        except (TypeError, ValueError):
            award = None
        try:
            bid_count = int(float(row[9])) if len(row) > 9 and row[9] not in (None, "") else None
        except (TypeError, ValueError):
            bid_count = None
        status = str(row[8] or "") if len(row) > 8 else ""
        winner = str(row[5] or "").strip() if len(row) > 5 else ""
        winner_bizno = str(row[6] or "") if len(row) > 6 else ""
        gen_agent = bool(row[10]) if len(row) > 10 else False
        day = str(row[0] or "")
        notice = {
            "date": day,
            "org": org,
            "title": row[2] or "",
            "budget_eok": budget,
            "id": nid or None,
            "winner": winner or None,
            "winner_bizno": winner_bizno or None,
            "award_amount_eok": award,
            "status": status or None,
            "bid_count": bid_count,
            "gen_agent": gen_agent,
        }
        notices.append(notice)

        cur = by_org.setdefault(
            org,
            {
                "name": org,
                "notices": 0,
                "wins": 0,
                "budget_eok": 0.0,
                "award_amount_eok": 0.0,
                "award_known": 0,
                "gen_agent_notices": 0,
                "bid_counts": [],
                "latest_date": "",
                "_winners": {},
            },
        )
        cur["notices"] += 1
        if budget is not None:
            cur["budget_eok"] = float(cur["budget_eok"]) + budget
        if gen_agent:
            cur["gen_agent_notices"] += 1
        if bid_count is not None:
            cur["bid_counts"].append(bid_count)
        if day >= str(cur["latest_date"] or ""):
            cur["latest_date"] = day
        if status == "낙찰" and winner:
            cur["wins"] += 1
            if award is not None:
                cur["award_amount_eok"] = float(cur["award_amount_eok"]) + award
                cur["award_known"] += 1
            wk = _firm_key(winner, winner_bizno)
            w = cur["_winners"].setdefault(
                wk, {"name": winner, "bizno": winner_bizno or None, "wins": 0, "award_amount_eok": 0.0}
            )
            if winner_bizno and not w.get("bizno"):
                w["bizno"] = winner_bizno
            w["wins"] += 1
            if award is not None:
                w["award_amount_eok"] = float(w["award_amount_eok"]) + award

    agencies: list[dict[str, Any]] = []
    for org, cur in by_org.items():
        counts = cur.pop("bid_counts")
        winners_map = cur.pop("_winners")
        top = sorted(
            winners_map.values(),
            key=lambda w: (-int(w["wins"]), -float(w.get("award_amount_eok") or 0), str(w["name"])),
        )[:10]
        for w in top:
            w["award_amount_eok"] = round(float(w.get("award_amount_eok") or 0), 1)
        avg_bids = round(sum(counts) / len(counts), 1) if counts else None
        agencies.append(
            {
                "name": org,
                "notices": int(cur["notices"]),
                "wins": int(cur["wins"]),
                "budget_eok": round(float(cur["budget_eok"]), 1),
                "award_amount_eok": round(float(cur["award_amount_eok"]), 1),
                "award_known": int(cur["award_known"]),
                "gen_agent_notices": int(cur["gen_agent_notices"]),
                "avg_bid_count": avg_bids,
                "latest_date": cur["latest_date"] or None,
                "top_winners": top,
            }
        )
    agencies.sort(key=lambda r: (-int(r["notices"]), -int(r["wins"]), str(r["name"])))
    wins_n = sum(1 for n in notices if n.get("status") == "낙찰")
    return {
        "generated_at": stamp_text(load_run_status(repo_root)),
        "summary": {"orgs": len(agencies), "notices": len(notices), "wins": wins_n},
        "agencies": agencies,
        "notices": notices,
    }


def write_spa_export(
    repo_root: Path,
    dest: Path | None = None,
    *,
    write_detail_files: bool = False,
) -> dict[str, Any]:
    """Write data/spa/ (and optional dest/data/spa/).

    Per-id detail files are off by default — `notices.json` already carries detail fields
    and the React client falls back to the list. Set write_detail_files=True for CDN
    single-object fetches.
    """
    from .competitors import build_spa_competitors

    payload = build_spa_payload(repo_root)
    bidders = _bidders_index(repo_root)
    agencies = _agencies_payload(repo_root)
    competitors = build_spa_competitors(repo_root)
    targets = [repo_root / "data" / "spa"]
    if dest is not None:
        targets.append(Path(dest) / "data" / "spa")

    detail_count = 0
    for out in targets:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        (out / "summary.json").write_text(
            json.dumps(payload["summary"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out / "notices.json").write_text(
            json.dumps(payload["notices"], ensure_ascii=False),
            encoding="utf-8",
        )
        (out / "bidders-index.json").write_text(
            json.dumps({"bidders": bidders}, ensure_ascii=False),
            encoding="utf-8",
        )
        (out / "agencies-index.json").write_text(
            json.dumps(agencies, ensure_ascii=False),
            encoding="utf-8",
        )
        (out / "competitors.json").write_text(
            json.dumps(competitors, ensure_ascii=False),
            encoding="utf-8",
        )
        if write_detail_files:
            detail_dir = out / "notices"
            detail_dir.mkdir()
            for nid, detail in payload["details"].items():
                if "/" in nid or "\\" in nid or ".." in nid:
                    continue
                (detail_dir / f"{nid}.json").write_text(
                    json.dumps(detail, ensure_ascii=False),
                    encoding="utf-8",
                )
                detail_count += 1

    return {
        "notices": len(payload["notices"]["notices"]),
        "details": detail_count,
        "bidders": len(bidders),
        "agencies": len(agencies.get("agencies") or []),
        "competitors": len(competitors.get("firms") or []),
        "has_fit": payload["summary"]["has_fit"],
        "open_notices": payload["summary"]["open_notices"],
        "dirs": [str(t) for t in targets],
    }


def copy_spa_into(repo_root: Path, dest: Path) -> dict[str, Any]:
    """Ensure spa JSON exists under repo data/spa, then copy into dest/data/."""
    spa_src = repo_root / "data" / "spa"
    if not (spa_src / "summary.json").is_file():
        write_spa_export(repo_root)
    dest_spa = dest / "data" / "spa"
    if dest_spa.exists():
        shutil.rmtree(dest_spa)
    shutil.copytree(spa_src, dest_spa)
    # Also stage search datasets next to spa.
    data_dest = dest / "data"
    data_dest.mkdir(exist_ok=True)
    copied = 0
    for name in (
        "bidders.json",
        "agencies.json",
        "firms.json",
        "prespecs.json",
        "order_plans.json",
        "reports.json",
        "contracts.json",
    ):
        src = repo_root / "data" / name
        if src.is_file():
            shutil.copy2(src, data_dest / name)
            copied += 1
    return {"spa": str(dest_spa), "data_files": copied}
