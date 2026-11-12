"""Shared page shell for fully generated pages (home, 사전규격, 사업 상세)."""

from __future__ import annotations

import html
import re
from typing import Any

from .assets import ASSET_VER, FONT_LINKS, stamp_asset_versions

NAV_GROUPS = (
    ("", (("index.html", "홈"),)),
    ("시장 분석", (
        ("band.html", "8~30억 분석"),
        ("awards.html", "수주 현황"),
        ("pricing.html", "투찰·경쟁"),
        ("plans.html", "발주 예정"),
        ("prespecs.html", "사전규격"),
    )),
    ("검색", (
        ("bidders.html", "입찰이력 검색"),
        ("agencies.html", "발주기관 검색"),
    )),
    ("기업·리포트", (
        ("competitors.html", "국내 전문기업"),
        ("reports/index.html", "리포트 목록"),
        ("deliverables.html", "산출물 안내"),
    )),
)
NAV_ITEMS = tuple(item for _, items in NAV_GROUPS for item in items)

# Marks the current page's link; report pages map to 리포트 목록. No `</nav>` inside (stamp_shell regex).
_NAV_ACTIVE_JS = (
    "<script>(function(){var n=document.currentScript.parentNode,p=location.pathname;"
    "if(/\\/$/.test(p))p+='index.html';var hit=null;"
    "n.querySelectorAll('.nav-group a').forEach(function(a){var h=new URL(a.href).pathname;"
    "if(h===p||(!hit&&/\\/reports\\//.test(p)&&/reports\\/index\\.html$/.test(h)))hit=a;});"
    "if(hit)hit.setAttribute('aria-current','page');})();</script>"
)

FOOTER = (
    "<footer>데이터 출처: 조달청 나라장터 입찰공고·낙찰정보·사전규격정보(공공데이터포털 Open API), "
    "각 사 공식 발표·보도자료. 사업명 기준 자동 분류라 일부 오분류가 있을 수 있습니다. "
    "확인하지 못한 항목은 '미확인'으로 표시합니다.</footer>"
)


DETAIL_DIR = "bids"


def detail_slug(n: dict[str, Any]) -> str | None:
    bid_no = n.get("bid_no")
    if not bid_no:
        return None
    return f"{bid_no}-{str(n.get('bid_ord') or '000').zfill(3)}"


def detail_href(n: dict[str, Any], prefix: str = "") -> str:
    slug = detail_slug(n)
    return f"{prefix}{DETAIL_DIR}/{slug}.html" if slug else ""


def nav(prefix: str = "") -> str:
    groups = "".join(
        '<div class="nav-group">'
        + (f'<span class="nav-label">{label}</span>' if label else "")
        + "".join(f'<a href="{prefix}{href}">{text}</a>' for href, text in items)
        + "</div>"
        for label, items in NAV_GROUPS
    )
    return (
        f'<nav class="top" aria-label="사이트 메뉴"><a class="brand" href="{prefix}index.html">'
        "공공 AI Agent 시장 리서치</a>"
        f"{groups}{_NAV_ACTIVE_JS}</nav>"
    )


_NAV_RE = re.compile(r'<nav class="top"[^>]*>.*?</nav>', re.S)


def stamp_shell(html_text: str, prefix: str = "") -> str:
    """Hand-edited templates: fresh asset versions and the shared nav."""
    return _NAV_RE.sub(lambda _: nav(prefix), stamp_asset_versions(html_text), count=1)


def page(
    title: str,
    body: str,
    *,
    prefix: str = "",
    scripts: tuple[str, ...] = ("table-sort.js",),
    footer: str = FOOTER,
) -> str:
    head = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{html.escape(title)}</title>"
        + FONT_LINKS +
        '<meta http-equiv="Cache-Control" content="no-cache">'
        f'<link rel="stylesheet" href="{prefix}assets/site.css?v={ASSET_VER}"></head><body>'
        '<div class="wrap">'
    )
    tail = "".join(
        f'<script src="{prefix}assets/{s}?v={ASSET_VER}" defer></script>' for s in scripts
    )
    return head + nav(prefix) + body + footer + f"</div>{tail}</body></html>"


def stat(value: str, label: str) -> str:
    return f'<div class="stat"><div class="v">{value}</div><div class="l">{label}</div></div>'
