"""index.html: 오늘의 사업 기회 (마감 임박·새 공고·의견 접수 중 사전규격·최근 개찰) + 분석 링크."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .classify import load_keywords
from .normalize import prespec_excluded
from .prespecs import STATUS_OPEN, load_prespecs, prespec_status
from .render import (
    KST,
    _fmt_budget,
    infer_status,
    load_run_status,
    stamp_text,
    title_link,
)
from .site import page, stat

DEADLINE_DAYS = 7
NEW_DAYS = 7
OPENED_DAYS = 14
LIMIT = 15

# Editorial blocks of the old hand-written home that no collector owns.
_KEEP_BLOCK_RE = re.compile(
    r'<h2>AI 사업 공고 연도별 추이</h2>.*?<p class="note">.*?</p>', re.DOTALL
)

STATIC_CARDS = (
    '<h2>분석</h2><div class="cards">'
    '<a class="card" href="band.html"><span class="k">예산 8~30억 · 매일 갱신</span>'
    "<span><b>8~30억 원 AI 사업</b><span class=\"d\">발주처, 계약 방식, 낙찰 업체와 투찰 경쟁, "
    "공고별 결과, 후속 사업 후보</span></span><span class=\"go\">열기 →</span></a>"
    '<a class="card" href="awards.html"><span class="k">누적 · 매일 갱신</span>'
    "<span><b>AI 사업 수주 현황</b><span class=\"d\">대형 사업 낙찰 결과, 수주 상위 업체, "
    "자주 투찰하는 업체</span></span><span class=\"go\">열기 →</span></a>"
    '<a class="card" href="prespecs.html"><span class="k">본공고 전 · 매일 갱신</span>'
    "<span><b>AI 사업 사전규격</b><span class=\"d\">의견 접수 중인 사전규격, 배정예산, "
    "규격서 원문, 연결된 본공고</span></span><span class=\"go\">열기 →</span></a>"
    '<a class="card" href="competitors.html"><span class="k">국내 전문기업 · 실적 매일 갱신</span>'
    "<span><b>공공 생성형 AI 국내 전문기업</b><span class=\"d\">회사·제품·조달 자격·"
    "나라장터 투찰·낙찰 실적</span></span><span class=\"go\">열기 →</span></a></div>"
    '<h2>분기 리서치</h2><div class="cards">'
    '<a class="card" href="research/profiles.html"><span class="k">분기 리서치</span>'
    "<span><b>Gen Agent 업체 프로필</b><span class=\"d\">업체 25곳 비즈니스 전략·프로덕트·과금·"
    "한국 진출</span></span><span class=\"go\">열기 →</span></a>"
    '<a class="card" href="research/architecture.html"><span class="k">분기 리서치</span>'
    "<span><b>Gen Agent 아키텍처 비교</b><span class=\"d\">11계층 기술 구조 비교와 표준화 흐름"
    "</span></span><span class=\"go\">열기 →</span></a>"
    '<a class="card" href="research/market.html"><span class="k">분기 리서치</span>'
    "<span><b>공공 AI 시장 1차 리서치</b><span class=\"d\">언론 보도 기반 공공 AI 사업 54건과 "
    "시장 구조</span></span><span class=\"go\">열기 →</span></a></div>"
)


def _table(head: list[tuple[str, bool]], rows: list[str], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty)}</p>'
    th = "".join(f'<th class="num">{h}</th>' if num else f"<th>{h}</th>" for h, num in head)
    return (
        f'<div class="tbl"><table class="notices home-list"><thead><tr>{th}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _td(v: str, num: bool = False) -> str:
    return f'<td class="num">{v}</td>' if num else f"<td>{v}</td>"


def _result(n: dict[str, Any]) -> str:
    if n.get("winner"):
        return html.escape(n["winner"])
    if n.get("first_rank"):
        return f'{html.escape(n["first_rank"])} <span class="meta">(1순위)</span>'
    return ""


def _report_cards(repo_root: Path) -> str:
    path = repo_root / "data" / "reports.json"
    if not path.exists():
        return ""
    meta = json.loads(path.read_text(encoding="utf-8"))
    cards = []
    weekly = [w for w in meta.get("weekly") or [] if "core_count" in w]
    if weekly:
        w = max(weekly, key=lambda m: (m["year"], m["week"]))
        cards.append(
            f'<a class="card" href="reports/{html.escape(w["file"])}">'
            f'<span class="k">주간 · {w.get("start", "")} ~ {w.get("end", "")}</span>'
            f"<span><b>주간 브리프 {w['year']}년 {w['week']}주차</b>"
            f'<span class="d">신규 핵심 공고 {w["core_count"]}건, 예산 {w["budget_sum"]:,}억, '
            f'개찰 결과 {w["awards_count"]}건</span></span><span class="go">열기 →</span></a>'
        )
    monthly = [m for m in meta.get("monthly") or [] if "core_count" in m]
    if monthly:
        m = max(monthly, key=lambda r: (r["year"], r["month"]))
        prog = " (진행 중)" if m.get("in_progress") else ""
        cards.append(
            f'<a class="card" href="reports/{html.escape(m["file"])}">'
            f'<span class="k">월간 · {m["year"]}-{m["month"]:02d}</span>'
            f"<span><b>월간 리포트 {m['year']}년 {m['month']}월{prog}</b>"
            f'<span class="d">핵심 공고 {m["core_count"]}건, 예산 {round(m["budget_sum"]):,}억</span>'
            '</span><span class="go">열기 →</span></a>'
        )
    if not cards:
        return ""
    return (
        f'<h2>최신 리포트</h2><div class="cards">{"".join(cards)}</div>'
        '<p class="meta" style="margin-top:10px"><a href="reports/index.html">지난 리포트 전체 보기 →</a></p>'
    )


def build_home(
    notices: list[dict[str, Any]],
    prespecs: list[dict[str, Any]],
    run_status: dict[str, Any],
    *,
    now: datetime,
    reports_html: str = "",
    keep_html: str = "",
) -> str:
    rules = load_keywords()
    today = now.date()
    now_s = now.strftime("%Y-%m-%d %H:%M")
    deadline_s = (now + timedelta(days=DEADLINE_DAYS)).strftime("%Y-%m-%d %H:%M")
    min_eok = rules["filters"].get("home_min_eok", 0)
    live = [
        n
        for n in notices
        if (n.get("budget_eok") or 0) >= min_eok and not prespec_excluded(n, rules)
    ]

    open_now = [n for n in live if (n.get("close_at") or "") >= now_s]
    closing = sorted(
        (n for n in open_now if n["close_at"] <= deadline_s), key=lambda n: n["close_at"]
    )
    new_since = (today - timedelta(days=NEW_DAYS - 1)).isoformat()
    new = sorted(
        (n for n in live if (n.get("notice_date") or "") >= new_since),
        key=lambda n: -(n.get("budget_eok") or 0),
    )
    opened_since = (today - timedelta(days=OPENED_DAYS - 1)).isoformat()
    opened = sorted(
        (
            n
            for n in live
            if opened_since <= (n.get("open_date") or "") <= today.isoformat()
            and (n.get("winner") or n.get("first_rank"))
        ),
        key=lambda n: (n.get("open_date") or "", n.get("budget_eok") or 0),
        reverse=True,
    )
    pre_open = sorted(
        (p for p in prespecs if prespec_status(p, now) == STATUS_OPEN),
        key=lambda p: (p.get("opinion_close_at") or "", -(p.get("asign_budget_eok") or 0)),
    )

    stats = (
        '<div class="stats">'
        + stat(f"{len(open_now):,}건", "입찰 접수 중인 AI 공고")
        + stat(f"{len(closing):,}건", f"{DEADLINE_DAYS}일 안에 마감")
        + stat(f"{len(new):,}건", f"최근 {NEW_DAYS}일 새 공고")
        + stat(f"{len(pre_open):,}건", "의견 접수 중 사전규격")
        + stat(f"{len(opened):,}건", f"최근 {OPENED_DAYS}일 개찰 결과")
        + "</div>"
    )

    closing_rows = [
        "<tr>"
        + _td(html.escape(n["close_at"][5:]))
        + _td(html.escape(n.get("org") or ""))
        + _td(title_link(n))
        + _td(html.escape(n.get("scope") or ""))
        + _td(_fmt_budget(n.get("budget_eok")), num=True)
        + _td(html.escape(n.get("contract_method") or ""))
        + "</tr>"
        for n in closing[: LIMIT * 2]
    ]
    new_rows = [
        "<tr>"
        + _td(html.escape(n.get("notice_date") or ""))
        + _td(html.escape(n.get("org") or ""))
        + _td(title_link(n))
        + _td(_fmt_budget(n.get("budget_eok")), num=True)
        + _td(html.escape((n.get("close_at") or "")[:10]))
        + "</tr>"
        for n in new[:LIMIT]
    ]
    pre_rows = [
        "<tr>"
        + _td(html.escape((p.get("opinion_close_at") or "")[:10]))
        + _td(html.escape(p.get("org") or ""))
        + _td(html.escape(p.get("title") or ""))
        + _td(_fmt_budget(p.get("asign_budget_eok")), num=True)
        + "</tr>"
        for p in pre_open[:LIMIT]
    ]
    opened_rows = [
        "<tr>"
        + _td(html.escape(n.get("open_date") or ""))
        + _td(html.escape(n.get("org") or ""))
        + _td(title_link(n))
        + _td(_fmt_budget(n.get("budget_eok")), num=True)
        + _td(html.escape(infer_status(n, today)))
        + _td(_result(n))
        + "</tr>"
        for n in opened[:LIMIT]
    ]

    def more(shown: int, total: int, href: str, label: str) -> str:
        extra = f"{total - shown:,}건 더 · " if total > shown else ""
        return f'<p class="meta" style="margin-top:8px">{extra}<a href="{href}">{label} →</a></p>'

    body = (
        '<div class="eyebrow">Public AI Agent Market Research</div><h1>공공 AI Agent 시장 리서치</h1>'
        '<p class="lede">나라장터 AI 사업의 오늘 기회(마감 임박·새 공고·사전규격)와 '
        "누가 어떤 사업을 수주하는지를 매일 갱신합니다.</p>"
        f'<div class="stamp">{html.escape(stamp_text(run_status))}</div>'
        + stats
        + f"<h2>마감 임박 ({DEADLINE_DAYS}일 이내)</h2>"
        + _table(
            [("입찰 마감", False), ("수요기관", False), ("사업명", False), ("범위", False),
             ("예산(억)", True), ("계약 방식", False)],
            closing_rows,
            f"{DEADLINE_DAYS}일 안에 마감되는 AI 공고가 없습니다.",
        )
        + (more(len(closing_rows), len(closing), "band.html", "8~30억 구간 공고 검색") if closing else "")
        + f"<h2>새 공고 (최근 {NEW_DAYS}일, 예산순)</h2>"
        + _table(
            [("공고일", False), ("수요기관", False), ("사업명", False), ("예산(억)", True),
             ("입찰 마감", False)],
            new_rows,
            f"최근 {NEW_DAYS}일 새 AI 공고가 없습니다.",
        )
        + (more(len(new_rows), len(new), "reports/index.html", "주간·월간 리포트") if new else "")
        + "<h2>의견 접수 중 사전규격</h2>"
        + _table(
            [("의견마감", False), ("수요기관", False), ("사전규격명", False), ("배정예산(억)", True)],
            pre_rows,
            "의견 접수 중인 AI 사전규격이 없습니다.",
        )
        + more(len(pre_rows), len(pre_open), "prespecs.html?status=%EC%9D%98%EA%B2%AC%20%EC%A0%91%EC%88%98%20%EC%A4%91", "사전규격 전체")
        + f"<h2>최근 개찰 결과 ({OPENED_DAYS}일)</h2>"
        + _table(
            [("개찰일", False), ("수요기관", False), ("사업명", False), ("예산(억)", True),
             ("상태", False), ("낙찰자·1순위", False)],
            opened_rows,
            f"최근 {OPENED_DAYS}일 개찰 결과가 없습니다.",
        )
        + (more(len(opened_rows), len(opened), "awards.html", "수주 현황") if opened else "")
        + f'<p class="note">예산 {min_eok:g}억 미만, 장비 구매, 감리·PMO·교육·행사성 공고는 제외합니다. 사업명을 누르면 사업 상세(일정·금액·투찰 업체·관련 사전규격)로 이동합니다.</p>'
        + reports_html
        + STATIC_CARDS
        + keep_html
    )
    return page("공공 AI Agent 시장 리서치", body)


def render_home(repo_root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(KST)
    path = repo_root / "index.html"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    m = _KEEP_BLOCK_RE.search(old)
    notices_path = repo_root / "data" / "notices.json"
    notices = (
        json.loads(notices_path.read_text(encoding="utf-8")).get("notices") or []
        if notices_path.exists()
        else []
    )
    text = build_home(
        notices,
        load_prespecs(repo_root),
        load_run_status(repo_root),
        now=now,
        reports_html=_report_cards(repo_root),
        keep_html=m.group(0) if m else "",
    )
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "stamp": stamp_text(load_run_status(repo_root))}
