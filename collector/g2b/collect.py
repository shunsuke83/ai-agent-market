from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .classify import classify_title, load_keywords
from .extract_html import bootstrap_all
from .normalize import (
    apply_awards_to_notices,
    apply_bidders_to_notice,
    in_band,
    merge_by_bid,
    normalize_award_item,
    normalize_bid_item,
    sanitize_notice_money_fields,
    sort_notices,
    utc_now_iso,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_bootstrap(args: argparse.Namespace) -> int:
    from .seed import seed_path

    out = Path(args.out)
    if out.resolve() == seed_path(ROOT).resolve():
        print("error: refusing to overwrite the frozen editorial seed", file=sys.stderr)
        return 2
    payload = bootstrap_all(ROOT)
    payload["generated_at"] = utc_now_iso()
    payload["mode"] = "bootstrap_html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out} — "
        f"band_notices={len(payload['band_notices'])}, "
        f"large_awards={len(payload['large_awards'])}, "
        f"competitors={len(payload['competitors_overview'])}"
    )
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    from .client import G2BClient, G2BError

    rules = load_keywords()
    start = _parse_date(args.since or rules["filters"]["history_start"])
    end = _parse_date(args.until) if args.until else date.today()
    if args.days:
        start = end - timedelta(days=args.days)

    try:
        client = G2BClient()
    except G2BError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"Collecting G2B bids {start} → {end} …")
    raw = client.search_bids_ai(start, end)
    print(f"Raw unique notices: {len(raw)}")

    normalized: list[dict[str, Any]] = []
    for item in raw:
        n = normalize_bid_item(item, rules)
        if n:
            normalized.append(n)
    print(f"After AI classify: {len(normalized)}")

    band = [n for n in normalized if in_band(n, rules)]
    print(f"In 8~30억 band: {len(band)}")

    existing: list[dict[str, Any]] = []
    out = Path(args.out)
    if out.exists() and not args.replace:
        prev = json.loads(out.read_text(encoding="utf-8"))
        existing = prev.get("notices") or prev.get("band_notices") or []

    merged = sort_notices(merge_by_bid(existing, normalized if args.all_budgets else band))

    award_stats: dict[str, Any] = {"fetched": 0, "updated": 0}
    if not args.skip_awards:
        print(f"Fetching Scsbid awards {start} → {end} …")
        raw_awards = client.fetch_awards_range(start, end)
        awards = [a for a in (normalize_award_item(x) for x in raw_awards) if a]
        print(f"Award rows (normalized): {len(awards)}")
        merged, n_upd = apply_awards_to_notices(merged, awards)
        merged = sort_notices(merged)
        award_stats = {"fetched": len(awards), "updated": n_upd}
        print(f"Notices updated with award fields: {n_upd}")

    payload = {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "mode": "g2b_api",
        "range": {"since": start.isoformat(), "until": end.isoformat()},
        "notices": merged,
        "stats": {
            "raw": len(raw),
            "classified": len(normalized),
            "stored": len(merged),
            "band": sum(1 for n in merged if in_band(n, rules)),
            "with_winner": sum(1 for n in merged if n.get("winner")),
            "awards": award_stats,
            "scope": {
                "생성형·Agent": sum(1 for n in merged if n.get("scope") == "생성형·Agent"),
                "AI SW 확대": sum(1 for n in merged if n.get("scope") == "AI SW 확대"),
            },
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(merged)} notices)")
    return 0


def cmd_enrich_awards(args: argparse.Namespace) -> int:
    """Fill winner/bid_count/award_amount on existing notices.json via Scsbid API."""
    from .client import G2BClient, G2BError

    out = Path(args.out)
    if not out.exists():
        print(f"error: {out} not found", file=sys.stderr)
        return 2
    try:
        client = G2BClient()
    except G2BError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    payload = json.loads(out.read_text(encoding="utf-8"))
    notices: list[dict[str, Any]] = list(payload.get("notices") or [])
    if not notices:
        print("No notices to enrich")
        return 0

    end = _parse_date(args.until) if args.until else date.today()
    if args.days:
        start = end - timedelta(days=args.days)
    elif args.since:
        start = _parse_date(args.since)
    else:
        # Cover open_dates present in file (capped)
        dates = [_parse_date(n["open_date"]) for n in notices if n.get("open_date")]
        start = min(dates) if dates else end - timedelta(days=90)
        # Guard: full history month-walk can be very long — allow override
        if (end - start).days > args.max_span_days:
            start = end - timedelta(days=args.max_span_days)
            print(f"Clamped award fetch window to last {args.max_span_days} days")

    print(f"Enrich awards {start} → {end} for {len(notices)} notices …")
    try:
        raw_awards = client.fetch_awards_range(start, end)
    except G2BError as e:
        # Range listing 500s now and then; per-bid lookups below can still make progress.
        print(f"::warning::award range fetch failed, continuing with per-bid lookups: {e}")
        raw_awards = []
    awards = [a for a in (normalize_award_item(x) for x in raw_awards) if a]
    print(f"Award rows: {len(awards)}")
    merged, n_upd = apply_awards_to_notices(notices, awards)

    # Optional per-bid lookup for still-missing winners (or award amounts) with past open_date
    missing = [
        n
        for n in merged
        if (not n.get("winner") or n.get("award_amount_eok") in (None, ""))
        and n.get("bid_no")
        and n.get("open_date")
        and n["open_date"] <= end.isoformat()
        and n.get("ntce_kind") != "취소공고"
        and n.get("status") not in ("유찰", "재공고됨")
    ]
    overdue_before = (end - timedelta(days=60)).isoformat()

    def _lookup_priority(n: dict[str, Any]) -> tuple[str, int, int, float]:
        # Least recently looked up first (rotation), then 개찰 확인 필요 (opened > 60 days
        # ago — results should exist by now), then missing winners before missing
        # amounts, then larger budgets.
        overdue = 0 if n["open_date"] <= overdue_before else 1
        try:
            budget = float(n.get("budget_eok") or 0)
        except (TypeError, ValueError):
            budget = 0.0
        return (n.get("award_lookup_at") or "", overdue, 1 if n.get("winner") else 0, -budget)

    missing.sort(key=_lookup_priority)
    looked = 0
    if args.lookup_missing and missing:
        limit = args.lookup_limit if args.lookup_limit is not None else len(missing)
        print(f"Per-bid lookup for up to {min(limit, len(missing))} / {len(missing)} missing …")
        extra: list[dict[str, Any]] = []
        today_iso = date.today().isoformat()
        for n in missing[:limit]:
            item = client.fetch_award_by_bid(n["bid_no"], n.get("bid_ord"))
            n["award_lookup_at"] = today_iso
            looked += 1
            if not item:
                continue
            a = normalize_award_item(item)
            if a:
                extra.append(a)
        if extra:
            merged, n2 = apply_awards_to_notices(merged, extra)
            n_upd += n2
        print(
            f"Per-bid hits: {len(extra)} (lookups={looked}, "
            f"api_errors={client.lookup_errors})"
        )

    merged = sort_notices(merged)
    payload["notices"] = merged
    payload["generated_at"] = utc_now_iso()
    stats = payload.setdefault("stats", {})
    stats["with_winner"] = sum(1 for n in merged if n.get("winner"))
    stats["awards_enrich"] = {
        "range": {"since": start.isoformat(), "until": end.isoformat()},
        "fetched": len(awards),
        "updated": n_upd,
        "lookups": looked,
        "lookup_api_errors": client.lookup_errors,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out} — winners={stats['with_winner']}/{len(merged)}, "
        f"updated={n_upd}"
    )
    return 0


def cmd_collect_prespecs(args: argparse.Namespace) -> int:
    """사전규격 (pre-specification) for AI titles → data/prespecs.json."""
    from .client import G2BClient, G2BError
    from .normalize import normalize_prespec_item, prespec_excluded

    end = _parse_date(args.until) if args.until else date.today()
    start = end - timedelta(days=args.days)
    try:
        client = G2BClient()
        raw = client.fetch_prespecs(start, end)
    except G2BError as e:
        print(f"::warning::prespec fetch failed (활용신청 확인 필요?): {e}")
        return 1
    if raw:
        print(f"Prespec item keys: {sorted(k for k in raw[0] if not k.startswith('_'))}")
    rules = load_keywords()
    rows = [r for r in (normalize_prespec_item(x, rules) for x in raw) if r]
    print(f"Prespecs {start} → {end}: raw={len(raw)} ai={len(rows)}")

    out = Path(args.out)
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    by_no = {p["prespec_no"]: p for p in prev.get("prespecs") or []}
    for r in rows:
        by_no[r["prespec_no"]] = {**by_no.get(r["prespec_no"], {}), **r}
    before = len(by_no)
    for p in by_no.values():
        p.update(classify_title(p.get("title") or "", rules))
    by_no = {
        k: p for k, p in by_no.items() if p["scope"] and not prespec_excluded(p, rules)
    }
    if before != len(by_no):
        print(f"Dropped {before - len(by_no)} stored prespecs by current rules")
    merged = sorted(by_no.values(), key=lambda p: p.get("registered_at") or "", reverse=True)
    payload = {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "range": {"since": start.isoformat(), "until": end.isoformat()},
        "prespecs": merged,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(merged)} prespecs)")
    return 0


def _notice_key(n: dict[str, Any]) -> str:
    return f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"


def _bootstrap_award_stubs(repo_root: Path) -> list[dict[str, Any]]:
    """Award rows from the editorial seed (band + large) as notice stubs."""
    from .classify import classify_title
    from .seed import load_seed

    boot = load_seed(repo_root)
    stubs: list[dict[str, Any]] = []
    for section in ("large_awards", "band_notices"):
        for row in boot.get(section) or []:
            if not row.get("bid_no"):
                continue
            title = row.get("title") or ""
            labels = classify_title(title) if title else {}
            stubs.append(
                {
                    "bid_no": row.get("bid_no"),
                    "bid_ord": row.get("bid_ord") or "000",
                    "title": title or None,
                    "org": row.get("org"),
                    "open_date": row.get("open_date") or row.get("notice_date"),
                    "notice_date": row.get("notice_date"),
                    "budget_eok": row.get("budget_eok"),
                    "award_amount_eok": row.get("award_amount_eok")
                    or row.get("win_amount_eok"),
                    "winner": row.get("winner"),
                    "first_rank": row.get("first_rank"),
                    "bid_count": row.get("bid_count"),
                    "second": row.get("second"),
                    "status": row.get("status") or ("낙찰" if row.get("winner") else None),
                    "scope": row.get("scope") or labels.get("scope"),
                    "fields": row.get("fields") or labels.get("fields"),
                    "nature": row.get("nature") or labels.get("nature"),
                    "source": "bootstrap",
                }
            )
    return stubs


def _competitor_alias_index(repo_root: Path) -> dict[str, str]:
    try:
        from .competitors import build_alias_index, load_competitors_config

        return build_alias_index(load_competitors_config())
    except Exception:
        return {}


def cmd_enrich_bidders(args: argparse.Namespace) -> int:
    """Attach per-notice bidder ranking lists via OpengCompt (투찰업체별)."""
    from .client import G2BClient, G2BError, redact_secrets
    from .competitors import match_competitor

    out = Path(args.out)
    if not out.exists():
        print(f"error: {out} not found", file=sys.stderr)
        return 2
    try:
        client = G2BClient()
    except G2BError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    payload = json.loads(out.read_text(encoding="utf-8"))
    notices: list[dict[str, Any]] = list(payload.get("notices") or [])
    by_key = {_notice_key(n): n for n in notices if n.get("bid_no")}

    upserted = 0
    if args.include_bootstrap:
        for stub in _bootstrap_award_stubs(ROOT):
            key = _notice_key(stub)
            if key in by_key:
                # Fill missing award / classify fields on existing notice
                cur = by_key[key]
                for fld in (
                    "winner",
                    "first_rank",
                    "award_amount_eok",
                    "budget_eok",
                    "second",
                    "bid_count",
                    "open_date",
                    "title",
                    "org",
                    "scope",
                    "fields",
                    "nature",
                ):
                    if stub.get(fld) and not cur.get(fld):
                        cur[fld] = stub[fld]
            else:
                by_key[key] = stub
                upserted += 1
        notices = list(by_key.values())

    from .reports import is_core

    alias_index = _competitor_alias_index(ROOT)
    today = date.today().isoformat()

    def _is_target(n: dict[str, Any]) -> bool:
        if not n.get("bid_no"):
            return False
        open_d = n.get("open_date") or n.get("notice_date")
        if open_d and str(open_d) > today:
            return False
        if getattr(args, "core_only", False) and not is_core(n):
            return False
        if n.get("bidders"):
            return bool(args.force)
        if n.get("bidders_empty") and not args.force:
            return False
        return True

    targets = [n for n in notices if _is_target(n)]

    # Priority: competitor win → core AI → has winner → newest
    targets.sort(key=lambda n: n.get("open_date") or "", reverse=True)
    targets.sort(
        key=lambda n: (
            0 if match_competitor(n.get("winner"), alias_index) else 1,
            0 if is_core(n) else 1,
            0 if (n.get("winner") or n.get("bid_count")) else 1,
        )
    )
    if args.limit is not None:
        targets = targets[: args.limit]

    print(
        f"Enrich bidders for {len(targets)} notices "
        f"(bootstrap_upserts={upserted}, core_only={bool(getattr(args, 'core_only', False))}) …"
    )
    updated = 0
    fetched = 0
    empty = 0
    skipped = 0
    consecutive_429 = 0
    # Mutate in place by key so we can checkpoint mid-run
    by_live = {_notice_key(n): n for n in notices if n.get("bid_no")}
    # Preserve notices without bid_no
    extras = [n for n in notices if not n.get("bid_no")]

    def _checkpoint() -> None:
        payload["notices"] = sort_notices(list(by_live.values()) + extras)
        payload["generated_at"] = utc_now_iso()
        stats = payload.setdefault("stats", {})
        stats["with_bidders"] = sum(1 for n in payload["notices"] if n.get("bidders"))
        stats["bidders_enrich"] = {
            "targets": len(targets),
            "fetched": fetched,
            "updated": updated,
            "empty": empty,
            "skipped": skipped,
            "bootstrap_upserts": upserted,
        }
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    for n in targets:
        key = _notice_key(n)
        try:
            rows = client.fetch_bidders_by_bid(n["bid_no"], n.get("bid_ord"))
        except (G2BError, Exception) as e:
            msg = redact_secrets(str(e))
            if getattr(e, "status_code", None) == 429:
                consecutive_429 += 1
                # OpengCompt quota recovers slowly — cool down instead of burning skips.
                try:
                    cool = float(os.environ.get("G2B_429_COOLDOWN", "90"))
                except ValueError:
                    cool = 90.0
                wait = min(300.0, cool * consecutive_429)
                print(f"  429 on {n.get('bid_no')} — cool down {wait:.0f}s ({consecutive_429})")
                _checkpoint()
                time.sleep(wait)
                if consecutive_429 >= 5:
                    print("  OpengCompt still rate-limited — checkpoint and stop")
                    break
                continue
            consecutive_429 = 0
            skipped += 1
            print(f"  skip {n.get('bid_no')}: {msg}")
            if skipped >= 8:
                print("  too many skips — checkpoint and stop")
                _checkpoint()
                break
            continue
        consecutive_429 = 0
        fetched += 1
        if not rows:
            empty += 1
            marked = dict(n)
            marked["bidders_empty"] = True
            by_live[key] = marked
        else:
            merged = apply_bidders_to_notice(n, rows)
            merged.pop("bidders_empty", None)
            by_live[key] = merged
            if merged.get("bidders"):
                updated += 1
        if fetched % 25 == 0:
            print(f"  … {fetched}/{len(targets)} fetched, updated={updated}")
            _checkpoint()

    _checkpoint()
    print(
        json.dumps(
            {
                "path": str(out),
                "with_bidders": payload["stats"]["with_bidders"],
                "updated": updated,
                "fetched": fetched,
                "empty": empty,
                "skipped": skipped,
                "bootstrap_upserts": upserted,
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    from .classify import classify_title

    title = args.title
    print(json.dumps(classify_title(title), ensure_ascii=False, indent=2))
    return 0


def cmd_sanitize_budgets(args: argparse.Namespace) -> int:
    """Repair budget/award fields still stored in 원 instead of 억."""
    out = Path(args.out)
    if not out.exists():
        print(f"error: {out} not found", file=sys.stderr)
        return 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    notices = list(payload.get("notices") or [])
    fixed_n = 0
    out_notices: list[dict[str, Any]] = []
    for n in notices:
        cleaned, changed = sanitize_notice_money_fields(n)
        if changed:
            fixed_n += 1
        out_notices.append(cleaned)
    payload["notices"] = sort_notices(out_notices)
    payload["generated_at"] = utc_now_iso()
    stats = payload.setdefault("stats", {})
    stats["budget_sanitized"] = fixed_n
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(out), "fixed": fixed_n, "total": len(out_notices)}))
    return 0


def cmd_migrate_results(args: argparse.Namespace) -> int:
    """One-off: split unconfirmed 1순위 winners and derived award/budget ratios."""
    from .normalize import split_derived_rate, split_first_rank
    from .seed import seed_path

    summary: dict[str, Any] = {}
    for label, path, key_names in (
        ("notices", Path(args.out), ("notices",)),
        ("seed", seed_path(ROOT), ("band_notices", "large_awards", "needs_confirm")),
    ):
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        ranks = rates = 0
        for k in key_names:
            rows = []
            for n in raw.get(k) or []:
                n, a = split_first_rank(n)
                n, b = split_derived_rate(n)
                ranks += a
                rates += b
                rows.append(n)
            raw[k] = rows
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary[label] = {"first_rank_split": ranks, "derived_rate_split": rates}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


STAGES = ("collect", "prespecs", "awards", "bidders")


def cmd_mark_run(args: argparse.Namespace) -> int:
    """Record per-stage outcomes; last_success_at only moves on success."""
    path = Path(args.out)
    status: dict[str, Any] = {}
    if path.exists():
        status = json.loads(path.read_text(encoding="utf-8"))
    stages = status.setdefault("stages", {})
    now = utc_now_iso()
    for name in STAGES:
        outcome = getattr(args, name, None)
        if not outcome or outcome == "skipped":
            continue
        s = stages.setdefault(name, {})
        s["last_attempt_at"] = now
        s["last_outcome"] = outcome
        if outcome == "success":
            s["last_success_at"] = now
    status["run_id"] = os.environ.get("GITHUB_RUN_ID")
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stages, ensure_ascii=False))
    return 0


def cmd_reclassify(args: argparse.Namespace) -> int:
    """Refresh scope/fields/nature on existing notices.json from keywords.yaml."""
    from .classify import classify_title

    path = Path(args.out)
    raw = json.loads(path.read_text(encoding="utf-8"))
    notices = list(raw.get("notices") or [])
    changed = 0
    for n in notices:
        labels = classify_title(n.get("title") or "")
        before = (n.get("scope"), tuple(n.get("fields") or []), n.get("nature"))
        n["scope"] = labels["scope"]
        n["fields"] = labels["fields"]
        n["nature"] = labels["nature"]
        after = (n.get("scope"), tuple(n.get("fields") or []), n.get("nature"))
        if before != after:
            changed += 1
    dropped = [n for n in notices if not n.get("scope")]
    notices = [n for n in notices if n.get("scope")]
    for n in dropped[:20]:
        print(f"  drop (no AI scope): {n.get('title')}")
    raw["notices"] = notices
    raw["reclassified_at"] = utc_now_iso()
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(path), "notices": len(notices), "changed": changed,
                      "dropped": len(dropped)}, ensure_ascii=False))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .competitors import render_competitors_page
    from .render import render_awards_page, render_band_page, render_index_stamp
    from .reports import render_reports

    targets = args.target
    if "all" in targets:
        targets = ["band", "awards", "index", "competitors", "reports", "prespecs", "details"]
    summary: dict[str, Any] = {}
    if "band" in targets:
        summary["band"] = render_band_page(ROOT)
    if "awards" in targets:
        summary["awards"] = render_awards_page(ROOT)
    if "competitors" in targets:
        summary["competitors"] = render_competitors_page(ROOT)
    if "reports" in targets:
        summary["reports"] = render_reports(ROOT)
    if "prespecs" in targets:
        from .prespecs import render_prespecs_page

        summary["prespecs"] = render_prespecs_page(ROOT)
    if "details" in targets:
        from .detail import render_detail_pages

        summary["details"] = render_detail_pages(ROOT)
    if "index" in targets:
        from .home import render_home

        # Home reads data/reports.json, so it renders after reports.
        summary["index"] = render_home(ROOT)
        render_index_stamp(ROOT, home=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="나라장터 AI Agent market collector")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser(
        "bootstrap",
        help="Extract structured JSON from current HTML pages (migration/recovery only)",
    )
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_bootstrap)

    mg = sub.add_parser(
        "migrate-results",
        help="Split 1순위 out of winner and award/budget out of 낙찰률 (notices + seed)",
    )
    mg.add_argument("--out", default=str(DATA / "notices.json"))
    mg.set_defaults(func=cmd_migrate_results)

    mr = sub.add_parser("mark-run", help="Record stage outcomes in data/run_status.json")
    mr.add_argument("--out", default=str(DATA / "run_status.json"))
    for name in STAGES:
        mr.add_argument(f"--{name}", choices=["success", "failure", "cancelled", "skipped"])
    mr.set_defaults(func=cmd_mark_run)

    c = sub.add_parser("collect", help="Fetch AI notices from 나라장터 Open API")
    c.add_argument("--since", help="YYYY-MM-DD (default: config history_start)")
    c.add_argument("--until", help="YYYY-MM-DD (default: today)")
    c.add_argument("--days", type=int, help="Collect last N days ending at --until/today")
    c.add_argument("--out", default=str(DATA / "notices.json"))
    c.add_argument("--replace", action="store_true", help="Do not merge with existing out file")
    c.add_argument(
        "--all-budgets",
        action="store_true",
        help="Store all classified notices (default: 8~30억 band only)",
    )
    c.add_argument(
        "--skip-awards",
        action="store_true",
        help="Skip Scsbid award enrichment for this collect window",
    )
    c.set_defaults(func=cmd_collect)

    ps = sub.add_parser("collect-prespecs", help="Fetch AI 사전규격 into data/prespecs.json")
    ps.add_argument("--days", type=int, default=14)
    ps.add_argument("--until", help="YYYY-MM-DD (default: today)")
    ps.add_argument("--out", default=str(DATA / "prespecs.json"))
    ps.set_defaults(func=cmd_collect_prespecs)

    e = sub.add_parser(
        "enrich-awards",
        help="Attach Scsbid winner/bid_count/amount onto existing notices.json",
    )
    e.add_argument("--out", default=str(DATA / "notices.json"))
    e.add_argument("--since", help="YYYY-MM-DD award fetch start")
    e.add_argument("--until", help="YYYY-MM-DD award fetch end (default: today)")
    e.add_argument("--days", type=int, help="Fetch awards for last N days")
    e.add_argument(
        "--max-span-days",
        type=int,
        default=120,
        help="When deriving range from notices, cap span (default 120)",
    )
    e.add_argument(
        "--lookup-missing",
        action="store_true",
        help="After range fetch, look up remaining notices by bidNtceNo",
    )
    e.add_argument(
        "--lookup-limit",
        type=int,
        default=None,
        help="Max per-bid lookups when --lookup-missing",
    )
    e.set_defaults(func=cmd_enrich_awards)

    eb = sub.add_parser(
        "enrich-bidders",
        help="Attach OpengCompt bidder rankings (투찰업체별) onto notices.json",
    )
    eb.add_argument("--out", default=str(DATA / "notices.json"))
    eb.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max notices to look up (default: all missing bidders)",
    )
    eb.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even when bidders already present",
    )
    eb.add_argument(
        "--include-bootstrap",
        action="store_true",
        help="Upsert editorial seed band/large awards into notices, then enrich (competitor wins first)",
    )
    eb.add_argument(
        "--core-only",
        action="store_true",
        help="Only enrich core AI natures (구축·ISP·구독·운영)",
    )
    eb.set_defaults(func=cmd_enrich_bidders)

    k = sub.add_parser("classify", help="Classify a single title")
    k.add_argument("title")
    k.set_defaults(func=cmd_classify)

    sb = sub.add_parser(
        "sanitize-budgets",
        help="Convert budget/award fields wrongly stored as 원 into 억",
    )
    sb.add_argument("--out", default=str(DATA / "notices.json"))
    sb.set_defaults(func=cmd_sanitize_budgets)

    rc = sub.add_parser(
        "reclassify",
        help="Re-apply keywords.yaml scope/fields/nature onto notices.json",
    )
    rc.add_argument("--out", default=str(DATA / "notices.json"))
    rc.set_defaults(func=cmd_reclassify)

    r = sub.add_parser(
        "render",
        help="Render static HTML from data/*.json (band + awards + index + competitors + reports)",
    )
    r.add_argument(
        "target",
        nargs="+",
        choices=["band", "awards", "index", "competitors", "reports", "prespecs", "details", "all"],
        help="What to render",
    )
    r.set_defaults(func=cmd_render)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
