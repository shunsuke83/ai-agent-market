# Collector — 나라장터 AI 공고 자동수집

정적 사이트(`awards.html` / `band.html` / …)의 데이터 구조를 정규화하고, 조달청 나라장터 Open API로 주기 수집하는 도구입니다.

## 데이터 모델 (요약)

| 엔티티 | 주요 필드 | 사이트 매핑 |
|--------|-----------|-------------|
| **Notice** | `bid_no`, `bid_ord`, `notice_date`, `org`, `title`, `scope`, `fields[]`, `nature`, `budget_eok`, `open_date`, `status`, `winner`, `first_rank`, … | `band.html` 공고별 결과, 주간/월간 리포트 |
| **Award** | `open_date`, `budget_eok`, `award_amount_eok`, `winner`, `bid_count`, `second` | `awards.html` 대형 낙찰 |
| **Competitor** | `name`, `type`, `bids`, `wins`, `award_amount_eok`, … | `competitors.html` (프로필은 편집, 실적은 집계) |

`scope` (범위): `생성형·Agent` | `AI SW 확대` — 사업명 키워드 (`config/keywords.yaml`, `deliverables.html` 분류 기준).

`fields` (분야): `생성형·LLM`, `AI 에이전트`, `AI 보안`, `AI 인프라`, `데이터·예측`, … 또는 `AI 일반`.

예산 단위는 **억 원** (`budget_eok`). 8~30억 구간이 `band.html` 타깃.

### 결과·금액 필드 규칙

- `winner`: 낙찰 확정 업체만. 개찰 1순위(협상·적격심사 전)는 `first_rank`에 두고 낙찰 집계에 넣지 않습니다.
- `award_amount_eok`: 나라장터가 공개한 낙찰금액만. 없으면 비워 두고 화면에 `미확인`으로 표시하며, 예산으로 대신 채우지 않습니다.
- `win_rate_pct`: 나라장터 낙찰률(예정가격 대비) 원값. `award_to_budget_pct`: 낙찰금액 ÷ 예산 계산값. 둘을 섞지 않습니다.

### 시드와 수집 상태

- `data/seed/editorial-2026-10-28.json`: 자동 렌더 이전 수작업 HTML에서 추출한 **동결 시드**. 읽기 전용이며 렌더된 HTML에서 다시 만들지 않습니다(지난주 화면이 이번 주 입력이 되는 순환 방지). 실 수집값이 항상 우선하고, 집계 하한으로 쓰지 않습니다.
- `data/run_status.json`: 단계별(`collect`·`awards`·`bidders`) 마지막 시도·결과·마지막 성공 시각. `index.html` 스탬프는 렌더 날짜가 아니라 공고 수집의 마지막 성공일을 `데이터 기준`으로 표시하고, 최근 수집이 실패했으면 "기존 데이터 표시 중"을 덧붙입니다.

## Open API

| 서비스 | 포털 | 용도 |
|--------|------|------|
| 입찰공고정보서비스 | [data.go.kr/15129394](https://www.data.go.kr/data/15129394/openapi.do) | 공고 검색 (`*PPSSrch`) |
| 낙찰정보서비스 | [data.go.kr/15129397](https://www.data.go.kr/data/15129397/openapi.do) | 개찰·낙찰 (`winner`/`bid_count`/`award_amount_eok`) |

환경변수: `DATA_GO_KR_SERVICE_KEY` (또는 `SERVICE_KEY`).  
키 재발급: [`docs/key-rotation.md`](docs/key-rotation.md)

## 사용법

```bash
cd collector
python -m pip install -r requirements.txt

# 1) (이관·복구용) 현재 HTML → 구조화 JSON. 동결 시드는 덮어쓰지 않음
python -m g2b.collect bootstrap --out /tmp/extract.json

# 2) 제목 분류 스모크 / notices 재분류
python -m g2b.collect classify "생성형 AI 플랫폼 구축"
python -m g2b.collect reclassify --out ../data/notices.json

# 3) 나라장터 수집 + 낙찰 병합 (키 필요)
export DATA_GO_KR_SERVICE_KEY='발급키'
python -m g2b.collect collect --days 30 --all-budgets --out ../data/notices.json
# 예산·낙찰금액이 원으로 남아 있으면 억으로 보정:
python -m g2b.collect sanitize-budgets

# 기존 파일만 낙찰 / 투찰업체 보강:
# python -m g2b.collect enrich-awards --days 120 --lookup-missing
# python -m g2b.collect enrich-bidders --limit 200

# 4) HTML 렌더 (band + awards + index + competitors)
python -m g2b.collect render all
# 경쟁사 KPI만: python -m g2b.collect render competitors
```

GitHub Actions: `.github/workflows/collect.yml` — secret `DATA_GO_KR_SERVICE_KEY` 가 있을 때 매일 00:30 KST 최근 3일 공고 증분 수집 → 렌더 → 커밋. 월요일 실행과 수동 실행은 14일 수집에 더해 건별 낙찰 보강·투찰업체 보강까지 합니다. 예약 실행은 GitHub 사정으로 늦어질 수 있습니다.

공고 일정·금액 필드: `close_at`(입찰 마감)과 `open_at`/`open_date`(개찰)는 서로 채우지 않습니다. `budget_eok`는 배정예산 → 예산 → 추정가격 → 기초금액 순으로 고른 값이고, 어느 필드인지 `budget_kind`에 남기며 원래 값은 `asign_budget_eok`·`presmpt_eok`·`base_amount_eok`에 따로 둡니다. 기존 공고는 다시 수집될 때 채워집니다.

## 렌더 범위

- `band.html` 공고별 결과 테이블 (+ 상단 공고 건수·예산 합계 스탯)
- `awards.html` 30억+ 낙찰 · 수주 상위 · 연도별 · 개찰 확인 필요
- `index.html` `데이터 기준` 스탬프 (`data/run_status.json`)
- `competitors.html` 한눈에 보기 KPI + 상세 실적 수치 (`competitors.yaml` 별칭 매칭)
  - 낙찰·금액: 동결 시드 ∪ notices 중 낙찰 확정 건, 공개 낙찰금액만 합산. 정정되면 줄어들 수 있음
  - 투찰: OpengCompt `bidders[]` 실측 (`max(live_bids, 낙찰)`)
  - 편집 조사값(2026-10-28)은 별도 열로만 표시하고 합치지 않음
  - `enrich-bidders --include-bootstrap`: 시드 낙찰 공고를 notices에 upsert 후 경쟁사 낙찰 우선 보강
- 이관: `python -m g2b.collect migrate-results` (1순위·계산 비율 분리, 재실행해도 변화 없음)

## 리포트

```bash
python -m g2b.collect render reports   # weekly + monthly + reports/index
```

월간「이번 달 투찰 참여 업체」는 OpengCompt `bidders[]` 집계(빈 업체명 제외).

```bash
# core AI 공고 투찰목록 우선 보강
python -m g2b.collect enrich-bidders --include-bootstrap --core-only --limit 400

# Optional tuning (Actions sets these too)
# G2B_SLEEP=0.5 G2B_CONNECT_TIMEOUT=15 G2B_TIMEOUT=90 G2B_HTTP_RETRIES=8 G2B_429_COOLDOWN=120
```

## 아직 안 하는 것

- 경쟁사 프로필 문단 (편집 콘텐츠)
- 키 재발급 자체는 소유자가 data.go.kr + GitHub secret에서 수행 ([key-rotation.md](docs/key-rotation.md))
