"""Shared page shell for fully generated pages (home, 사전규격, 사업 상세)."""

from __future__ import annotations

import html
import re
from typing import Any

from .assets import ASSET_VER, FONT_LINKS, stamp_asset_versions

SITE_TITLE = "AI 사업 입찰·수주 분석"
SITE_URL = "https://shunsuke83.github.io/ai-agent-market/"
SITE_DESC = (
    "나라장터 AI 사업의 입찰·낙찰·사전규격을 매일 모은 공개 분석입니다. "
    "사업명 기준 자동 분류이며, 개인이 운영합니다."
)

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
        ("alerts.html", "알림 구독"),
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
    "각 사 공식 발표·보도자료. 사업명 기준 자동 분류라 일부 오분류가 있을 수 있고, "
    "나라장터 원문과 전수 대조하지 않았습니다. 개인이 운영하는 사이트입니다. "
    "확인하지 못한 항목은 '미확인'으로 표시합니다.</footer>"
)


DETAIL_DIR = "bids"


def detail_slug(n: dict[str, Any]) -> str | None:
    bid_no = n.get("bid_no")
    if not bid_no:
        return None
    return f"{bid_no}-{str(n.get('bid_ord') or '000').zfill(3)}"


def detail_href(n: dict[str, Any], prefix: str = "") -> str:
    """SPA detail path (no .html). Legacy bids/*.html shells are retired."""
    slug = detail_slug(n)
    return f"{prefix}{DETAIL_DIR}/{slug}" if slug else ""


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
        f"{SITE_TITLE}</a>"
        f"{groups}{_NAV_ACTIVE_JS}</nav>"
    )


_NAV_RE = re.compile(r'<nav class="top"[^>]*>.*?</nav>', re.S)


def document_start(
    title: str,
    prefix: str = "",
    description: str | None = None,
    path: str = "",
    *,
    noindex: bool = False,
) -> str:
    desc = description or SITE_DESC
    url = SITE_URL + path.lstrip("/")
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>{html.escape(title)}</title>"
        f'<meta name="description" content="{html.escape(desc)}">'
        f'<meta property="og:title" content="{html.escape(title)}">'
        f'<meta property="og:description" content="{html.escape(desc)}">'
        '<meta property="og:type" content="website">'
        f'<meta property="og:url" content="{html.escape(url)}">'
        f'<link rel="canonical" href="{html.escape(url)}">'
        + robots
        + f'<link rel="icon" href="{prefix}assets/favicon.svg?v={ASSET_VER}" type="image/svg+xml">'
        + FONT_LINKS
        + '<meta http-equiv="Cache-Control" content="no-cache">'
        f'<link rel="stylesheet" href="{prefix}assets/site.css?v={ASSET_VER}"></head><body>'
        f'<a class="skip-link" href="#main">본문으로 건너뛰기</a>'
        '<div class="wrap">'
    )


def ensure_meta(html_text: str, prefix: str = "", path: str = "") -> str:
    """Templates that are not rebuilt from page() still get a description, share tags, and an icon."""
    url = SITE_URL + path.lstrip("/") if path else SITE_URL
    if 'name="description"' not in html_text:
        snippet = (
            f'<meta name="description" content="{html.escape(SITE_DESC)}">'
            f'<meta property="og:title" content="{html.escape(SITE_TITLE)}">'
            f'<meta property="og:description" content="{html.escape(SITE_DESC)}">'
            '<meta property="og:type" content="website">'
            f'<meta property="og:url" content="{html.escape(url)}">'
            f'<link rel="canonical" href="{html.escape(url)}">'
        )
        html_text = html_text.replace("</head>", snippet + "</head>", 1)
    else:
        # U-03: rewrite home-only og:url when we know the real path.
        if path:
            html_text = re.sub(
                r'<meta property="og:url" content="[^"]*">',
                f'<meta property="og:url" content="{html.escape(url)}">',
                html_text,
                count=1,
            )
            if 'rel="canonical"' not in html_text:
                html_text = html_text.replace(
                    "</head>",
                    f'<link rel="canonical" href="{html.escape(url)}"></head>',
                    1,
                )
            else:
                html_text = re.sub(
                    r'<link rel="canonical" href="[^"]*">',
                    f'<link rel="canonical" href="{html.escape(url)}">',
                    html_text,
                    count=1,
                )
    if 'rel="icon"' not in html_text:
        icon = f'<link rel="icon" href="{prefix}assets/favicon.svg?v={ASSET_VER}" type="image/svg+xml">'
        html_text = html_text.replace("</head>", icon + "</head>", 1)
    if 'class="skip-link"' not in html_text:
        html_text = html_text.replace(
            "<body>",
            '<body><a class="skip-link" href="#main">본문으로 건너뛰기</a>',
            1,
        )
    if "<main" not in html_text and "<footer" in html_text:
        html_text = re.sub(
            r"(</nav>)(.*?)(<footer)",
            r'\1<main id="main">\2</main>\3',
            html_text,
            count=1,
            flags=re.S,
        )
    elif '<main id="main"' not in html_text:
        html_text = html_text.replace("<main>", '<main id="main">', 1)
        html_text = html_text.replace("<main ", '<main id="main" ', 1)
    return html_text


def stamp_shell(html_text: str, prefix: str = "", path: str = "") -> str:
    """Hand-edited templates: fresh asset versions, the shared nav, and basic head tags."""
    text = _NAV_RE.sub(lambda _: nav(prefix), html_text, count=1)
    return stamp_asset_versions(ensure_meta(text, prefix, path=path))


def page(
    title: str,
    body: str,
    *,
    prefix: str = "",
    path: str = "",
    scripts: tuple[str, ...] = ("table-sort.js",),
    footer: str = FOOTER,
    description: str | None = None,
    noindex: bool = False,
) -> str:
    head = document_start(title, prefix, description=description, path=path, noindex=noindex)
    ordered: list[str] = []
    for name in (*scripts, "watch.js"):
        if name not in ordered:
            ordered.append(name)
    tail = "".join(
        f'<script src="{prefix}assets/{s}?v={ASSET_VER}" defer></script>' for s in ordered
    )
    return (
        head
        + nav(prefix)
        + f'<main id="main">{body}</main>'
        + footer
        + f"</div>{tail}</body></html>"
    )


def site_base_path() -> str:
    """Absolute site root path for 404.html (served under nested URLs on GitHub Pages)."""
    from urllib.parse import urlparse

    path = urlparse(SITE_URL).path.rstrip("/")
    return f"{path}/" if path else "/"


def write_not_found(repo_root) -> None:
    from pathlib import Path

    prefix = site_base_path()
    body = (
        "<h1>페이지를 찾을 수 없습니다</h1>"
        '<p class="lede">주소가 바뀌었거나 없는 페이지입니다.</p>'
        f'<p><a href="{prefix}index.html">홈으로</a></p>'
    )
    Path(repo_root, "404.html").write_text(
        page(
            "페이지를 찾을 수 없습니다",
            body,
            prefix=prefix,
            path="404.html",
            scripts=(),
        ),
        encoding="utf-8",
    )


_STUB_MARKER = "이 공고 페이지는 더 이상 없습니다"


def write_sitemap(repo_root) -> None:
    import json
    from pathlib import Path

    root = Path(repo_root)
    # SPA client routes (GitHub Pages + Cloudflare). Do not list deleted bids/*.html.
    spa_paths = [
        "",
        "band",
        "awards",
        "pricing",
        "plans",
        "prespecs",
        "bidders",
        "agencies",
        "alerts",
        "competitors",
        "consortium",
        "decisions",
        "deliverables",
        "reports",
    ]
    extra: list[str] = []
    notices_path = root / "data" / "notices.json"
    if notices_path.is_file():
        try:
            raw = json.loads(notices_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        if isinstance(raw, dict):
            notices = raw.get("notices") or raw.get("items") or []
        else:
            notices = raw
        if isinstance(notices, list):
            for n in notices:
                if not isinstance(n, dict):
                    continue
                slug = detail_slug(n)
                if slug:
                    extra.append(f"bids/{slug}")
    for p in sorted((root / "reports").glob("*.html")):
        if p.name == "index.html":
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _STUB_MARKER in body or 'meta http-equiv="refresh"' in body:
            continue
        extra.append(f"reports/{p.name}")
    # Dedupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in spa_paths + extra:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    locs = [f"  <url><loc>{html.escape(SITE_URL + name)}</loc></url>" for name in ordered]
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(locs)
        + "\n</urlset>\n"
    )
    (root / "sitemap.xml").write_text(xml, encoding="utf-8")
    (root / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n",        encoding="utf-8",
    )


def stat(value: str, label: str) -> str:
    return f'<div class="stat"><div class="v">{value}</div><div class="l">{label}</div></div>'
