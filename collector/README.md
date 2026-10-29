# Collector — 나라장터 AI 공고 자동수집

정적 사이트(`awards.html` / `band.html` / …)의 데이터 구조를 정규화하고, 조달청 나라장터 Open API로 주기 수집하는 도구입니다.

## 데이터 모델 (요약)

| 엔티티 | 주요 필드 | 사이트 매핑 |
|--------|-----------|-------------|
| **Notice** | `bid_no`, `bid_ord`, `notice_date`, `org`, `title`, `scope`, `fields[]`, `nature`, `budget_eok`, `open_date`, `status`, `winner`, … | `band.html` 공고별 결과, 주간/월간 리포트 |
| **Award** | `open_date`, `budget_eok`, `award_amount_eok`, `winner`, `bid_count`, `second` | `awards.html` 대형 낙찰 |
| **Competitor** | `name`, `type`, `bids`, `wins`, `award_amount_eok`, … | `competitors.html` (프로필은 편집, 실적은 집계) |

`scope` (범위): `생성형·Agent` | `AI SW 확대` — 사업명 키워드 (`config/keywords.yaml`, `deliverables.html` 분류 기준).

`fields` (분야): `생성형·LLM`, `AI 에이전트`, `AI 보안`, `AI 인프라`, `데이터·예측`, … 또는 `AI 일반`.

예산 단위는 **억 원** (`budget_eok`). 8~30억 구간이 `band.html` 타깃.

## Open API

| 서비스 | 포털 | 용도 |
|--------|------|------|
| 입찰공고정보서비스 | [data.go.kr/15129394](https://www.data.go.kr/data/15129394/openapi.do) | 공고 검색 (`*PPSSrch`) |
| 낙찰정보서비스 | [data.go.kr/15129397](https://www.data.go.kr/data/15129397/openapi.do) | 개찰·낙찰 (`winner`/`bid_count`/`award_amount_eok`) |

환경변수: `DATA_GO_KR_SERVICE_KEY` (또는 `SERVICE_KEY`).

## 사용법

```bash
cd collector
python -m pip install -r requirements.txt

# 1) 현재 HTML → 구조화 JSON (API 키 불필요)
python -m g2b.collect bootstrap --out ../data/bootstrap.json

# 2) 제목 분류 스모크
python -m g2b.collect classify "생성형 AI 플랫폼 구축"

# 3) 나라장터 수집 + 낙찰 병합 (키 필요)
export DATA_GO_KR_SERVICE_KEY='발급키'
python -m g2b.collect collect --days 30 --all-budgets --out ../data/notices.json
# 기존 파일만 낙찰 보강:
# python -m g2b.collect enrich-awards --days 120 --lookup-missing

# 4) HTML 렌더 (band + awards + index + reports)
python -m g2b.collect render all
# 주·월간만: python -m g2b.collect render reports
```

GitHub Actions: `.github/workflows/collect.yml` — secret `DATA_GO_KR_SERVICE_KEY` 가 있을 때 매주 수집(낙찰 포함) → `band`/`awards`/`index`/`reports` 렌더 → 커밋.

## 렌더 범위

- `band.html` 공고별 결과 테이블 (+ 상단 공고 건수·예산 합계 스탯)
- `awards.html` 30억+ 낙찰 · 수주 상위 · 연도별 · 개찰 확인 필요
- `index.html` `최종 갱신` 스탬프
- `reports/weekly-*` · `monthly-*` · `reports/index.html` · `data/reports.json`
  - 핵심 성격: `시스템 구축·고도화` / `ISP·전략` / `구독·라이선스` / `운영·유지보수`
  - 주간: 직전 완료 ISO 주(월~일). 월간: 당월(진행 중이면 오늘까지)
- 시드: `data/bootstrap.json` ∪ `data/notices.json`

## 아직 안 하는 것

- awards「자주 투찰」·월간「투찰 참여」재집계 (투찰 참가자 BidResult API 미연동)
- 경쟁사 프로필 문단 (편집 콘텐츠)
