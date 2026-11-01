"""One-off probe for 발주계획(15129462) and 계약정보(15129427) endpoints."""

import json
from collections import Counter

from g2b.client import G2BClient, G2BError

c = G2BClient(max_attempts=2)
OP = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
CT = "https://apis.data.go.kr/1230000/ao/CntrctInfoService"
CT_PPS = f"{CT}/getCntrctInfoListServcPPSSrch"


def run(name, url, params, rows=3, show=1):
    print(f"\n=== {name}")
    try:
        data = c._get(url, {**params, "numOfRows": rows})
    except G2BError as e:
        print("ERROR", e.status_code, str(e)[:300])
        return []
    items = c._items(data)
    print("total", c._total(data))
    for it in items[:show]:
        print(json.dumps(it, ensure_ascii=False)[:600])
    return items


run("contract name 1y", CT_PPS, {"inqryDiv": "1", "inqryBgnDate": "20251101", "inqryEndDate": "20261031", "cntrctNm": "인공지능"})
run("contract name 3y", CT_PPS, {"inqryDiv": "1", "inqryBgnDate": "20240101", "inqryEndDate": "20261031", "cntrctNm": "인공지능"})
run("contract name AI 1m", CT_PPS, {"inqryDiv": "1", "inqryBgnDate": "20261001", "inqryEndDate": "20261031", "cntrctNm": "AI"})
for div in ("1", "2", "3", "4", "5"):
    run(f"contract ntceNo div{div} 1m", CT_PPS, {"inqryDiv": div, "ntceNo": "R26BK01729805",
                                                 "inqryBgnDate": "20261001", "inqryEndDate": "20261031"})
run("contract ntceNo no dates", CT_PPS, {"inqryDiv": "1", "ntceNo": "R26BK01729805"})

items = run("contract AI sample 1y", CT_PPS, {"inqryDiv": "1", "inqryBgnDate": "20251101",
                                               "inqryEndDate": "20261031", "cntrctNm": "인공지능"}, rows=100, show=0)
print("\n--- period formats")
for it in items[:60]:
    print(repr(it.get("cntrctPrd")), "| wbgn", it.get("wbgnDate"), "| ttal", it.get("ttalScmpltDate"),
          "| thtm", it.get("thtmScmpltDate"), "|", it.get("lngtrmCtnuDivNm"),
          "| tot", it.get("totCntrctAmt"), "thtm", it.get("thtmCntrctAmt"), "|", it.get("cntrctCnclsMthdNm"))
print("filled ttal", sum(1 for i in items if i.get("ttalScmpltDate")), "/", len(items))
print("methods", Counter(i.get("cntrctCnclsMthdNm") for i in items))

run("plan servc posted 2y", f"{OP}/getOrderPlanSttusListServcPPSSrch",
    {"orderBgnYm": "202601", "orderEndYm": "202712", "inqryBgnDt": "202501010000",
     "inqryEndDt": "202610312359", "bizNm": "인공지능"})
run("plan servc future months", f"{OP}/getOrderPlanSttusListServcPPSSrch",
    {"orderBgnYm": "202611", "orderEndYm": "202712", "inqryBgnDt": "202601010000",
     "inqryEndDt": "202611012359", "bizNm": "AI"})
plans = run("plan servc AI sample", f"{OP}/getOrderPlanSttusListServcPPSSrch",
            {"orderBgnYm": "202611", "orderEndYm": "202712", "inqryBgnDt": "202601010000",
             "inqryEndDt": "202611012359", "bizNm": "인공지능"}, rows=100, show=0)
print("\n--- plans")
for p in plans[:40]:
    print(p.get("orderYear"), p.get("orderMnth"), p.get("sumOrderAmt"), p.get("orderInsttNm"), "|",
          p.get("bizNm"), "|", p.get("cntrctMthdNm"), "| ntce", p.get("bidNtceNoList"))
