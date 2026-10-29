from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .classify import load_keywords
from .extract_html import bootstrap_all
from .normalize import (
    apply_awards_to_notices,
    in_band,
    merge_by_bid,
    normalize_award_item,
    normalize_bid_item,
    sort_notices,
    utc_now_iso,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_bootstrap(args: argparse.Namespace) -> int:
    payload = bootstrap_all(ROOT)
    payload["generated_at"] = utc_now_iso()
    payload["mode"] = "bootstrap_html"
    out = Path(args.out)
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
    raw_awards = client.fetch_awards_range(start, end)
    awards = [a for a in (normalize_award_item(x) for x in raw_awards) if a]
    print(f"Award rows: {len(awards)}")
    merged, n_upd = apply_awards_to_notices(notices, awards)

    # Optional per-bid lookup for still-missing winners with past open_date
    missing = [
        n
        for n in merged
        if not n.get("winner")
        and n.get("bid_no")
        and n.get("open_date")
        and n["open_date"] <= end.isoformat()
    ]
    looked = 0
    if args.lookup_missing and missing:
        limit = args.lookup_limit if args.lookup_limit is not None else len(missing)
        print(f"Per-bid lookup for up to {min(limit, len(missing))} / {len(missing)} missing …")
        extra: list[dict[str, Any]] = []
        for n in missing[:limit]:
            item = client.fetch_award_by_bid(n["bid_no"], n.get("bid_ord"))
            looked += 1
            if not item:
                continue
            a = normalize_award_item(item)
            if a:
                extra.append(a)
        if extra:
            merged, n2 = apply_awards_to_notices(merged, extra)
            n_upd += n2
            print(f"Per-bid hits: {len(extra)} (lookups={looked})")

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
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out} — winners={stats['with_winner']}/{len(merged)}, "
        f"updated={n_upd}"
    )
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    from .classify import classify_title

    title = args.title
    print(json.dumps(classify_title(title), ensure_ascii=False, indent=2))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from .render import render_awards_page, render_band_page, render_index_stamp

    targets = args.target
    if "all" in targets:
        targets = ["band", "awards", "index"]
    summary: dict[str, Any] = {}
    if "band" in targets:
        summary["band"] = render_band_page(ROOT)
    if "awards" in targets:
        summary["awards"] = render_awards_page(ROOT)
    if "index" in targets:
        summary["index"] = render_index_stamp(ROOT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="나라장터 AI Agent market collector")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap", help="Extract structured JSON from current HTML pages")
    b.add_argument("--out", default=str(DATA / "bootstrap.json"))
    b.set_defaults(func=cmd_bootstrap)

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

    k = sub.add_parser("classify", help="Classify a single title")
    k.add_argument("title")
    k.set_defaults(func=cmd_classify)

    r = sub.add_parser(
        "render",
        help="Render static HTML from data/*.json (band + awards + index)",
    )
    r.add_argument(
        "target",
        nargs="+",
        choices=["band", "awards", "index", "all"],
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
