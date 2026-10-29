# ScsbidInfoService (낙찰정보) — 참고 요약

출처: 공공데이터포털 조달청 나라장터 낙찰정보서비스 + 실측 (2026-10)

- Base: `https://apis.data.go.kr/1230000/as/ScsbidInfoService`
- Auth: query `serviceKey` (입찰공고와 동일 포털 키, 서비스 활용신청 필요)
- Format: `type=json`

## 사용 오퍼레이션

| Op | 용도 |
|----|------|
| `getScsbidListSttusServc` / `…Thng` | 기간별 낙찰 목록 (`inqryDiv=1`) 또는 공고번호 (`inqryDiv=4`) |
| `getOpengResultListInfoServcPPSSrch` | 개찰결과·`opengCorpInfo` (보조) |
| `getOpengResultListInfoOpengCompt` | **투찰업체별 순위** (`inqryDiv=1` + `bidNtceNo`) |

`getBidResultList*` 는 게이트웨이 **400** — OpengCompt 가 동일 데이터.

## 주요 응답 필드 → Notice

| API | Notice |
|-----|--------|
| `bidNtceNo` / `bidNtceOrd` | `bid_no` / `bid_ord` |
| `bidwinnrNm` | `winner` (주식회사/(주) 제거) |
| `prtcptCnum` | `bid_count` |
| `sucsfbidAmt` (원) | `award_amount_eok` |
| `sucsfbidRate` | `win_rate_pct` (없으면 낙찰가/예산으로 추정) |
| `rlOpengDt` | `open_date` (보강) |
| OpengCompt `prcbdrNm` / `opengRank` | `bidders[]`, `second`(2순위) |

## CLI

```bash
# 수집 시 같은 기간 낙찰 병합 (기본)
python -m g2b.collect collect --days 14 --all-budgets

# 기존 notices.json만 낙찰 보강
python -m g2b.collect enrich-awards --days 120 --lookup-missing

# 투찰 순위(업체별) 보강 → awards「자주 투찰」재집계에 사용
python -m g2b.collect enrich-bidders --limit 200
python -m g2b.collect render awards
```
