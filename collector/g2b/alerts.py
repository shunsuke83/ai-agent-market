"""Rule-based alerts: RSS per rule (feeds/<id>.xml), deadline calendar (feeds/deadlines.ics),
Slack digest of newly matched notices/사전규격, and the alerts.html subscribe page."""

from __future__ import annotations

import html
import json
import os
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import yaml

from .classify import ROOT as COLLECTOR_ROOT
from .classify import load_keywords
from .firms import load_firms
from .normalize import prespec_excluded
from .render import KST, _fmt_budget, _g2b_href
from .site import detail_href, page

DEFAULT_ALERTS = COLLECTOR_ROOT / "config" / "alerts.yaml"
FEEDS_DIR = "feeds"
STATE_REL = Path("data") / "alerts_state.json"
FEED_LIMIT = 50
STATE_KEEP_DAYS = 180
KIND_LABEL = {"notice": "공고", "prespec": "사전규격"}


def load_alert_config(path: Path | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_ALERTS, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fields(v: Any) -> list[str]:
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def notice_item(n: dict[str, Any], site_url: str) -> dict[str, Any]:
    href = detail_href(n)
    return {
        "key": f"n:{n.get('bid_no')}-{str(n.get('bid_ord') or '000').zfill(3)}",
        "kind": "notice",
        "title": n.get("title") or "",
        "org": n.get("org") or "",
        "scope": n.get("scope"),
        "fields": _fields(n.get("fields")),
        "nature": n.get("nature"),
        "budget_eok": n.get("budget_eok"),
        "date": n.get("notice_date") or "",
        "deadline": n.get("close_at") or "",
        "url": site_url + href if href else html.unescape(_g2b_href(n)),
        "raw": n,
    }


def prespec_item(p: dict[str, Any], site_url: str) -> dict[str, Any]:
    return {
        "key": f"p:{p.get('prespec_no')}",
        "kind": "prespec",
        "title": p.get("title") or "",
        "org": p.get("org") or "",
        "scope": p.get("scope"),
        "fields": _fields(p.get("fields")),
        "nature": p.get("nature"),
        "budget_eok": p.get("asign_budget_eok"),
        "date": p.get("registered_date") or "",
        "deadline": p.get("opinion_close_at") or "",
        "url": site_url + "prespecs.html",
        "raw": p,
    }


def build_items(
    notices: list[dict[str, Any]], prespecs: list[dict[str, Any]], site_url: str
) -> list[dict[str, Any]]:
    """Every alertable item, minus 장비·감리·교육행사 (same rule as the home page) and 취소공고."""
    kw = load_keywords()
    items = [
        notice_item(n, site_url)
        for n in notices
        if n.get("bid_no") and n.get("ntce_kind") != "취소공고" and not prespec_excluded(n, kw)
    ]
    items += [
        prespec_item(p, site_url)
        for p in prespecs
        if p.get("prespec_no") and not prespec_excluded(p, kw)
    ]
    return items


def matches(item: dict[str, Any], match: dict[str, Any]) -> bool:
    if match.get("kinds") and item["kind"] not in match["kinds"]:
        return False
    if match.get("scope") and item["scope"] not in match["scope"]:
        return False
    if match.get("nature") and item["nature"] not in match["nature"]:
        return False
    if match.get("fields") and not set(match["fields"]) & set(item["fields"]):
        return False
    if match.get("keywords") and not any(k in item["title"] for k in match["keywords"]):
        return False
    if match.get("orgs") and not any(o in item["org"] for o in match["orgs"]):
        return False
    budget = item["budget_eok"]
    if match.get("min_eok") is not None and (budget is None or budget < match["min_eok"]):
        return False
    if match.get("max_eok") is not None and (budget is None or budget > match["max_eok"]):
        return False
    return True


def rule_items(items: list[dict[str, Any]], rule: dict[str, Any]) -> list[dict[str, Any]]:
    got = [i for i in items if matches(i, rule.get("match") or {})]
    got.sort(key=lambda i: (i["date"], i["budget_eok"] or 0), reverse=True)
    return got


def _summary(item: dict[str, Any]) -> str:
    parts = [item["org"]]
    budget = _fmt_budget(item["budget_eok"])
    if budget:
        parts.append(f"{budget}억")
    if item["deadline"]:
        label = "의견 마감" if item["kind"] == "prespec" else "입찰 마감"
        parts.append(f"{label} {item['deadline']}")
    return " · ".join(p for p in parts if p)


def _pub_date(item: dict[str, Any]) -> str:
    try:
        d = datetime.strptime(item["date"][:10], "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError:
        d = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return format_datetime(d)


def build_rss(rule: dict[str, Any], items: list[dict[str, Any]], site_url: str) -> str:
    entries = "".join(
        "<item>"
        f"<title>{xml_escape('[' + KIND_LABEL[i['kind']] + '] ' + i['title'])}</title>"
        f"<link>{xml_escape(i['url'])}</link>"
        f'<guid isPermaLink="false">{xml_escape(i["key"])}</guid>'
        f"<pubDate>{_pub_date(i)}</pubDate>"
        f"<description>{xml_escape(_summary(i))}</description>"
        "</item>"
        for i in items[:FEED_LIMIT]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>{xml_escape('공공 AI 사업 알림 — ' + rule['name'])}</title>"
        f"<link>{xml_escape(site_url)}alerts.html</link>"
        f"<description>{xml_escape(rule['name'] + ' 조건에 맞는 나라장터 AI 공고·사전규격')}</description>"
        "<language>ko</language>"
        f"{entries}</channel></rss>\n"
    )


def _ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets continue on the next line after a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def build_ics(items: list[dict[str, Any]], now: datetime, days: int) -> str:
    """입찰 마감 and 사전규격 의견 마감 within `days` for every item that matched some rule."""
    start = now.strftime("%Y-%m-%d %H:%M")
    end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ai-agent-market//alerts//KO",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:공공 AI 사업 마감",
        "X-WR-TIMEZONE:Asia/Seoul",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Seoul",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0900",
        "TZOFFSETTO:+0900",
        "TZNAME:KST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for i in sorted(items, key=lambda i: i["deadline"]):
        when = i["deadline"]
        if len(when) < 16 or not (start <= when <= end):
            continue
        label = "사전규격 의견 마감" if i["kind"] == "prespec" else "입찰 마감"
        dt = datetime.strptime(when[:16], "%Y-%m-%d %H:%M").strftime("%Y%m%dT%H%M%S")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{i['key'].replace(':', '-')}@ai-agent-market",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Asia/Seoul:{dt}",
            "DURATION:PT30M",
            _fold(f"SUMMARY:{_ics_text(label + ': ' + i['title'])}"),
            _fold(f"DESCRIPTION:{_ics_text(_summary(i) + chr(10) + i['url'])}"),
            _fold(f"URL:{i['url']}"),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def load_state(repo_root: Path) -> dict[str, Any]:
    path = repo_root / STATE_REL
    if not path.exists():
        return {"sent": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(repo_root: Path, state: dict[str, Any], today: date) -> None:
    cutoff = (today - timedelta(days=STATE_KEEP_DAYS)).isoformat()
    state["sent"] = {k: v for k, v in sorted(state.get("sent", {}).items()) if v >= cutoff}
    path = repo_root / STATE_REL
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_by_rule(
    items: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    sent: dict[str, str],
    since: str,
    now_s: str = "",
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Unsent recent items per rule; an item shows under the first rule it matches only.

    Notices whose 입찰 마감 already passed are dropped; a closed 사전규격 still signals a coming 본공고.
    """
    claimed: set[str] = set()
    out = []
    for rule in rules:
        fresh = [
            i for i in rule_items(items, rule)
            if i["key"] not in sent
            and i["key"] not in claimed
            and i["date"] >= since
            and not (i["kind"] == "notice" and i["deadline"] and i["deadline"] < now_s)
        ]
        claimed.update(i["key"] for i in fresh)
        if fresh:
            out.append((rule, fresh))
    return out


def _slack_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slack_text(groups: list[tuple[dict[str, Any], list[dict[str, Any]]]], today: date, limit: int, site_url: str) -> str:
    total = sum(len(g) for _, g in groups)
    lines = [f"*나라장터 AI 새 공고·사전규격 {total}건* ({today.isoformat()})"]
    for rule, got in groups:
        lines.append("")
        lines.append(f"*{_slack_escape(rule['name'])}* — {len(got)}건")
        for i in got[:limit]:
            title = _slack_escape(i["title"]).replace("|", "¦")
            lines.append(f"• [{KIND_LABEL[i['kind']]}] <{i['url']}|{title}>\n    {_slack_escape(_summary(i))}")
        if len(got) > limit:
            lines.append(f"    …외 {len(got) - limit}건 (<{site_url}feeds/{rule['id']}.xml|RSS>)")
    lines.append("")
    lines.append(f"<{site_url}alerts.html|알림 규칙·구독 안내> · <{site_url}index.html|오늘의 사업 기회>")
    return "\n".join(lines)


def firm_change_items(firms: dict[str, dict[str, Any]], sent: dict[str, str], since: str) -> list[dict[str, Any]]:
    """Unsent 조달업체 등록정보 changes recorded since `since`, newest first."""
    out = []
    for bizno, firm in firms.items():
        for c in firm.get("changes") or []:
            key = f"firm:{bizno}:{c.get('date')}:{c.get('field')}"
            if key not in sent and str(c.get("date") or "") >= since:
                out.append({"key": key, "bizno": bizno, "name": firm.get("corp_name") or bizno, **c})
    out.sort(key=lambda i: (i["date"], i["name"]), reverse=True)
    return out


def firm_change_text(items: list[dict[str, Any]], site_url: str, limit: int) -> str:
    lines = [f"*경쟁사 조달업체 등록정보 변경 {len(items)}건*"]
    for i in items[:limit]:
        name = _slack_escape(str(i["name"])).replace("|", "¦")
        change = _slack_escape(f"{i['label']}: {i['from']} → {i['to']}")
        lines.append(f"• <{site_url}bidders.html#{i['bizno']}|{name}> — {change} ({i['date']} 확인)")
    if len(items) > limit:
        lines.append(f"    …외 {len(items) - limit}건")
    return "\n".join(lines)


def post_slack(webhook: str, text: str) -> None:
    import requests

    resp = requests.post(webhook, json={"text": text, "unfurl_links": False}, timeout=30)
    resp.raise_for_status()


def build_alerts_page(config: dict[str, Any], counts: dict[str, int]) -> str:
    site_url = config["site_url"]
    rows = []
    for rule in config["rules"]:
        m = rule.get("match") or {}
        cond = []
        if m.get("kinds"):
            cond.append("·".join(KIND_LABEL[k] for k in m["kinds"]))
        for key, label in (("scope", "범위"), ("nature", "성격"), ("fields", "분야"), ("keywords", "키워드"), ("orgs", "기관")):
            if m.get(key):
                cond.append(f"{label} {', '.join(m[key])}")
        lo, hi = m.get("min_eok"), m.get("max_eok")
        if lo is not None and hi is not None:
            cond.append(f"예산 {lo:g}~{hi:g}억")
        elif lo is not None:
            cond.append(f"예산 {lo:g}억 이상")
        elif hi is not None:
            cond.append(f"예산 {hi:g}억 이하")
        feed = f"{FEEDS_DIR}/{rule['id']}.xml"
        rows.append(
            "<tr>"
            f"<td><b>{html.escape(rule['name'])}</b>"
            f'<div class="meta">{html.escape(" · ".join(cond))}</div></td>'
            f'<td class="num">{counts.get(rule["id"], 0):,}</td>'
            f'<td><a href="{feed}">RSS</a></td>'
            "</tr>"
        )
    ics = f"{site_url}{FEEDS_DIR}/deadlines.ics"
    webcal = "webcal://" + ics.split("://", 1)[1]
    body = (
        '<div class="eyebrow">Alerts</div><h1>알림 구독</h1>'
        '<p class="lede">조건에 맞는 새 AI 공고·사전규격을 RSS로 받고, 입찰 마감·사전규격 의견 마감을 캘린더로 구독하세요. '
        "매일 수집 후 갱신됩니다.</p>"
        "<h2>알림 규칙</h2>"
        '<div class="tbl"><table class="notices"><thead><tr><th>규칙 · 조건</th>'
        '<th class="num">해당 건수</th><th>피드</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        '<p class="note">장비 구매, 감리·PMO·교육·행사성 공고와 취소공고는 뺍니다. '
        "규칙은 <code>collector/config/alerts.yaml</code>에서 바꿉니다.</p>"
        "<h2>마감 캘린더</h2>"
        f'<p>위 규칙 중 하나라도 맞는 사업의 입찰 마감과 사전규격 의견 마감({config.get("calendar_days", 60)}일 이내)을 담은 캘린더입니다.</p>'
        f'<p><a href="{html.escape(webcal, quote=True)}">캘린더 앱으로 구독</a> · '
        f'<a href="{FEEDS_DIR}/deadlines.ics">ICS 파일</a></p>'
        f'<p class="meta">구글 캘린더: 다른 캘린더 추가 → URL로 추가 → <code>{html.escape(ics)}</code></p>'
        "<h2>Slack</h2>"
        "<p>매일 수집 후 새로 걸린 공고·사전규격을 팀 Slack 채널로 보냅니다. 같은 건은 한 번만 보냅니다.</p>"
    )
    return page("알림 구독", body)


def run_alerts(
    repo_root: Path,
    *,
    now: datetime | None = None,
    webhook: str | None = None,
    dry_run: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .pricing import load_notices
    from .prespecs import load_prespecs

    now = now or datetime.now(KST)
    today = now.date()
    config = config or load_alert_config()
    site_url = config["site_url"]
    rules = config["rules"]
    items = build_items(load_notices(repo_root), load_prespecs(repo_root), site_url)

    feeds = repo_root / FEEDS_DIR
    feeds.mkdir(exist_ok=True)
    matched: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for rule in rules:
        got = rule_items(items, rule)
        counts[rule["id"]] = len(got)
        matched.update((i["key"], i) for i in got)
        (feeds / f"{rule['id']}.xml").write_text(build_rss(rule, got, site_url), encoding="utf-8")
    keep = {f"{r['id']}.xml" for r in rules} | {"deadlines.ics"}
    for path in feeds.glob("*.xml"):
        if path.name not in keep:
            path.unlink()
    (feeds / "deadlines.ics").write_text(
        build_ics(list(matched.values()), now, int(config.get("calendar_days", 60))), encoding="utf-8", newline=""
    )
    (repo_root / "alerts.html").write_text(build_alerts_page(config, counts), encoding="utf-8")

    state = load_state(repo_root)
    since = (today - timedelta(days=int(config.get("slack_max_age_days", 7)))).isoformat()
    groups = new_by_rule(items, rules, state.get("sent", {}), since, now.strftime("%Y-%m-%d %H:%M"))
    changes = firm_change_items(load_firms(repo_root), state.get("sent", {}), since)
    new_count = sum(len(g) for _, g in groups)
    summary: dict[str, Any] = {"rules": counts, "new": new_count, "firm_changes": len(changes), "slack": "skipped"}
    if not groups and not changes:
        summary["slack"] = "nothing new"
        return summary
    limit = int(config.get("slack_limit_per_rule", 15))
    parts = [slack_text(groups, today, limit, site_url)] if groups else []
    if changes:
        parts.append(firm_change_text(changes, site_url, limit))
    text = "\n\n".join(parts)
    if dry_run:
        print(text)
        summary["slack"] = "dry run"
        return summary
    webhook = webhook if webhook is not None else os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        summary["slack"] = "no SLACK_WEBHOOK_URL"
        return summary
    post_slack(webhook, text)
    sent = state.setdefault("sent", {})
    for i in [i for _, got in groups for i in got] + changes:
        sent[i["key"]] = today.isoformat()
    save_state(repo_root, state, today)
    summary["slack"] = "sent"
    return summary
