from datetime import date

from g2b.plans import (
    build_plans_page,
    contract_block,
    expiring_contracts,
    firm_contract_rows,
    merge_contracts,
    normalize_contract_item,
    normalize_plan_item,
    parse_end,
    parse_firms,
    upcoming_plans,
)

TODAY = date(2026, 11, 1)

PLAN = {
    "orderPlanUntyNo": "R26DD20898663",
    "bizNm": "한국투자공사 내부 인공지능 플랫폼 고도화",
    "orderInsttNm": "한국투자공사",
    "totlmngInsttNm": "한국투자공사",
    "jrsdctnDivNm": "기타공공기관",
    "orderYear": "2026",
    "orderMnth": "12",
    "sumOrderAmt": "250000000",
    "cntrctMthdNm": "제한경쟁",
    "prcrmntMethd": "자체조달",
    "deptNm": "정보시스템실",
    "telNo": "02-2179-1067",
    "nticeDt": "2026-10-16 18:08:09",
    "bidNtceNoList": "",
    "orderPlanDtlUrl": "https://www.g2b.go.kr/link/PRPA015_01/single/?oderPlanNo=R26DD20898663",
    "bsnsDivNm": "일반용역",
    "_biz": "servc",
}

CORP_JOINT = (
    "[1^주계약업체^공동^삼성에스디에스 주식회사^이준희^대한민국^40^삼성에스디에스 주식회사^^1108128774],"
    "[2^도급업체^공동^네이버클라우드 주식회사^김유원^대한민국^60^네이버클라우드 주식회사^^1298631394]"
)

CONTRACT = {
    "untyCntrctNo": "R26TE18814046",
    "cntrctRefNo": "R26TA0228352400",
    "cntrctNm": "범정부 인공지능 공통기반 구현(2차)",
    "cmmnCntrctYn": "Y",
    "lngtrmCtnuDivNm": "신규",
    "cntrctCnclsDate": "2026-10-02",
    "cntrctPrd": "계약 후 180일 이내",
    "totCntrctAmt": "0",
    "thtmCntrctAmt": "6505000000",
    "ntceNo": "R26BK01729805",
    "cntrctInsttNm": "조달청 대구지방조달청",
    "dminsttList": "[1^B554393^한국지능정보사회진흥원^준정부기관^^^]",
    "corpList": CORP_JOINT,
    "cntrctCnclsMthdNm": "제한경쟁",
    "rgstDt": "2026-10-12 10:39:46",
    "ttalScmpltDate": "",
    "cntrctDtlInfoUrl": "https://www.g2b.go.kr/link/FIUA027_01/single/?ctrtNo=R26TA02283524",
}


def test_plan_normalizes_and_strips_bid_ord():
    p = normalize_plan_item({**PLAN, "bidNtceNoList": "R26BK01776532000"})
    assert p["order_ym"] == "2026-12"
    assert p["amount_eok"] == 2.5
    assert p["bid_nos"] == ["R26BK01776532"]
    assert p["scope"]


def test_plan_placeholder_amount_is_blank():
    assert normalize_plan_item({**PLAN, "sumOrderAmt": "1"})["amount_eok"] is None


def test_plan_drops_hardware_goods_and_non_ai():
    gpu = {**PLAN, "_biz": "thng", "bizNm": "AI 연산용 GPU 구매", "prdctClsfcNoNm": "그래픽또는비디오가속카드"}
    assert normalize_plan_item(gpu) is None
    assert normalize_plan_item({**PLAN, "bizNm": "청사 시설 경비 용역"}) is None


def test_upcoming_skips_announced_and_past_months():
    plans = [
        normalize_plan_item(PLAN),
        normalize_plan_item({**PLAN, "orderPlanUntyNo": "B", "bidNtceNoList": "R26BK01776532000"}),
        normalize_plan_item({**PLAN, "orderPlanUntyNo": "C", "orderMnth": "10"}),
    ]
    assert [p["plan_no"] for p in upcoming_plans(plans, TODAY)] == ["R26DD20898663"]


def test_parse_end_formats():
    assert parse_end("2027/07/30", "2026-10-01") == "2027-07-30"
    assert parse_end("2026.11.01 ~ 2027.10.31", None) == "2027-10-31"
    assert parse_end("계약 후 180일 이내", "2026-10-02") == "2027-03-31"
    assert parse_end("착수일로부터 6개월", "2026-08-31") == "2027-02-28"
    assert parse_end("계약 후 180일 이내", None) is None
    assert parse_end("", "2026-10-02") is None


def test_parse_firms_shares():
    firms = parse_firms(CORP_JOINT)
    assert [(f["name"], f["share"], f["bizno"]) for f in firms] == [
        ("삼성에스디에스 주식회사", 40.0, "1108128774"),
        ("네이버클라우드 주식회사", 60.0, "1298631394"),
    ]
    assert firms[0]["role"] == "주계약업체"


def test_contract_normalizes():
    c = normalize_contract_item(CONTRACT)
    assert c["contract_no"] == "R26TA02283524"
    assert c["org"] == "한국지능정보사회진흥원"
    assert c["amount_eok"] == 65.05
    assert c["end_date"] == "2027-03-31"
    assert c["joint"] and len(c["firms"]) == 2


def test_contract_change_supersedes_original():
    old = normalize_contract_item(CONTRACT)
    new = normalize_contract_item({
        **CONTRACT, "cntrctRefNo": "R26TA0228352401", "cntrctPrd": "2027/06/30", "rgstDt": "2026-12-01 09:00:00",
    })
    merged = merge_contracts([old], [new])
    assert len(merged) == 1 and merged[0]["end_date"] == "2027-06-30"
    assert merge_contracts([new], [old])[0]["end_date"] == "2027-06-30"


def test_expiring_window():
    base = normalize_contract_item(CONTRACT)
    rows = [
        {**base, "contract_no": "a", "end_date": "2026-10-15"},
        {**base, "contract_no": "b", "end_date": "2027-03-31"},
        {**base, "contract_no": "c", "end_date": "2027-08-01"},
        {**base, "contract_no": "d", "end_date": "2026-09-01"},
        {**base, "contract_no": "e", "end_date": None},
    ]
    assert [c["contract_no"] for c in expiring_contracts(rows, TODAY)] == ["a", "b"]


def test_firm_rows_split_by_share():
    c = normalize_contract_item(CONTRACT)
    solo = {**c, "contract_no": "x", "amount_eok": 10.0,
            "firms": [{"name": "단독업체", "role": "주계약업체", "share": None, "bizno": "1"}]}
    rows = {r["name"]: r for r in firm_contract_rows([c, solo], TODAY)}
    assert round(rows["네이버클라우드 주식회사"]["amount"], 2) == 39.03
    assert rows["삼성에스디에스 주식회사"]["lead"] == 1
    assert rows["단독업체"]["amount"] == 10.0 and rows["단독업체"]["joint"] == 0


def test_page_and_contract_block_render():
    plans = [normalize_plan_item(PLAN)]
    contracts = [normalize_contract_item(CONTRACT)]
    out = build_plans_page(plans, contracts, {}, TODAY)
    assert "한국투자공사 내부 인공지능 플랫폼 고도화" in out
    assert "범정부 인공지능 공통기반 구현(2차)" in out
    assert "삼성에스디에스 주식회사 40%" in out
    block = contract_block(contracts[0])
    assert "계약 후 180일 이내" in block and "65.0억" in block
    assert contract_block(None) == ""
    assert "공고 전인 AI 발주계획이 없습니다" in build_plans_page([], [], {}, TODAY)
