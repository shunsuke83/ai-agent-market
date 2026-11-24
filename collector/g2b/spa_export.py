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
from .normalize import list_exclude_reason, list_excluded, sort_notices
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


def _g2b_url(n: dict[str, Any]) -> str | None:
    """Prefer stored URL; otherwise synthesize from bid_no (same as render._g2b_href)."""
    url = (n.get("g2b_url") or "").strip()
    if url:
        return url
    bid = n.get("bid_no") or ""
    if not bid:
        return None
    ord_ = str(n.get("bid_ord") or "000").zfill(3)
    return (
        "https://www.g2b.go.kr/link/PNPE027_01/single/"
        f"?bidPbancNo={bid}&bidPbancOrd={ord_}"
    )


def _win_rate_pct(n: dict[str, Any]) -> float | None:
    """win_rate_pct, else award_to_budget_pct (budget-share stand-in)."""
    for key in ("win_rate_pct", "award_to_budget_pct"):
        v = n.get(key)
        if v in (None, ""):
            continue
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            continue
    return None


_HW_MARKERS = (
    "GPU",
    "서버",
    "Server",
    "H/W",
    "하드웨어",
    "NPU",
    "서버팜",
    "워크스테이션",
    "스토리지",
)


def _hw_included(n: dict[str, Any], summary: dict[str, Any] | None = None) -> bool:
    """True when title/nature/RFP text signals GPU·server hardware (not soft-exclude)."""
    blobs = [
        str(n.get("title") or ""),
        str(n.get("nature") or ""),
        str(n.get("scope") or ""),
    ]
    if summary:
        s = summary.get("summary") if isinstance(summary.get("summary"), dict) else summary
        if isinstance(s, dict):
            blobs.append(str(s.get("overview") or ""))
            for key in ("tasks", "tech"):
                for item in s.get(key) or []:
                    blobs.append(str(item))
    text = " ".join(blobs)
    return any(m.casefold() in text.casefold() for m in _HW_MARKERS)


def _split_rate_score(rate: Any) -> tuple[float | None, float | None]:
    """Heuristic: values in 50–110 look like 투찰률; 0–50 look like price score."""
    try:
        v = float(rate)
    except (TypeError, ValueError):
        return None, None
    if 50 <= v <= 110:
        return v, None
    if 0 <= v < 50:
        return None, v
    return None, None


def _compact_bidders(n: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw = n.get("bidders")
    if not isinstance(raw, list) or not raw:
        return None
    out: list[dict[str, Any]] = []
    for b in raw:
        if not isinstance(b, dict):
            continue
        rate = b.get("rate_pct")
        price = b.get("price_score")
        if price is None and rate is not None:
            _r, score = _split_rate_score(rate)
            if score is not None:
                price = score
                rate = _r
            else:
                rate = _r if _r is not None else rate
        row: dict[str, Any] = {
            "rank": b.get("rank"),
            "name": b.get("name"),
            "bizno": b.get("bizno"),
            "amount_eok": b.get("amount_eok"),
            "rate_pct": rate,
            "price_score": price,
            "tech_score": b.get("tech_score"),
            "total_score": b.get("total_score"),
        }
        out.append(row)
    return out or None


def _slim_notice(
    n: dict[str, Any],
    *,
    rules: dict[str, Any],
    scored: dict[str, Any] | None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bid = n.get("bid_no") or ""
    ord_ = str(n.get("bid_ord") or "000").zfill(3)
    soft = list_excluded(n, rules)
    close = (n.get("close_at") or n.get("close_date") or "")
    close_at = str(close)[:16] or None
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
        "close_at": close_at,
        "open_date": n.get("open_date"),
        "open_at": n.get("open_at"),
        "contract_method": n.get("contract_method"),
        "ntce_kind": n.get("ntce_kind"),
        "winner": n.get("winner"),
        "first_rank": n.get("first_rank"),
        "second": n.get("second"),
        "status": n.get("status"),
        "bid_count": n.get("bid_count"),
        "award_amount_eok": n.get("award_amount_eok"),
        "award_to_budget_pct": n.get("award_to_budget_pct"),
        "win_rate_pct": _win_rate_pct(n),
        "g2b_url": _g2b_url(n),
        "hw_included": _hw_included(n, summary),
        "soft_excluded": soft,
        "exclude_reason": list_exclude_reason(n, rules) if soft else None,
        "fit_verdict": None,
        "fit_score": None,
        "fit_reasons": [],
    }
    bidders = _compact_bidders(n)
    if bidders:
        row["bidders"] = bidders
        if row.get("bid_count") is None:
            row["bid_count"] = len(bidders)
    extras = {
        k: n.get(k)
        for k in (
            "notice_files",
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
            "asign_budget_eok",
            "presmpt_eok",
            "base_amount_eok",
            "budget_kind",
            "source",
        )
        if n.get(k) is not None
    }
    if extras:
        row["payload"] = extras
    if scored:
        row["fit_verdict"] = scored.get("verdict")
        row["fit_score"] = scored.get("score")
        row["fit_reasons"] = list(scored.get("reasons") or [])
        if scored.get("stops"):
            row["fit_stops"] = list(scored["stops"])
    return row


def _detail(n: dict[str, Any], slim: dict[str, Any]) -> dict[str, Any]:
    """Detail payload = slim (already carries bidders + payload extras)."""
    return dict(slim)


def build_spa_payload(repo_root: Path) -> dict[str, Any]:
    from .detail import load_detail_notices

    rules = load_keywords()
    # Same merge as legacy detail HTML: editorial seed fills blanks on bootstrap rows.
    notices = sort_notices(load_detail_notices(repo_root))
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
        entry = summaries.get(n.get("bid_no") or "") if summaries else None
        scored = None
        if profile:
            scored = score_policy(n, profile, now, summary=entry, rules=rules)
        slim = _slim_notice(n, rules=rules, scored=scored, summary=entry)
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


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def _bidders_payload(repo_root: Path) -> dict[str, Any]:
    """SPA bidder search: firm rollups + shared notices + per-bid history.

    hist entries are [notice_idx, rank, rate_pct|score, amount]. Wins = notices where
    notice[5] (winner 사업자번호) equals this firm — same rule as assets/bidder-search.js.
    """
    from .render import load_run_status, stamp_text

    empty = {
        "generated_at": stamp_text(load_run_status(repo_root)),
        "summary": {"firms": 0, "notices": 0, "bids": 0, "wins": 0},
        "notices": [],
        "firms": [],
    }
    path = repo_root / "data" / "bidders.json"
    if not path.is_file():
        return empty
    raw = json.loads(path.read_text(encoding="utf-8"))
    firms_raw = raw.get("firms") if isinstance(raw, dict) else None
    notices_raw = raw.get("notices") if isinstance(raw, dict) else None
    if not isinstance(firms_raw, dict):
        return empty
    if not isinstance(notices_raw, list):
        notices_raw = []

    notices: list[dict[str, Any]] = []
    for row in notices_raw:
        if not isinstance(row, list) or len(row) < 3:
            notices.append(
                {
                    "date": None,
                    "org": "",
                    "title": "",
                    "budget_eok": None,
                    "id": None,
                    "winner_bizno": "",
                    "status": "",
                    "bidder_count": 0,
                }
            )
            continue
        href = str(row[4] or "") if len(row) > 4 else ""
        nid = ""
        if href:
            base = href.rsplit("/", 1)[-1]
            nid = base.replace(".html", "")
        try:
            budget = float(row[3]) if len(row) > 3 and row[3] not in (None, "") else None
        except (TypeError, ValueError):
            budget = None
        notices.append(
            {
                "date": str(row[0] or "") or None,
                "org": str(row[1] or ""),
                "title": str(row[2] or ""),
                "budget_eok": budget,
                "id": nid or None,
                "winner_bizno": str(row[5] or "") if len(row) > 5 else "",
                "status": str(row[6] or "") if len(row) > 6 else "",
                "bidder_count": 0,
            }
        )

    # Participants per notice: [(bizno, rank), ...] for rivals + bidder_count.
    by_notice: list[list[tuple[str, int | None]]] = [[] for _ in notices]
    firm_hists: dict[str, list[list[Any]]] = {}
    for bizno, v in firms_raw.items():
        row = v if isinstance(v, list) else []
        hist = row[2] if len(row) > 2 and isinstance(row[2], list) else []
        firm_hists[str(bizno)] = hist
        for h in hist:
            if not isinstance(h, list) or not h:
                continue
            try:
                idx = int(h[0])
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(notices):
                continue
            rank: int | None
            try:
                rank = int(h[1]) if len(h) > 1 and h[1] not in (None, "") else None
            except (TypeError, ValueError):
                rank = None
            by_notice[idx].append((str(bizno), rank))
    for i, parts in enumerate(by_notice):
        notices[i]["bidder_count"] = len(parts)

    firm_name = {
        str(bz): (v[0] if isinstance(v, list) and v else bz) for bz, v in firms_raw.items()
    }

    firms: list[dict[str, Any]] = []
    total_bids = 0
    total_wins = 0
    for bizno, v in firms_raw.items():
        bz = str(bizno)
        row = v if isinstance(v, list) else []
        hist = firm_hists.get(bz, [])
        wins = 0
        firsts = 0
        win_rates: list[float] = []
        bid_rates: list[float] = []
        shares: list[float] = []
        history: list[dict[str, Any]] = []
        faced: dict[str, dict[str, int]] = {}

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
            winner_bz = str(notice.get("winner_bizno") or "")
            try:
                rank = int(h[1]) if len(h) > 1 and h[1] not in (None, "") else None
            except (TypeError, ValueError):
                rank = None
            raw_rate = None
            if len(h) > 2 and h[2] not in (None, ""):
                try:
                    raw_rate = float(h[2])
                except (TypeError, ValueError):
                    raw_rate = None
            amount = None
            if len(h) > 3 and h[3] not in (None, ""):
                try:
                    amount = float(h[3])
                except (TypeError, ValueError):
                    amount = None
            budget = notice.get("budget_eok")
            is_rate = raw_rate is not None and 50 <= raw_rate <= 110
            is_score = raw_rate is not None and 0 <= raw_rate < 50
            if is_rate:
                bid_rates.append(raw_rate)
            if (
                amount is not None
                and budget not in (None, "")
                and float(budget or 0) > 0
            ):
                share = 100.0 * amount / float(budget)  # type: ignore[arg-type]
                if 20 <= share <= 160:
                    shares.append(share)

            won = winner_bz == bz
            if won:
                wins += 1
                # Prefer amount/budget (true 낙찰률). hist rate is often a 10-pt price score.
                rate = None
                try:
                    if amount is not None and budget not in (None, "") and float(budget or 0) > 0:
                        rate = amount / float(budget) * 100.0  # type: ignore[arg-type]
                    elif is_rate and raw_rate is not None:
                        rate = raw_rate
                except (TypeError, ValueError):
                    rate = None
                if rate is not None:
                    win_rates.append(rate)
            elif not winner_bz and notice.get("status") != "낙찰" and rank == 1:
                firsts += 1

            for other_bz, other_rank in by_notice[idx]:
                if other_bz == bz:
                    continue
                slot = faced.get(other_bz) or {"n": 0, "ahead": 0, "behind": 0}
                slot["n"] += 1
                if rank is not None and other_rank is not None:
                    if rank < other_rank:
                        slot["ahead"] += 1
                    elif rank > other_rank:
                        slot["behind"] += 1
                faced[other_bz] = slot

            history.append(
                {
                    "notice_idx": idx,
                    "rank": rank,
                    "rate_pct": round(raw_rate, 3) if is_rate and raw_rate is not None else None,
                    "price_score": round(raw_rate, 3) if is_score and raw_rate is not None else None,
                    "amount_eok": amount,
                }
            )

        rivals = sorted(
            (
                {
                    "bizno": obz,
                    "name": firm_name.get(obz, obz),
                    "faced": stats["n"],
                    "ahead": stats["ahead"],
                    "behind": stats["behind"],
                }
                for obz, stats in faced.items()
            ),
            key=lambda r: (-int(r["faced"]), str(r["name"])),
        )[:8]

        changes: list[dict[str, Any]] = []
        raw_changes = row[3] if len(row) > 3 and isinstance(row[3], list) else []
        for c in raw_changes:
            if not isinstance(c, list) or not c:
                continue
            changes.append(
                {
                    "date": str(c[0] or "") if len(c) > 0 else "",
                    "text": str(c[1] or "") if len(c) > 1 else "",
                    "confirmed": bool(c[2]) if len(c) > 2 else False,
                }
            )

        med_rate = _median(bid_rates)
        med_share = _median(shares)
        entry: dict[str, Any] = {
            "bizno": bz,
            "name": row[0] if row else bz,
            "region": row[1] if len(row) > 1 else "",
            "bids": len(history),
            "wins": wins,
            "firsts": firsts,
            "history": history,
            "rivals": rivals,
            "changes": changes,
        }
        if win_rates:
            entry["avg_win_rate"] = round(sum(win_rates) / len(win_rates), 1)
        if med_rate is not None:
            entry["median_bid_rate"] = round(med_rate, 2)
            entry["bid_rate_n"] = len(bid_rates)
        if med_share is not None:
            entry["median_budget_share"] = round(med_share, 1)
            entry["budget_share_n"] = len(shares)
        firms.append(entry)
        total_bids += len(history)
        total_wins += wins

    firms.sort(key=lambda r: (-int(r["wins"]), -int(r["bids"]), str(r["name"])))
    return {
        "generated_at": stamp_text(load_run_status(repo_root)),
        "summary": {
            "firms": len(firms),
            "notices": len(notices),
            "bids": total_bids,
            "wins": total_wins,
        },
        "notices": notices,
        "firms": firms,
    }


def _bidders_index(repo_root: Path) -> list[dict[str, Any]]:
    """Firm summary rows only (tests / callers that do not need history)."""
    return list(_bidders_payload(repo_root).get("firms") or [])


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


XENON_BIZNO = "7638101040"
LARGE_JOINT_MIN_EOK = 30.0


def _firm_key_name(name: str, bizno: str | None) -> str:
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


def _consortium_payload(repo_root: Path) -> dict[str, Any]:
    """Lead↔member edges and rollups from contracts.json (multi-firm = joint)."""
    from .competitors import load_competitors_config
    from .render import load_run_status, stamp_text

    empty = {
        "generated_at": stamp_text(load_run_status(repo_root)),
        "summary": {
            "contracts": 0,
            "multi_firm": 0,
            "large_joint": 0,
            "external_lead_to_listed": 0,
            "xenon_lead": 0,
            "xenon_member": 0,
        },
        "edges": [],
        "leaders": [],
        "members": [],
        "large_joint": [],
        "xenon": {"bizno": XENON_BIZNO, "lead": 0, "member": 0, "contracts": []},
    }
    path = repo_root / "data" / "contracts.json"
    if not path.is_file():
        return empty
    raw = json.loads(path.read_text(encoding="utf-8"))
    contracts = raw.get("contracts") if isinstance(raw, dict) else None
    if not isinstance(contracts, list):
        return empty

    listed_bz = {
        "".join(ch for ch in str(c.get("bizno") or "") if ch.isdigit())
        for c in load_competitors_config()
    }
    listed_bz.discard("")

    edges: dict[tuple[str, str], dict[str, Any]] = {}
    leaders: dict[str, dict[str, Any]] = {}
    members: dict[str, dict[str, Any]] = {}
    large_joint: list[dict[str, Any]] = []
    xenon_contracts: list[dict[str, Any]] = []
    xenon_lead = xenon_member = 0
    multi_n = 0
    external_lead_to_listed = 0

    for c in contracts:
        if not isinstance(c, dict):
            continue
        firms = [f for f in (c.get("firms") or []) if isinstance(f, dict) and f.get("name")]
        try:
            amount = float(c.get("amount_eok")) if c.get("amount_eok") not in (None, "") else None
        except (TypeError, ValueError):
            amount = None
        multi = len(firms) > 1
        if multi:
            multi_n += 1

        leads = [f for f in firms if f.get("role") == "주계약업체"] or (
            [firms[0]] if firms and not multi else []
        )
        members_f = [f for f in firms if f.get("role") == "도급업체"]
        if multi and not members_f:
            lead_keys = {_firm_key_name(str(f.get("name")), str(f.get("bizno") or "") or None) for f in leads}
            members_f = [
                f
                for f in firms
                if _firm_key_name(str(f.get("name")), str(f.get("bizno") or "") or None) not in lead_keys
            ]

        for f in firms:
            bz = "".join(ch for ch in str(f.get("bizno") or "") if ch.isdigit())
            role = f.get("role") or ""
            if bz == XENON_BIZNO or "제논" in str(f.get("name") or ""):
                if role == "주계약업체":
                    xenon_lead += 1
                elif role == "도급업체":
                    xenon_member += 1
                elif multi:
                    xenon_member += 1
                else:
                    xenon_lead += 1
                xenon_contracts.append(
                    {
                        "contract_no": c.get("contract_no"),
                        "title": c.get("title"),
                        "org": c.get("org") or c.get("contract_org"),
                        "amount_eok": amount,
                        "role": role or ("주계약업체" if not multi else "도급업체"),
                        "share": f.get("share"),
                        "signed_date": c.get("signed_date"),
                    }
                )

        for lead in leads:
            lbz = "".join(ch for ch in str(lead.get("bizno") or "") if ch.isdigit()) or None
            lk = _firm_key_name(str(lead.get("name")), lbz)
            L = leaders.setdefault(
                lk,
                {
                    "name": lead.get("name"),
                    "bizno": lbz,
                    "contracts": 0,
                    "amount_eok": 0.0,
                    "listed": bool(lbz and lbz in listed_bz),
                },
            )
            L["contracts"] += 1
            if amount is not None:
                L["amount_eok"] = float(L["amount_eok"]) + amount

            for mem in members_f:
                mbz = "".join(ch for ch in str(mem.get("bizno") or "") if ch.isdigit()) or None
                mk = _firm_key_name(str(mem.get("name")), mbz)
                M = members.setdefault(
                    mk,
                    {
                        "name": mem.get("name"),
                        "bizno": mbz,
                        "contracts": 0,
                        "amount_eok": 0.0,
                        "listed": bool(mbz and mbz in listed_bz),
                    },
                )
                M["contracts"] += 1
                if amount is not None:
                    M["amount_eok"] = float(M["amount_eok"]) + amount

                ek = (lk, mk)
                E = edges.setdefault(
                    ek,
                    {
                        "lead_name": lead.get("name"),
                        "lead_bizno": lbz,
                        "member_name": mem.get("name"),
                        "member_bizno": mbz,
                        "count": 0,
                        "amount_eok_sum": 0.0,
                        "sample_contract_no": c.get("contract_no"),
                        "member_listed": bool(mbz and mbz in listed_bz),
                        "lead_listed": bool(lbz and lbz in listed_bz),
                    },
                )
                E["count"] += 1
                if amount is not None:
                    E["amount_eok_sum"] = float(E["amount_eok_sum"]) + amount
                if (not lbz or lbz not in listed_bz) and mbz and mbz in listed_bz:
                    external_lead_to_listed += 1

        if multi and amount is not None and amount >= LARGE_JOINT_MIN_EOK:
            large_joint.append(
                {
                    "contract_no": c.get("contract_no"),
                    "title": c.get("title"),
                    "org": c.get("org") or c.get("contract_org"),
                    "amount_eok": amount,
                    "signed_date": c.get("signed_date"),
                    "bid_no": c.get("bid_no"),
                    "url": c.get("url"),
                    "firms": [
                        {
                            "name": f.get("name"),
                            "role": f.get("role"),
                            "share": f.get("share"),
                            "bizno": "".join(ch for ch in str(f.get("bizno") or "") if ch.isdigit())
                            or None,
                        }
                        for f in firms
                    ],
                }
            )

    def _roll(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        out = list(rows.values())
        for r in out:
            r["amount_eok"] = round(float(r.get("amount_eok") or 0), 1)
        out.sort(key=lambda r: (-float(r["amount_eok"]), -int(r["contracts"]), str(r["name"])))
        return out

    edge_rows = list(edges.values())
    for e in edge_rows:
        e["amount_eok_sum"] = round(float(e.get("amount_eok_sum") or 0), 1)
    edge_rows.sort(
        key=lambda e: (-int(e["count"]), -float(e["amount_eok_sum"]), str(e["lead_name"]))
    )
    large_joint.sort(key=lambda r: (-float(r.get("amount_eok") or 0), str(r.get("signed_date") or "")))

    # Count unique contracts where external lead brought a listed member (dedupe by contract sample is weak;
    # use edge flag sum of occurrences as in the idea brief: contract-level recount).
    ext_contracts = 0
    for c in contracts:
        firms = [f for f in (c.get("firms") or []) if isinstance(f, dict)]
        if len(firms) < 2:
            continue
        leads = [f for f in firms if f.get("role") == "주계약업체"]
        mems = [f for f in firms if f.get("role") == "도급업체"]
        lead_listed = any(
            "".join(ch for ch in str(f.get("bizno") or "") if ch.isdigit()) in listed_bz for f in leads
        )
        mem_listed = any(
            "".join(ch for ch in str(f.get("bizno") or "") if ch.isdigit()) in listed_bz for f in mems
        )
        if mem_listed and not lead_listed:
            ext_contracts += 1

    return {
        "generated_at": stamp_text(load_run_status(repo_root)),
        "summary": {
            "contracts": len(contracts),
            "multi_firm": multi_n,
            "large_joint": len(large_joint),
            "large_joint_min_eok": LARGE_JOINT_MIN_EOK,
            "external_lead_to_listed": ext_contracts,
            "xenon_lead": xenon_lead,
            "xenon_member": xenon_member,
        },
        "edges": edge_rows[:200],
        "leaders": _roll(leaders)[:50],
        "members": _roll(members)[:50],
        "large_joint": large_joint,
        "xenon": {
            "bizno": XENON_BIZNO,
            "lead": xenon_lead,
            "member": xenon_member,
            "contracts": xenon_contracts,
        },
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
    bidders = _bidders_payload(repo_root)
    agencies = _agencies_payload(repo_root)
    competitors = build_spa_competitors(repo_root)
    consortium = _consortium_payload(repo_root)
    decisions_path = repo_root / "data" / "seed" / "xenon_decisions.json"
    decisions = (
        json.loads(decisions_path.read_text(encoding="utf-8"))
        if decisions_path.is_file()
        else {"decisions": []}
    )
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
            json.dumps(bidders, ensure_ascii=False),
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
        (out / "consortium-index.json").write_text(
            json.dumps(consortium, ensure_ascii=False),
            encoding="utf-8",
        )
        (out / "decisions.json").write_text(
            json.dumps(decisions, ensure_ascii=False, indent=2),
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
        "bidders": len(bidders.get("firms") or []),
        "agencies": len(agencies.get("agencies") or []),
        "competitors": len(competitors.get("firms") or []),
        "consortium_edges": len(consortium.get("edges") or []),
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
