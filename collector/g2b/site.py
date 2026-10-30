"""Shared page shell for fully generated pages (home, 사전규격, 사업 상세)."""

from __future__ import annotations

import html
from typing import Any

from .assets import ASSET_VER

NAV_ITEMS = (
    ("index.html", "홈"),
    ("band.html", "8~30억 분석"),
    ("awards.html", "수주 현황"),
    ("prespecs.html", "사전규격"),
    ("competitors.html", "국내 전문기업"),
    ("reports/index.html", "리포트 목록"),
    ("deliverables.html", "산출물 안내"),
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
    links = "".join(f'<a href="{prefix}{href}">{label}</a>' for href, label in NAV_ITEMS)
    return f'<nav class="top"><b>공공 AI Agent 시장 리서치</b>{links}</nav>'


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
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap">'
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
