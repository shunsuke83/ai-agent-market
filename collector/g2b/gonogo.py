"""Go/No-Go: rule-based fit score of open AI notices against a private company profile.

The profile comes from the COMPANY_PROFILE secret (YAML) and scores go to Slack only — never
to the public site, data/ or the (public) Actions log.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .competitors import normalize_firm
from .render import KST

PROFILE_LOCAL = Path(__file__).resolve().parents[1] / "config" / "profile.local.yaml"

GO, REVIEW, NO_GO = "Go", "검토", "No-Go"
INCUMBENT_YEARS = 3
SIMILAR_MIN = 0.4
_STOP_TOKENS = {
    "사업", "용역", "구축", "고도화", "운영", "유지보수", "유지관리", "시스템", "기반", "위한", "통합",
    "개발", "도입", "서비스", "플랫폼", "재공고", "긴급", "협상", "계약", "년도", "차년도",
}


def load_profile() -> dict[str, Any] | None:
    raw = os.environ.get("COMPANY_PROFILE")
    if raw:
        return yaml.safe_load(raw) or None
    if PROFILE_LOCAL.exists():
        return yaml.safe_load(PROFILE_LOCAL.read_text(encoding="utf-8")) or None
    return None


def _tokens(title: str) -> set[str]:
    words = re.findall(r"[가-힣A-Za-z]{2,}", re.sub(r"\d{2,4}\s*년", " ", title or ""))
    return {w.casefold() for w in words} - _STOP_TOKENS


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


class IncumbentIndex:
    """Who did this 기관's similar AI 용역 lately (data/contracts.json)."""

    def __init__(self, contracts: list[dict[str, Any]], today: date):
        since = (today - timedelta(days=365 * INCUMBENT_YEARS)).isoformat()
        self.by_org: dict[str, list[dict[str, Any]]] = {}
        for c in contracts:
            if c.get("org") and (c.get("signed_date") or "") >= since:
                self.by_org.setdefault(c["org"], []).append(c)

    def find(self, n: dict[str, Any]) -> dict[str, Any] | None:
        best, best_sim = None, SIMILAR_MIN
        for c in self.by_org.get(n.get("org") or "", []):
            if c.get("bid_no") and c["bid_no"] == n.get("bid_no"):
                continue
            sim = similarity(n.get("title") or "", c.get("title") or "")
            if sim >= best_sim:
                best, best_sim = c, sim
        return best


def _hits(title: str, words: list[str] | None) -> list[str]:
    t = title.casefold()
    return [w for w in words or [] if str(w).casefold() in t]


def _days_left(n: dict[str, Any], now: datetime) -> float | None:
    close = n.get("close_at")
    if not close:
        return None
    try:
        dt = datetime.strptime(close, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return None
    return (dt - now).total_seconds() / 86400


def score_notice(
    n: dict[str, Any],
    profile: dict[str, Any],
    now: datetime,
    context: dict[str, Any] | None = None,
    incumbent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """0~100 and reasons. Fit 35 · budget 15 · competition 20 · evaluation 10 · schedule 10 · signals 10."""
    title = n.get("title") or ""
    reasons: list[str] = []
    stops: list[str] = []

    natures = profile.get("natures") or {}
    weight = float(natures.get(n.get("nature") or "", profile.get("other_nature_weight", 0.3)))
    if weight <= 0:
        stops.append(f"제외 성격: {n.get('nature')}")
    fit = 20 * weight
    prefer = _hits(title, profile.get("keywords_prefer"))
    fit += min(15, 5 * len(prefer))
    if prefer:
        reasons.append("키워드 " + ", ".join(prefer))
    avoid = _hits(title, profile.get("keywords_avoid"))
    if avoid:
        stops.append("회피 키워드 " + ", ".join(avoid))
    scopes = profile.get("scopes") or []
    if scopes and n.get("scope") not in scopes:
        fit *= 0.5
    if _hits(n.get("org") or "", profile.get("orgs_prefer")):
        fit += 5
        reasons.append("관심 기관")
    fit = min(35.0, fit)

    budget = n.get("budget_eok")
    b = profile.get("budget_eok") or {}
    lo, hi = b.get("min", 0), b.get("max", 10_000)
    if budget is None:
        money = 7.0
    elif b.get("sweet_min", lo) <= budget <= b.get("sweet_max", hi):
        money = 15.0
    elif lo <= budget <= hi:
        money = 10.0
    else:
        money = 0.0
        shown = round(budget, 1)
        if budget > hi * 2 or budget < lo / 2:
            stops.append(f"예산 {shown:g}억 (기준 {lo:g}~{hi:g}억)")
        else:
            reasons.append(f"예산 {shown:g}억 기준 밖")

    comp = 10.0
    if context and context.get("median_bids") is not None:
        med = context["median_bids"]
        comp = 20.0 if med <= 3 else 14.0 if med <= 6 else 8.0 if med <= 10 else 3.0
        basis = context["basis"].split(" (")[0].replace("같은 사업 성격·예산대", "비슷한 사업")
        reasons.append(f"{basis} 투찰 중앙값 {med:g}곳")
        rivals = {normalize_firm(r) for r in profile.get("rivals") or []}
        strong = [nm for nm, _ in context.get("regulars") or [] if normalize_firm(nm) in rivals]
        if strong:
            comp = max(0.0, comp - 4)
            reasons.append("경쟁사 단골 " + ", ".join(strong))

    tech = n.get("tech_rate")
    evaluation = 5.0 if tech is None else 10.0 if tech >= 80 else 6.0 if tech >= 60 else 3.0
    if tech is not None:
        reasons.append(f"기술 {tech:g}:가격 {n.get('price_rate') or 100 - tech:g}")

    days = _days_left(n, now)
    need = float(profile.get("min_days_to_prepare", 7))
    if days is None:
        schedule = 5.0
    elif days <= 0:
        schedule = 0.0
        stops.append("입찰 마감 지남")
    elif days < need:
        schedule = 0.0
        reasons.append(f"마감까지 {days:.0f}일 (준비 {need:g}일 필요)")
    else:
        schedule = 10.0 if days >= need * 2 else 6.0

    signals = 5.0
    if n.get("rebid"):
        signals += 3
        reasons.append("재공고(유찰 이력)")
    if n.get("prespec_no"):
        signals += 1
    if n.get("plan_no"):
        signals += 1
    if incumbent:
        firms = [f["name"] for f in incumbent.get("firms") or []]
        ours = {normalize_firm(x) for x in [profile.get("name"), *(profile.get("aliases") or [])] if x}
        if ours & {normalize_firm(f) for f in firms}:
            signals += 5
            reasons.append("우리 회사 기존 수행")
        else:
            signals -= 3
            reasons.append(f"기존 수행 {', '.join(firms[:2])} ({(incumbent.get('signed_date') or '')[:4]})")
    if n.get("industry_limit") or n.get("participation_limit") or n.get("record_limit"):
        reasons.append("참가 제한 있음 — 자격 확인")
    signals = max(0.0, min(10.0, signals))

    total = round(fit + money + comp + evaluation + schedule + signals)
    go_at, review_at = profile.get("go_score", 70), profile.get("review_score", 50)
    verdict = NO_GO if stops else GO if total >= go_at else REVIEW if total >= review_at else NO_GO
    return {"score": total, "verdict": verdict, "reasons": stops + reasons}


def candidates(notices: list[dict[str, Any]], now: datetime, days: int) -> list[dict[str, Any]]:
    """Open notices published in the last `days` days, latest 차수 per 공고."""
    since = (now.date() - timedelta(days=days)).isoformat()
    now_s = now.strftime("%Y-%m-%d %H:%M")
    latest: dict[str, dict[str, Any]] = {}
    for n in notices:
        if (n.get("notice_date") or "") < since or (n.get("close_at") or "") <= now_s:
            continue
        if "취소" in (n.get("ntce_kind") or ""):
            continue
        prev = latest.get(n["bid_no"])
        if prev is None or (n.get("bid_ord") or "") > (prev.get("bid_ord") or ""):
            latest[n["bid_no"]] = n
    return list(latest.values())


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "¦")


def slack_text(
    rows: list[tuple[dict[str, Any], dict[str, Any]]],
    today: date,
    site_url: str,
    total: int,
    summaries: dict[str, dict[str, Any]] | None = None,
) -> str:
    from .site import detail_href

    summaries = summaries or {}
    lines = [f"*Go/No-Go 추천 {len(rows)}건* ({today.isoformat()}, 새 공고 {total}건 중)"]
    for n, s in rows:
        url = site_url + detail_href(n) if n.get("bid_no") else n.get("g2b_url") or site_url
        budget = f"{round(n['budget_eok'], 1):g}억" if n.get("budget_eok") is not None else "예산 미상"
        meta = " · ".join(x for x in (n.get("org"), budget, f"마감 {n.get('close_at') or '?'}") if x)
        lines.append(f"• *{s['score']}점 {s['verdict']}* <{url}|{_esc(n.get('title') or '')}>")
        lines.append(f"    {_esc(meta)}")
        if s["reasons"]:
            lines.append(f"    {_esc(' / '.join(s['reasons'][:4]))}")
        overview = ((summaries.get(n.get("bid_no") or "") or {}).get("summary") or {}).get("overview")
        if overview:
            short = overview if len(overview) <= 140 else overview[:139] + "…"
            lines.append(f"    요약: {_esc(short)}")
    return "\n".join(lines)


def run_gonogo(
    repo_root: Path,
    *,
    days: int = 1,
    now: datetime | None = None,
    webhook: str | None = None,
    dry_run: bool = False,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .alerts import load_alert_config, post_slack
    from .plans import load_contracts
    from .pricing import ContextIndex, load_notices

    profile = profile or load_profile()
    if not profile:
        return {"skipped": "COMPANY_PROFILE not set"}
    from .gonogo_policy import GO as POLICY_GO, NO_GO as POLICY_NO_GO, is_policy_profile, score_policy, slack_text_policy
    from .normalize import load_keywords
    from .rfp import load_summaries

    now = now or datetime.now(KST)
    notices = load_notices(repo_root)
    contexts = ContextIndex(notices)
    incumbents = IncumbentIndex(load_contracts(repo_root), now.date())
    summaries = load_summaries(repo_root)
    pool = candidates(notices, now, days)
    # Bids the company is already working on (profile.pipeline) are not re-scored.
    pipeline = {str(p.get("bid_no") or "").split("-")[0] for p in profile.get("pipeline") or [] if isinstance(p, dict)}
    pool = [n for n in pool if n.get("bid_no") not in pipeline]
    policy = is_policy_profile(profile)
    if policy:
        out = profile.get("output") or {}
        min_score = out.get("min_score", 50)
        rules = load_keywords()
        scored = [
            (n, score_policy(n, profile, now, contexts.context(n), incumbents.find(n), summaries.get(n["bid_no"]), rules))
            for n in pool
        ]
        picked = [(n, s) for n, s in scored if s["verdict"] != POLICY_NO_GO and s["score"] >= min_score]
        picked.sort(key=lambda r: (r[1]["verdict"] != POLICY_GO, -r[1]["score"]))
        picked = picked[: int(out.get("top_n", 10))]
    else:
        scored = [(n, score_notice(n, profile, now, contexts.context(n), incumbents.find(n))) for n in pool]
        min_score = profile.get("min_score", profile.get("review_score", 50))
        picked = [(n, s) for n, s in scored if s["verdict"] != NO_GO and s["score"] >= min_score]
        picked.sort(key=lambda r: -r[1]["score"])
        picked = picked[: int(profile.get("top_n", 10))]
    # Counts only: Actions logs of a public repo are public.
    summary: dict[str, Any] = {"candidates": len(pool), "picked": len(picked)}
    if not picked:
        summary["slack"] = "nothing to send"
        return summary
    site_url = load_alert_config()["site_url"]
    if policy:
        text = slack_text_policy(picked, now.date(), site_url, len(pool), profile, summaries)
    else:
        text = slack_text(picked, now.date(), site_url, len(pool), summaries)
    if dry_run:
        print(text)
        summary["slack"] = "dry run"
        return summary
    hook = os.environ.get("SLACK_WEBHOOK_URL", "") if webhook is None else webhook
    if not hook:
        summary["slack"] = "no webhook"
        return summary
    post_slack(hook, text)
    summary["slack"] = "sent"
    return summary
