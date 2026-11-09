"""Go/No-Go for policy profiles (company · capabilities · policy · hard_gates · scoring).

Gates are judged before scoring: fail → NO-GO, unknown → REVIEW (확인 먼저). Score components
without evidence are left out and lower the 근거 충족률 instead of being guessed.
Output goes to Slack only; no 수주 확률 wording.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .competitors import normalize_firm
from .normalize import load_keywords, prespec_excluded

GO, REVIEW, NO_GO = "GO", "REVIEW", "NO-GO"
PASS, FAIL, UNKNOWN = "통과", "미충족", "미확인"

INDUSTRIES = {
    "발전·에너지": ("발전", "전력", "에너지", "가스", "석유", "원자력", "수력", "지역난방"),
    "해양·물류": ("해양", "항만", "해운", "물류", "수산", "선박"),
    "금융": ("은행", "금융", "투자", "보증", "증권", "보험", "신용", "예금", "자산관리", "주택금융"),
}
BUILD_WORDS = ("고도화", "기능 개발", "구축", "플랫폼")
REGIONS = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
    "충북", "충남", "충청북", "충청남", "전북", "전남", "전라북", "전라남", "경북", "경남",
    "경상북", "경상남", "제주",
)
_REGION_RE = re.compile(rf"({'|'.join(REGIONS)})[가-힣]*\s*(?:에\s*)?(?:소재|주된\s*영업소|본사)")
_RECORD_RE = re.compile(r"실적[^\n]{0,40}?(\d+(?:\.\d+)?)\s*억|(\d+(?:\.\d+)?)\s*억[^\n]{0,20}?실적")
QUALIFICATION_SIGNALS = (
    ("sw_business_registration", "소프트웨어사업자", re.compile(r"소프트웨어\s*사업자|1468")),
    ("sme_certificate", "중소기업 확인서", re.compile(r"중소기업\s*확인|중소\s*SW\s*사업자|중소기업자\s*간")),
    ("direct_production_cert", "직접생산확인", re.compile(r"직접\s*생산")),
)
CERT_SIGNALS = (
    ("csap", "CSAP", re.compile(r"CSAP|클라우드\s*보안\s*인증", re.I)),
    ("security_certs", "ISMS·ISO 27001", re.compile(r"ISMS|ISO\s*/?\s*(?:IEC\s*)?27001", re.I)),
    ("gs", "GS인증", re.compile(r"GS\s*인증", re.I)),
)


def is_policy_profile(profile: dict[str, Any]) -> bool:
    return isinstance(profile.get("company"), dict) and "scoring" in profile


def _hits(text: str, words: list[str] | tuple[str, ...] | None) -> list[str]:
    t = (text or "").casefold()
    return [w for w in words or [] if str(w).casefold() in t]


def _industry(org: str) -> str | None:
    for name, words in INDUSTRIES.items():
        if _hits(org, words):
            return name
    return None


def org_kind(org: str) -> str:
    o = org or ""
    if re.search(r"교육청|대학|학교|교육원", o) or re.search(r"(?:특별|광역)?시$|도$|군$|구$|^(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충청|전라|경상|제주)\S*(?:시|도|청)", o):
        return "지자체·교육"
    if re.search(r"공사|공단|진흥원|\(주\)|주식회사|재단|공기업|은행|원$|센터$", o):
        return "공기업·준정부기관"
    if re.search(r"부$|처$|청$|위원회$", o):
        return "중앙부처"
    return "기타"


def business_days_until(now: datetime, close_at: str | None) -> int | None:
    if not close_at:
        return None
    try:
        end = datetime.strptime(close_at, "%Y-%m-%d %H:%M").date()
    except ValueError:
        return None
    day, count = now.date(), 0
    while day < end:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return count


def _summary_text(summary: dict[str, Any] | None) -> str:
    s = (summary or {}).get("summary") or {}
    parts = [*(s.get("requirements") or []), *(s.get("cautions") or []), s.get("evaluation") or ""]
    return "\n".join(parts)


def _own_names(company: dict[str, Any]) -> set[str]:
    return {normalize_firm(x) for x in [company.get("name"), *(company.get("aliases") or [])] if x}


def _is_own_customer(org: str, profile: dict[str, Any]) -> bool:
    customers = (profile.get("track_record") or {}).get("own_customers") or []
    norm = normalize_firm(org or "")
    return any(c and (c in (org or "") or normalize_firm(c) in norm) for c in customers)


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _qualification(
    key: str, label: str, value: Any, text: str, now: datetime, company: dict[str, Any]
) -> tuple[str, str]:
    """Status of one qualification; direct_production_cert may be {세부품명: 유효기간 종료일}."""
    if not isinstance(value, dict):
        return (PASS if value else FAIL if value is False else UNKNOWN), label
    flat, today = _squash(text), now.date().isoformat()
    held = [item for item in value if _squash(item) in flat]
    if held:
        valid = [item for item in held if str(value[item] or "9999") >= today]
        return (PASS, f"{label}({held[0]})") if valid else (FAIL, f"{label} 만료({held[0]})")
    missing = [item for item in company.get("g2b_items_without_direct_production") or [] if _squash(item) in flat]
    if missing:
        return FAIL, f"{label} 없음({missing[0]})"
    return UNKNOWN, f"{label} 품목 확인"


_CODE_LINE = re.compile(r"업종|코드")
_CODE = re.compile(r"(?<!\d)(?!19|20)(\d{4})(?!\d)")
_REGISTERED_LINE = re.compile(r"업종|코드|등록|면허")
# Licensed industries that summaries often name without the code.
INDUSTRY_NAMES = (
    ("0036", re.compile(r"정보통신\s*공사업(?!\s*법)")),
    ("1169", re.compile(r"학술\s*[·ㆍ.]?\s*연구\s*용역")),
    ("9901", re.compile(r"행사\s*대행업")),
)


def _industry_codes(summary: dict[str, Any] | None) -> list[tuple[set[str], bool]]:
    """[(codes, all_required)] per requirement line; '또는' → any, '및' → all."""
    reqs = ((summary or {}).get("summary") or {}).get("requirements") or []
    out = []
    for line in reqs:
        codes = set(_CODE.findall(line)) if _CODE_LINE.search(line) else set()
        named = {code for code, rx in INDUSTRY_NAMES if rx.search(line)} if _REGISTERED_LINE.search(line) else set()
        if named:
            codes |= named | set(_CODE.findall(line))
        if codes:
            out.append((codes, "또는" not in line and bool(re.search(r"\s및\s|\)\s*및", line))))
    return out


_GRADE_BASES = ("AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D")
_GRADE = r"(?<![A-Za-z])(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)\s*([+\-0]?)(?![A-Za-z+\-])"
_CREDIT_MIN_RE = re.compile(r"(?:신용|회사채|기업어음)[^.\n]{0,40}?" + _GRADE + r"\s*(?:등급\s*)?이상")
_CREDIT_SCORED_RE = re.compile(r"경영\s*상태|신용\s*(?:평가)?\s*등급")


def grade_rank(grade: str | None) -> int | None:
    """Lower is better: AAA=0 … D. 'BBB0' equals 'BBB'."""
    m = re.fullmatch(r"\s*" + _GRADE + r"\s*", str(grade or "").upper())
    if not m:
        return None
    return _GRADE_BASES.index(m.group(1)) * 3 + {"+": 0, "-": 2}.get(m.group(2), 1)


def _credit_gate(
    n: dict[str, Any], text: str, credit: dict[str, Any], cfg: dict[str, Any]
) -> tuple[str, str] | None:
    """Notice minimum grade vs ours; scored 경영상태 below review_below → REVIEW; certificate expiry."""
    ours = str(credit.get("grade") or "")
    rank = grade_rank(ours)
    found: list[tuple[str, str]] = []
    mins = [(m.group(1) + m.group(2), grade_rank(m.group(1) + m.group(2))) for m in _CREDIT_MIN_RE.finditer(text)]
    if mins:
        need, need_rank = min(mins, key=lambda g: g[1])
        if rank is None:
            found.append((UNKNOWN, f"요건 {need} 이상 — 보유 등급 미입력"))
        else:
            found.append((PASS if rank <= need_rank else FAIL, f"요건 {need} 이상, 보유 {ours}"))
    elif _CREDIT_SCORED_RE.search(text):
        floor = grade_rank(cfg.get("review_below"))
        if rank is None:
            found.append((UNKNOWN, "경영상태(신용등급) 평가 — 보유 등급 미입력"))
        elif floor is not None and rank > floor:
            found.append((UNKNOWN, f"경영상태(신용등급) 평가 — 보유 {ours}, 감점 가능성 확인"))
    if found:
        until = str(credit.get("valid_until") or "")
        close = str(n.get("close_at") or "")[:10]
        if until and close and until < close:
            found.append((UNKNOWN, f"신용평가 확인서 {until} 만료 — 마감 전 갱신 필요"))
    if not found:
        return None
    statuses = [s for s, _ in found]
    status = FAIL if FAIL in statuses else UNKNOWN if UNKNOWN in statuses else PASS
    return status, ", ".join(label for s, label in found if s == status)


def credit_warning(profile: dict[str, Any], today: Any) -> str:
    credit = (profile.get("company") or {}).get("credit_rating") or {}
    until = str(credit.get("valid_until") or "")
    if until and until < today.isoformat():
        return f"신용평가등급 확인서 유효기간 만료({until}) — 협상에 의한 계약 제출 전 갱신 필요"
    return ""


def judge_gates(
    n: dict[str, Any],
    profile: dict[str, Any],
    now: datetime,
    summary: dict[str, Any] | None,
) -> list[tuple[str, str, str]]:
    """[(gate, 통과/미충족/미확인, 근거)] for gates that have a signal in the notice or its RFP."""
    company = profile.get("company") or {}
    quals = company.get("todo_qualifications") or {}
    gates_cfg = {g.get("id"): g for g in profile.get("hard_gates") or [] if isinstance(g, dict)}
    text = _summary_text(summary)
    out: list[tuple[str, str, str]] = []

    if "region" in gates_cfg:
        found = {m.group(1) for m in _REGION_RE.finditer(text)}
        if found:
            hq = (company.get("hq_region") or "")[:2]
            ok = any(hq and hq.startswith(r[:2]) for r in found)
            out.append(("지역", PASS if ok else FAIL, "·".join(sorted(found)) + " 소재 제한"))

    if "eligibility" in gates_cfg:
        groups = _industry_codes(summary)
        own_codes = {str(c) for c in company.get("g2b_industry_codes") or []}
        groups = groups if own_codes else []
        sw_by_code = any(codes & {"1468", "1426"} for codes, _ in groups)
        found = [_qualification(key, label, quals.get(key), text, now, company)
                 for key, label, rx in QUALIFICATION_SIGNALS
                 if rx.search(text) and not (sw_by_code and key == "sw_business_registration")]
        licensed = {str(c) for c in company.get("g2b_registrable_codes") or []}
        for codes, all_required in groups:
            ok = codes <= own_codes if all_required else bool(codes & own_codes)
            if ok:
                found.append((PASS, "업종 " + "·".join(sorted(codes))))
                continue
            missing = codes - own_codes
            registrable = (missing <= licensed) if all_required else bool(missing & licensed)
            shown = sorted(missing & licensed) if registrable else sorted(missing)
            label = "업종 " + "·".join(shown) + (" — 면허 보유, 나라장터 업종 등록 필요" if registrable else "")
            found.append((UNKNOWN if registrable else FAIL, label))
        if found:
            statuses = [s for s, _ in found]
            status = FAIL if FAIL in statuses else UNKNOWN if UNKNOWN in statuses else PASS
            shown = [label for s, label in found if s == status]
            out.append(("자격", status, ", ".join(shown)))
        elif n.get("industry_limit"):
            out.append(("자격", UNKNOWN, "업종 제한 — 공고서 확인"))

    if "track_record_amount" in gates_cfg:
        record = profile.get("track_record") or {}
        largest = float(record.get("largest_g2b_contract_eok") or 0)
        outside = record.get("non_g2b_amounts_eok")
        known = max(largest, float(outside or 0))
        amounts = [float(a or b) for a, b in _RECORD_RE.findall(text)]
        if amounts:
            need = max(amounts)
            if need <= known:
                out.append(("실적 금액", PASS, f"요건 {need:g}억"))
            elif outside is None:
                out.append(("실적 금액", UNKNOWN, f"요건 {need:g}억 > 나라장터 실적 {largest:g}억"))
            else:
                out.append(("실적 금액", FAIL, f"요건 {need:g}억"))
        elif n.get("record_limit"):
            budget = n.get("budget_eok")
            ok = budget is not None and budget <= known
            out.append(("실적 금액", PASS if ok else UNKNOWN, "실적 제한 — 요건 금액 확인" if not ok else "예산 이하"))

    if "certification" in gates_cfg:
        owned = " ".join(str(c.get("name") or "") for c in company.get("certifications") or [] if isinstance(c, dict))
        for key, label, rx in CERT_SIGNALS:
            if not rx.search(text):
                continue
            if key == "gs":
                out.append(("인증", PASS if "GS" in owned.upper() else UNKNOWN, label))
            else:
                v = quals.get(key)
                out.append(("인증", PASS if v else FAIL if v is False else UNKNOWN, label))

    if "credit" in gates_cfg:
        credit = _credit_gate(n, text, company.get("credit_rating") or {}, gates_cfg["credit"])
        if credit:
            out.append(("신용등급", *credit))

    if "schedule" in gates_cfg:
        need = gates_cfg["schedule"].get("min_business_days_to_deadline")
        left = business_days_until(now, n.get("close_at"))
        if need is not None and left is not None:
            out.append(("일정", PASS if left >= int(need) else FAIL, f"마감까지 영업일 {left}일"))
    return out


def _avoid_hits(n: dict[str, Any], profile: dict[str, Any]) -> list[tuple[str, bool]]:
    """[(desc, excepted)] — excepted means 예외 조건에 걸려 REVIEW로 완화."""
    title, nature = n.get("title") or "", n.get("nature") or ""
    company = profile.get("company") or {}
    products = [str(p.get("name") or "").split(" ")[0] for p in company.get("products") or [] if isinstance(p, dict)]
    out = []
    for rule in (profile.get("policy") or {}).get("avoid") or []:
        sig = rule.get("signals") or {}
        by_title = bool(_hits(title, sig.get("title_keywords")))
        if nature not in (sig.get("nature") or []) and not by_title:
            continue
        # A title that names the avoided thing itself (GPU 서버 구매) is not rescued by 구축 elsewhere.
        excepted = bool(rule.get("exception")) and (
            _is_own_customer(n.get("org") or "", profile)
            or bool(_hits(title, [*products, *(company.get("aliases") or [])]))
            or (not by_title and bool(_hits(title, BUILD_WORDS)))
        )
        out.append((rule.get("desc") or rule.get("id") or "회피 규칙", excepted))
    return out


def _tier(budget: float | None, profile: dict[str, Any]) -> dict[str, Any] | None:
    if budget is None:
        return None
    for t in ((profile.get("policy") or {}).get("budget") or {}).get("tiers") or []:
        bounds = list(t.get("range") or []) + [None, None]
        lo, hi = bounds[0], bounds[1]
        if (lo is None or budget >= lo) and (hi is None or budget < hi):
            return t
    return None


def score_policy(
    n: dict[str, Any],
    profile: dict[str, Any],
    now: datetime,
    context: dict[str, Any] | None = None,
    incumbent: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = rules or load_keywords()
    company = profile.get("company") or {}
    caps = profile.get("capabilities") or {}
    record = profile.get("track_record") or {}
    policy = profile.get("policy") or {}
    weights = (profile.get("scoring") or {}).get("weights") or {}
    title, org = n.get("title") or "", n.get("org") or ""
    reasons: list[str] = []
    stops: list[str] = []
    caps_review: list[str] = []
    notes: list[str] = []

    gates = judge_gates(n, profile, now, summary)
    for name, status, why in gates:
        if status == FAIL:
            stops.append(f"{name} 미충족 ({why})")
        elif status == UNKNOWN:
            caps_review.append(f"{name} 미확인 ({why})")

    if prespec_excluded(n, rules):
        stops.append("사이트 제외 규칙 (감리·PMO·교육·행사·장비 구매)")
    for desc, excepted in _avoid_hits(n, profile):
        if excepted:
            caps_review.append(f"회피 규칙 예외 검토: {desc}")
        else:
            stops.append(f"회피: {desc}")

    budget = n.get("budget_eok")
    own_customer = _is_own_customer(org, profile)
    min_eok = (policy.get("budget") or {}).get("min_eok")
    if budget is not None and min_eok is not None and budget < float(min_eok):
        if own_customer:
            caps_review.append(f"예산 {budget:.1f}억 < {min_eok}억, 기존 고객 후속")
        else:
            stops.append(f"예산 {budget:.1f}억 < 최소 {min_eok}억")
    if n.get("nature") == "ISP·전략" and policy.get("isp_strategy"):
        caps_review.append("ISP: " + " / ".join(policy["isp_strategy"].get("required_checks") or [])[:120])

    parts: dict[str, float | None] = {}
    fields = set(n.get("fields") or [])
    kw = caps.get("title_keywords") or {}
    strong, medium = _hits(title, kw.get("strong")), _hits(title, kw.get("medium"))
    if fields & set(caps.get("core_fields") or []) or strong:
        parts["tech_fit"] = 1.0
    elif fields & set(caps.get("adjacent_fields") or []) or medium:
        parts["tech_fit"] = 0.6
    elif fields & set(caps.get("other_fields") or []):
        parts["tech_fit"] = 0.25
    else:
        parts["tech_fit"] = 0.4
    if strong or medium:
        reasons.append("키워드 " + ", ".join((strong + medium)[:3]))

    customer_industries = {
        _industry(c) for c in record.get("own_customers") or []
    } - {None}
    if own_customer:
        parts["similar_track_record"] = 1.0
        reasons.append("기존 고객 기관")
    elif _industry(org) in customer_industries:
        parts["similar_track_record"] = 0.7
        reasons.append(f"실적 업종({_industry(org)})")
    else:
        parts["similar_track_record"] = 0.4

    gate_cfg = {g.get("id"): g for g in profile.get("hard_gates") or [] if isinstance(g, dict)}
    need_days = (gate_cfg.get("schedule") or {}).get("min_business_days_to_deadline")
    max_builds = (gate_cfg.get("capacity") or {}).get("max_concurrent_builds")
    left = business_days_until(now, n.get("close_at"))
    if need_days is not None and max_builds is not None and left is not None:
        parts["staffing_schedule"] = 1.0 if left >= 2 * int(need_days) else 0.6 if left >= int(need_days) else 0.0
    else:
        parts["staffing_schedule"] = None
        if left is not None:
            notes.append(f"마감까지 영업일 {left}일")

    tier = _tier(budget, profile)
    if budget is None:
        parts["budget_fit"] = None
    else:
        label = (tier or {}).get("label") or ""
        default = str((tier or {}).get("default") or "")
        parts["budget_fit"] = 1.0 if "GO" in default else 0.6 if (tier and (tier.get("range") or [0])[0] < 30) else 0.3
        if tier and "GO" not in default:
            caps_review.append(f"예산 {budget:.1f}억 {label} — 구간 기본 REVIEW")
        else:
            reasons.append(f"예산 {budget:.1f}억 {label}".strip())
    if budget is None:
        caps_review.append("예산 미상")

    kind = org_kind(org)
    parts["domain_org"] = {"공기업·준정부기관": 1.0, "중앙부처": 0.7, "지자체·교육": 0.4}.get(kind, 0.5)

    total_w = sum(float(w) for w in weights.values()) or 100.0
    known_w = sum(float(weights.get(k, 0)) for k, v in parts.items() if v is not None)
    got = sum(float(weights.get(k, 0)) * v for k, v in parts.items() if v is not None)
    score = round(100 * got / known_w) if known_w else 0
    evidence = known_w / total_w

    if context and context.get("median_bids") is not None:
        notes.append(f"비슷한 사업 투찰 중앙값 {context['median_bids']:g}곳")
    if n.get("tech_rate") is not None:
        notes.append(f"기술 {n['tech_rate']:g}:가격 {n.get('price_rate') or 100 - n['tech_rate']:g}")
    if n.get("rebid"):
        notes.append("재공고(유찰 이력)")
    if incumbent:
        firms = incumbent.get("firms") or []
        bizno = re.sub(r"\D", "", str(company.get("bizno") or ""))
        ours = _own_names(company)
        if any(bizno and re.sub(r"\D", "", str(f.get("bizno") or "")) == bizno for f in firms) or ours & {
            normalize_firm(f.get("name") or "") for f in firms
        }:
            reasons.append("자사 기존 수행")
        else:
            names = ", ".join(f.get("name") or "" for f in firms[:2])
            notes.append(f"기존 수행 {names} ({(incumbent.get('signed_date') or '')[:4]})")

    th = (profile.get("scoring") or {}).get("thresholds") or {}
    go_th = th.get("go") or {}
    no_go_max = (th.get("no_go") or {}).get("max_score", 40)
    if stops or score <= no_go_max:
        verdict = NO_GO
    elif (
        score >= go_th.get("min_score", 70)
        and evidence >= go_th.get("min_evidence_ratio", 0.8)
        and not caps_review
    ):
        verdict = GO
    else:
        verdict = REVIEW
    if evidence < go_th.get("min_evidence_ratio", 0.8):
        caps_review.insert(0, "추가 확인 필요 (근거 충족률 미달)")
    return {
        "score": score,
        "evidence": round(evidence, 2),
        "verdict": verdict,
        "gates": gates,
        "reasons": stops + caps_review + reasons,
        "notes": notes,
    }


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "¦")


def slack_text_policy(
    rows: list[tuple[dict[str, Any], dict[str, Any]]],
    today: Any,
    site_url: str,
    total: int,
    profile: dict[str, Any],
    summaries: dict[str, dict[str, Any]] | None = None,
) -> str:
    from .site import detail_href

    summaries = summaries or {}
    counts = {v: sum(1 for _, s in rows if s["verdict"] == v) for v in (GO, REVIEW)}
    lines = [
        f"*Go/No-Go 검토 우선순위 {len(rows)}건* ({today.isoformat()}, 새 공고 {total}건 중 · "
        f"GO {counts[GO]} · REVIEW {counts[REVIEW]})"
    ]
    for n, s in rows:
        url = site_url + detail_href(n) if n.get("bid_no") else n.get("g2b_url") or site_url
        budget = f"{n['budget_eok']:.1f}억" if n.get("budget_eok") is not None else "예산 미상"
        meta = " · ".join(x for x in (n.get("org"), budget, f"마감 {n.get('close_at') or '?'}") if x)
        lines.append(
            f"• *{s['verdict']} {s['score']}점* (근거 {round(s['evidence'] * 100)}%) "
            f"<{url}|{_esc(n.get('title') or '')}>"
        )
        lines.append(f"    {_esc(meta)}")
        if s["reasons"]:
            lines.append(f"    사유: {_esc(' / '.join(s['reasons'][:4]))}")
        if s["gates"]:
            lines.append("    게이트: " + _esc(" · ".join(f"{g} {st}" for g, st, _ in s["gates"])))
        if s["notes"]:
            lines.append(f"    참고: {_esc(' / '.join(s['notes'][:3]))}")
        overview = ((summaries.get(n.get("bid_no") or "") or {}).get("summary") or {}).get("overview")
        if overview:
            lines.append(f"    요약: {_esc(overview if len(overview) <= 140 else overview[:139] + '…')}")
    warning = credit_warning(profile, today)
    if warning:
        lines.insert(1, f"_주의: {_esc(warning)}_")
    obs = (profile.get("track_record") or {}).get("observations") or []
    if obs:
        lines.append("_참고 관측: " + _esc(" / ".join(obs[:3])) + "_")
    lines.append("_검토 우선순위이며 수주 확률이 아닙니다._")
    return "\n".join(lines)
