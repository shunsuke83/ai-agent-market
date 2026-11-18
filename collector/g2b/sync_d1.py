"""Upsert notices.json (+ fit scores) into Cloudflare D1 via HTTP API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gonogo import load_profile
from .gonogo_policy import score_policy
from .classify import load_keywords
from .normalize import list_exclude_reason, list_excluded, read_notices, sort_notices
from .render import KST
from .rfp import load_summaries

D1_BATCH = 25  # statements per HTTP call (D1 API limit is higher; stay conservative)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _d1_query(
    account_id: str,
    database_id: str,
    token: str,
    sql: str,
    params: list[Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
    body = {"sql": sql}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"D1 HTTP {e.code}: {detail}") from e
    if not payload.get("success"):
        raise RuntimeError(f"D1 error: {payload.get('errors')}")
    return payload


def _row(
    n: dict[str, Any],
    *,
    rules: dict[str, Any],
    profile: dict[str, Any] | None,
    now: datetime,
    summaries: dict[str, dict[str, Any]],
    updated_at: str,
) -> tuple[str, list[Any]]:
    bid = n.get("bid_no") or ""
    ord_ = n.get("bid_ord") or "000"
    soft = 1 if list_excluded(n, rules) else 0
    reason = list_exclude_reason(n, rules) if soft else None
    fit_verdict = fit_score = None
    fit_reasons: list[str] = []
    if profile:
        scored = score_policy(n, profile, now, summary=summaries.get(bid), rules=rules)
        fit_verdict = scored.get("verdict")
        fit_score = scored.get("score")
        fit_reasons = list(scored.get("reasons") or [])

    slim = {k: v for k, v in n.items() if k not in ("_soft_excluded", "_exclude_reason")}
    sql = (
        "INSERT INTO notices ("
        "bid_no, bid_ord, title, org, scope, nature, fields_json, budget_eok, notice_date, "
        "close_at, open_date, open_at, contract_method, ntce_kind, winner, first_rank, bid_count, "
        "award_amount_eok, win_rate_pct, g2b_url, soft_excluded, exclude_reason, "
        "fit_verdict, fit_score, fit_reasons_json, payload_json, updated_at"
        ") VALUES ("
        "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?"
        ") ON CONFLICT(bid_no, bid_ord) DO UPDATE SET "
        "title=excluded.title, org=excluded.org, scope=excluded.scope, nature=excluded.nature, "
        "fields_json=excluded.fields_json, budget_eok=excluded.budget_eok, "
        "notice_date=excluded.notice_date, close_at=excluded.close_at, open_date=excluded.open_date, "
        "open_at=excluded.open_at, contract_method=excluded.contract_method, ntce_kind=excluded.ntce_kind, "
        "winner=excluded.winner, first_rank=excluded.first_rank, bid_count=excluded.bid_count, "
        "award_amount_eok=excluded.award_amount_eok, win_rate_pct=excluded.win_rate_pct, "
        "g2b_url=excluded.g2b_url, soft_excluded=excluded.soft_excluded, "
        "exclude_reason=excluded.exclude_reason, fit_verdict=excluded.fit_verdict, "
        "fit_score=excluded.fit_score, fit_reasons_json=excluded.fit_reasons_json, "
        "payload_json=excluded.payload_json, updated_at=excluded.updated_at"
    )
    bid_count = n.get("bid_count")
    try:
        bid_count_i = int(float(bid_count)) if bid_count not in (None, "") else None
    except (TypeError, ValueError):
        bid_count_i = None
    params: list[Any] = [
        bid,
        ord_,
        n.get("title"),
        n.get("org"),
        n.get("scope"),
        n.get("nature"),
        json.dumps(n.get("fields") or [], ensure_ascii=False),
        n.get("budget_eok"),
        n.get("notice_date"),
        n.get("close_at"),
        n.get("open_date"),
        n.get("open_at"),
        n.get("contract_method"),
        n.get("ntce_kind"),
        n.get("winner"),
        n.get("first_rank"),
        bid_count_i,
        n.get("award_amount_eok"),
        n.get("win_rate_pct"),
        n.get("g2b_url"),
        soft,
        reason,
        fit_verdict,
        fit_score,
        json.dumps(fit_reasons, ensure_ascii=False),
        json.dumps(slim, ensure_ascii=False),
        updated_at,
    ]
    return sql, params


def sync_notices_to_d1(
    repo_root: Path,
    *,
    account_id: str | None = None,
    database_id: str | None = None,
    token: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID") or ""
    database_id = database_id or os.environ.get("CLOUDFLARE_D1_DATABASE_ID") or ""
    token = token or os.environ.get("CLOUDFLARE_API_TOKEN") or ""
    if not dry_run and (not account_id or not database_id or not token):
        return {
            "skipped": "missing CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_D1_DATABASE_ID / CLOUDFLARE_API_TOKEN",
        }

    rules = load_keywords()
    profile = load_profile()
    summaries = load_summaries(repo_root)
    now = datetime.now(KST)
    updated_at = _utc_now()
    path = repo_root / "data" / "notices.json"
    notices = sort_notices(read_notices(path, collapse=True))
    if limit is not None:
        notices = notices[:limit]

    statements: list[tuple[str, list[Any]]] = []
    for n in notices:
        if not n.get("bid_no"):
            continue
        statements.append(
            _row(n, rules=rules, profile=profile, now=now, summaries=summaries, updated_at=updated_at)
        )

    meta_sql = (
        "INSERT INTO meta(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
    )
    meta_rows = [
        (meta_sql, ["synced_at", updated_at, updated_at]),
        (meta_sql, ["notice_count", str(len(statements)), updated_at]),
        (meta_sql, ["fit_enabled", "1" if profile else "0", updated_at]),
    ]

    if dry_run:
        return {
            "dry_run": True,
            "notices": len(statements),
            "fit_enabled": bool(profile),
            "sample": statements[0][1][:8] if statements else None,
        }

    upserted = 0
    for i in range(0, len(statements), D1_BATCH):
        chunk = statements[i : i + D1_BATCH]
        # D1 HTTP "query" runs one statement; loop within batch for clarity/errors.
        for sql, params in chunk:
            _d1_query(account_id, database_id, token, sql, params)
            upserted += 1
    for sql, params in meta_rows:
        _d1_query(account_id, database_id, token, sql, params)

    return {
        "upserted": upserted,
        "fit_enabled": bool(profile),
        "synced_at": updated_at,
        "database_id": database_id,
    }
