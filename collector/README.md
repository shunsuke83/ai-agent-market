# Collector — 나라장터 AI 공고 자동수집

정적 사이트(`awards.html` / `band.html` / …)의 데이터 구조를 정규화하고, 조달청 나라장터 Open API로 주기 수집하는 도구입니다.

## 데이터 모델 (요약)

| 엔티티 | 주요 필드 | 사이트 매핑 |
|--------|-----------|-------------|
| **Notice** | `bid_no`, `bid_ord`, `notice_date`, `org`, `title`, `scope`, `fields[]`, `nature`, `budget_eok`, `open_date`, `status`, `winner`, `first_rank`, … | `band.html` 공고별 결과, 주간/월간 리포트 |
| **Award** | `open_date`, `budget_eok`, `award_amount_eok`, `winner`, `bid_count`, `second` | `awards.html` 대형 낙찰 |
| **Competitor** | `name`, `type`, `bids`, `wins`, `award_amount_eok`, … | `competitors.html` (프로필은 편집, 실적은 집계) |
| **Prespec** | `prespec_no`, `org`, `title`, `asign_budget_eok`, `registered_at`, `opinion_close_at`, `bid_nos[]`, `spec_files` | `prespecs.html`, `index.html` 의견 접수 중 사전규격 |
| **Firm** | `bizno`, `corp_name`, `ceo`, `region`, `opened`, `employees`, `fetched_at` | `competitors.html` 업체 프로필·맞대결 업체명 |
| **OrderPlan** | `plan_no`, `title`, `org`, `order_ym`, `amount_eok`, `contract_method`, `bid_nos[]` | `plans.html` 발주 예정 |
| **Contract** | `contract_no`, `title`, `org`, `signed_date`, `end_date`, `amount_eok`, `firms[]`(지분·사업자번호), `bid_no` | `plans.html` 재발주 후보·업체 실적, 사업 상세 계약 블록, Go/No-Go 기존 수행사 |
| **RfpSummary** | `bid_no`, `status`, `source`, `files[]`, `fields`(기간·제한), `summary`(개요·과업·기술·요건·평가·유의) | 사업 상세 "제안요청서 요약", Go/No-Go 게이트·한 줄 요약 |

Notice의 평가·참가 조건 필드: `award_method`, `tech_rate`/`price_rate`, `joint_method`, `industry_limit`·`participation_limit`·`record_limit`, `rebid`, `prev_bid_no`, `prespec_no`, `plan_no`, `notice_files[]`.

`scope` (범위): `생성형·Agent` | `AI SW 확대` — 사업명 키워드 (`config/keywords.yaml`, `deliverables.html` 분류 기준).

`fields` (분야): `생성형·LLM`, `AI 에이전트`, `AI 보안`, `AI 인프라`, `데이터·예측`, … 또는 `AI 일반`.

예산 단위는 **억 원** (`budget_eok`). 8~30억 구간이 `band.html` 타깃.

### 결과·금액 필드 규칙

- `winner`: 낙찰 확정 업체만. 개찰 1순위(협상·적격심사 전)는 `first_rank`에 두고 낙찰 집계에 넣지 않습니다.
- `award_amount_eok`: 나라장터가 공개한 낙찰금액만. 없으면 비워 두고 화면에 `미확인`으로 표시하며, 예산으로 대신 채우지 않습니다.
- `win_rate_pct`: 나라장터 낙찰률(예정가격 대비) 원값. `award_to_budget_pct`: 낙찰금액 ÷ 예산 계산값. 둘을 섞지 않습니다.

### 시드와 수집 상태

- `data/seed/editorial-2026-10-28.json`: 자동 렌더 이전 수작업 HTML에서 추출한 **동결 시드**. 읽기 전용이며 렌더된 HTML에서 다시 만들지 않습니다(지난주 화면이 이번 주 입력이 되는 순환 방지). 실 수집값이 항상 우선하고, 집계 하한으로 쓰지 않습니다.
- `data/run_status.json`: 단계별(`collect`·`prespecs`·`plans`·`contracts`·`awards`·`bidders`·`firms`) 마지막 시도·결과·마지막 성공 시각과 이를 기록한 Actions `run_id`. 마지막 성공 시각은 성공했을 때만 갱신됩니다. `index.html` 스탬프는 렌더 날짜가 아니라 공고 수집의 마지막 성공일을 `데이터 기준`으로 표시하고, 최근 수집이 실패했으면 "기존 데이터 표시 중"을 덧붙입니다.

## Open API

| 서비스 | 포털 | 용도 |
|--------|------|------|
| 입찰공고정보서비스 | [data.go.kr/15129394](https://www.data.go.kr/data/15129394/openapi.do) | 공고 검색 (`*PPSSrch`) |
| 낙찰정보서비스 | [data.go.kr/15129397](https://www.data.go.kr/data/15129397/openapi.do) | 개찰·낙찰 (`winner`/`bid_count`/`award_amount_eok`), 투찰업체 순위(OpengCompt) |
| 사전규격정보서비스 | [data.go.kr/15129437](https://www.data.go.kr/data/15129437/openapi.do) | AI 사전규격 (`data/prespecs.json`) |
| 사용자정보서비스 | [data.go.kr/15129466](https://www.data.go.kr/data/15129466/openapi.do) | 조달업체 기본정보 (`data/firms.json`) |
| 발주계획현황서비스 | [data.go.kr/15129462](https://www.data.go.kr/data/15129462/openapi.do) | AI 발주계획 (`data/order_plans.json`) |
| 계약정보서비스 | [data.go.kr/15129427](https://www.data.go.kr/data/15129427/openapi.do) | AI 용역 계약 (`data/contracts.json`) |

서비스마다 data.go.kr 활용신청이 따로 필요합니다. 키 하나로 모두 호출하지만, 활용신청하지 않은 서비스는 실패합니다(공고 수집 외에는 실패해도 경고만 남김). 공고·사전규격 첨부 파일(`g2b.go.kr .../downloadFile.do`)은 인증 없이 받아집니다.

| 환경변수 | 용도 |
|----------|------|
| `DATA_GO_KR_SERVICE_KEY` (또는 `SERVICE_KEY`) | data.go.kr 인증키 |
| `SLACK_WEBHOOK_URL` | 알림·Go/No-Go Slack 전송 |
| `GEMINI_API_KEY`, `GEMINI_MODEL`(선택) | 제안요청서 요약 |
| `COMPANY_PROFILE` | Go/No-Go 회사 프로필 YAML (없으면 `config/profile.local.yaml`) |

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

# 4) 사전규격 (별도 활용신청 필요) → data/prespecs.json
python -m g2b.collect collect-prespecs --days 14

# 5) 조달업체 기본정보 (별도 활용신청 필요) → data/firms.json, 30일 지난 업체만 다시 조회
python -m g2b.collect enrich-firms

# 5-1) 발주계획 (별도 활용신청 15129462) → data/order_plans.json, 이번 달부터 12개월
python -m g2b.collect collect-plans
# 5-2) 용역 계약 (별도 활용신청 15129427) → data/contracts.json, 파일이 없으면 약 18개월 백필
python -m g2b.collect collect-contracts --days 14

# 6) HTML 렌더 (band + awards + competitors + reports + prespecs + pricing + plans + details + index)
python -m g2b.collect render all
# 일부만: python -m g2b.collect render competitors prespecs

# 7) 알림: feeds/*.xml(RSS) + feeds/deadlines.ics + alerts.html, SLACK_WEBHOOK_URL이 있으면 Slack 전송
python -m g2b.collect alerts
# Slack 없이 파일만: --no-slack / 보낼 내용만 확인: --dry-run

# 8) Go/No-Go: COMPANY_PROFILE(YAML)로 최근 공고 점수 → Slack에만 전송 (파일·로그에는 건수만)
python -m g2b.collect gonogo --days 1 --dry-run

# 9) 제안요청서 요약: 열린 공고 첨부(HWPX·HWP·PDF) → data/rfp_summaries.json (GEMINI_API_KEY)
python -m g2b.collect summarize-rfp --limit 8
# Gemini 없이 규칙 항목만: --no-llm
```

### 제안요청서 요약 (`g2b/rfp.py`)

마감 전 공고(최신 차수) 중 아직 요약이 없는 건을 실행당 `--limit`건 처리합니다. 순서는 공개 분류만 씁니다: 생성형·Agent 범위 → 예산 3~30억 → 공고일 최신. 압축 첨부는 안의 제안요청서부터 읽습니다. 공고 첨부가 없으면 연결된 사전규격 규격서를 씁니다. 서식·서약서 같은 파일은 건너뛰고 제안요청서·과업지시서·규격서·공고문 순으로 최대 3개, 합계 6만 자까지 읽습니다.

- 규칙 추출: 사업 기간, 중소기업·대기업 참여 제한, 하도급 제한, 제안 발표 언급
- Gemini(`gemini-3.5-flash`, 안 되면 `gemini-flash-lite-latest`, `GEMINI_MODEL`로 변경. `gemini-flash-latest`(3.8)는 무료 등급에서 응답이 없고 2.5는 신규 제공 종료): 개요, 주요 과업, 요구 기술, 자격·요건, 평가, 유의 사항
- 무료 등급 입력은 학습에 쓰일 수 있어 공개 첨부 텍스트만 보냅니다. 회사 프로필은 보내지 않습니다.
- 결과는 공개입니다. 사업 상세 페이지의 "제안요청서 요약"과 Go/No-Go Slack 메시지의 한 줄 요약에 쓰입니다.
- 첨부 URL이 바뀌면 다시 요약합니다. 응답 지연(150초)·402·5xx면 다음 모델로 넘어가고, 그래도 실패하면 다음 실행에서 3번까지 재시도합니다. 429(할당량)면 그 실행은 멈춥니다. 키가 없으면 규칙 항목만 저장했다가 키가 생기면 요약합니다.
- 같은 문서가 hwpx·pdf로 함께 올라오면 한 번만 읽습니다. 배포용·암호 HWP는 읽지 못합니다.

### Go/No-Go (`g2b/gonogo.py`)

회사 프로필은 공개 저장소에 두지 않습니다. 실제 값은 repo secret `COMPANY_PROFILE`에 YAML 그대로 넣고, 로컬에서는 `config/profile.local.yaml`(gitignore)을 읽습니다. 프로필 형식은 두 가지입니다.

- **단순형** (`config/profile.example.yaml`): 성격 가중치·키워드·예산 범위·경쟁사로 100점 만점
- **정책형** (`company`·`capabilities`·`track_record`·`policy`·`hard_gates`·`scoring` 키): 하드 게이트 → 회피 정책 → 가중치 점수·근거 충족률. 현재 등록된 프로필이 이 형식입니다

secret 갱신(PowerShell): `cmd /c "gh secret set COMPANY_PROFILE < collector\config\profile.local.yaml"` (PowerShell 파이프는 한글이 깨질 수 있음)

단순형 배점:

| 항목 | 배점 | 기준 |
|------|------|------|
| 적합도 | 35 | 사업 성격 가중치, 선호 키워드, 관심 기관. 범위가 프로필 밖이면 절반 |
| 예산 | 15 | sweet 범위 만점, min~max 일부 |
| 경쟁 | 20 | 비슷한 과거 사업 투찰 수 중앙값(`pricing.ContextIndex`), 경쟁사가 단골이면 감점 |
| 평가 | 10 | 기술 평가 비율 80% 이상 만점 |
| 일정 | 10 | 마감까지 남은 날 vs `min_days_to_prepare` |
| 신호 | 10 | 재공고(유찰 이력)·사전규격·발주계획 연계 가점, 같은 기관 비슷한 계약의 기존 수행사 감점(우리 회사면 가점) |

프로필에 `company`·`scoring` 키가 있으면 정책형 판정(`g2b/gonogo_policy.py`)을 씁니다.

- 하드 게이트를 점수보다 먼저 봅니다. 지역·자격·실적 금액·인증은 공고 제한 표시와 제안요청서 요약에서 신호를 찾습니다. 미충족이면 NO-GO, 프로필 값이 비어 있으면(null) 미확인으로 REVIEW입니다.
  - 자격: 요약의 요건 줄마다 업종코드(코드 없이 정보통신공사업·학술연구용역·행사대행업 이름만 있어도)를 `company.g2b_industry_codes`와 대조. 한 줄 안의 "또는"은 하나, "및"은 전부, 줄끼리는 모두 충족해야 통과. 면허는 있고 나라장터 업종만 미등록인 코드(`g2b_registrable_codes`)는 미충족 대신 미확인(등록 필요). 직접생산은 `direct_production_cert: {세부품명: 유효기간 종료일}`로 품목별 판정하고, `g2b_items_without_direct_production` 품목을 요구하면 미충족
  - 실적 금액: 요약의 "실적 N억" 요건을 `largest_g2b_contract_eok`·`non_g2b_amounts_eok` 중 큰 값과 비교
  - 일정: 마감까지 영업일 ≥ `min_business_days_to_deadline`. 동시 수행(`max_concurrent_builds`)은 현재 수행 건수가 없어 점수 항목에만 씁니다
- `company.credit_rating.valid_until`이 지났으면 Slack 머리에 갱신 경고를 붙입니다.
- `policy.avoid` 규칙(성격·제목 키워드)은 NO-GO입니다. 기존 고객 기관, 자사 제품명, 또는 성격으로만 걸렸고 제목에 고도화·구축이 있으면 REVIEW로 완화합니다. 사이트 제외 규칙(감리·PMO·교육·장비 구매)도 NO-GO입니다.
- 점수는 `scoring.weights`로 계산하되 근거가 없는 항목은 빼고 비율로 환산하며, 뺀 비중만큼 근거 충족률이 내려갑니다. GO는 점수·충족률 기준을 넘고 미확인 게이트가 없으며 예산 구간 기본값이 GO인 경우에만 나옵니다.
- Slack에는 판정 사유, 게이트 결과, 점수와 근거 충족률, 참고 관측을 보내고 수주 확률은 표기하지 않습니다.

추천된 공고에 요약이 없으면 Go/No-Go 단계에서 최대 5건을 바로 요약해 Slack 한 줄 요약과 게이트 판정에 씁니다. 이 요약은 `data/`에 저장하지 않습니다(어떤 공고를 먼저 요약했는지로 프로필이 드러나지 않게).

두 형식 모두 프로필의 `pipeline: [{bid_no: ...}]`에 있는 공고(이미 제안서를 쓰는 중인 입찰)는 판정에서 뺍니다.

단순형에서는 회피 키워드, 가중치 0인 성격, 예산이 기준의 2배 넘게 벗어남, 마감 지남이 바로 No-Go입니다. `go_score`(70) 이상 Go, `review_score`(50) 이상 검토이고, `min_score` 이상 상위 `top_n`건만 보냅니다.

## GitHub Actions

`.github/workflows/collect.yml` — repo secret `DATA_GO_KR_SERVICE_KEY`가 있어야 돕니다.

| 실행 | 언제 | 하는 일 |
|------|------|---------|
| 일일 | 매일 13:17 KST (월요일 제외) | 최근 3일 공고·사전규격 수집 → 재분류 → 렌더 → 커밋 |
| 주간 | 월요일(KST) 예약 실행, 그리고 모든 수동 실행(Run workflow) | 14일 수집에 더해 건별 낙찰 보강·투찰업체 보강·업체 기본정보까지 |

- 예약 실행은 GitHub 사정으로 몇 시간 늦게 시작할 수 있습니다. 새벽(KST)에 apis.data.go.kr 연결 타임아웃으로 실패한 적이 있어 낮 시간대·정각이 아닌 분에 둡니다.
- 일일/주간 판정은 실행되는 시점의 KST 요일로 합니다. 예약 실행을 Re-run 해도 월요일이면 주간 모드로 돕니다.
단계 순서: 공고 → 사전규격 → 발주계획 → 계약 → 재분류 → (주간) 낙찰·투찰업체·업체정보 보강 → 제안요청서 요약 → 렌더 → 알림 → Go/No-Go → 커밋.

- 발주계획·계약 수집은 매일 돕니다. 각각 별도 활용신청이 필요하고 실패해도 경고만 남깁니다.
- 제안요청서 요약은 실행당 8건 돕니다(secret `GEMINI_API_KEY`). 실패해도 경고만 남깁니다.
- 알림은 secret `SLACK_WEBHOOK_URL`이 있으면 Slack으로 보내고, 실패해도 커밋은 막지 않습니다(못 보낸 건은 다음 실행에 다시 보냄).
- Go/No-Go는 secret `COMPANY_PROFILE`이 없으면 건너뜁니다. 일일은 최근 1일, 주간은 3일 공고를 보고, 로그에는 건수만 찍습니다.
- API 단계가 실패해도 기존 데이터로 렌더·커밋은 계속하고, `data/run_status.json`에 결과를 남깁니다. 공고 수집(`collect`)이나 투찰업체 보강(`bidders`)이 실패하면 마지막 단계에서 실행을 실패로 표시합니다. 원인은 그 단계가 아니라 앞 단계 로그에 있습니다.

공고 일정·금액 필드: `close_at`(입찰 마감)과 `open_at`/`open_date`(개찰)는 서로 채우지 않습니다. `budget_eok`는 배정예산 → 예산 → 추정가격 → 기초금액 순으로 고른 값이고, 어느 필드인지 `budget_kind`에 남기며 원래 값은 `asign_budget_eok`·`presmpt_eok`·`base_amount_eok`에 따로 둡니다. 기존 공고는 다시 수집될 때 채워집니다.

## 렌더 범위

- `index.html` 오늘의 사업 기회(마감 임박·새 공고·의견 접수 중 사전규격·최근 개찰) + 분석 링크, `데이터 기준` 스탬프 (`data/run_status.json`)
- `band.html` 공고별 결과 테이블 (+ 상단 공고 건수·예산 합계 스탯)
- `awards.html` 30억+ 낙찰 · 수주 상위 · 연도별 · 개찰 확인 필요
- `prespecs.html` AI 사전규격 목록 (`data/prespecs.json`), 본공고가 나온 건은 사업 상세로 연결
- `pricing.html` 투찰·경쟁 분석 (`g2b/pricing.py`)
  - 낙찰 투찰률: 낙찰자의 예정가격 대비 투찰률. OpengCompt가 투찰률 대신 협상계약 가격평가 점수(`bidPrceEvlVal`, 약 8~20)를 주는 경우가 있어 50~110%만 씁니다
  - 경쟁 강도: 투찰 업체 수 중앙값·상위 25%·단독 응찰 비율. 수백 곳이 몰리는 공고가 있어 평균은 쓰지 않고, 수의계약은 뺍니다
  - 표본이 5건 미만인 구분은 수치 대신 `표본 부족`
  - 경쟁이 약했던 사업: 최근 1년 유찰·단독 응찰 (수의계약·장비·감리·교육행사 제외, 재공고 차수 병합)
- 사업 상세 공고 정보에 낙찰 방법, 기술:가격 평가 비율, 공동수급 방식, 업종·참가 자격·실적 제한, 이전 공고(재공고), 공고 첨부 파일 링크를 붙입니다. 공고 API 필드라 이 기능 이후 다시 수집된 공고부터 채워집니다
- `plans.html` 발주 예정·재발주 후보 (`g2b/plans.py`)
  - 발주계획: 사업명 키워드로 찾고 공고와 같은 분류·제외 규칙을 씁니다. 발주 예정월이 이번 달 이후이고 연결된 공고(`bidNtceNoList`)가 없는 것만 보여 주며, 금액 0·1원은 비공개로 봅니다
  - 계약: 용역 계약명 키워드 검색은 조회 기간이 1개월을 넘으면 0건이라 월별로 나눠 부릅니다. AI 계약 대부분이 소액 수의계약이라 1억 원 이상만 저장합니다
  - 종료일: 총완수일 → 계약기간 원문의 날짜(`2027/07/30`, `20251111~20261110`) → `계약 후 N일`·`N개월`을 체결일에 더한 값. 변경계약은 계약참조번호 끝 2자리(변경 차수)를 떼고 최신 등록 건으로 덮습니다
  - 업체 실적: 최근 1년 계약금액을 공동수급 지분율로 나눔. 공고번호가 맞는 사업 상세 페이지에는 계약 블록(체결일·기간·금액·지분)을 붙입니다
- `alerts.html` + `feeds/` 알림 (`g2b/alerts.py`, 규칙은 `config/alerts.yaml`)
  - 규칙 조건(종류·범위·분야·성격·키워드·기관·예산)은 모두 AND. 장비·감리·교육행사와 취소공고는 뺍니다
  - RSS는 규칙별 최근 50건, 캘린더는 60일 이내 입찰 마감·사전규격 의견 마감
  - Slack은 공고·사전규격 등록일이 최근 7일 안이고 마감이 지나지 않은 건만, 규칙당 15건까지 보냅니다. 보낸 건은 `data/alerts_state.json`에 남겨 다시 보내지 않습니다
- `bids/<공고번호>-<차수>.html` AI 공고별 사업 상세 (공개 데이터만). 같은 기관 개찰 이력이 3건 이상이면 그 기관, 아니면 같은 사업 성격·예산대 기준으로 "비슷한 과거 사업의 경쟁"(투찰 수, 낙찰 투찰률, 자주 투찰한 업체)을 붙입니다
- `competitors.html` 한눈에 보기 KPI + 상세 실적 수치 (`competitors.yaml` 별칭 매칭)
  - 낙찰·금액: 동결 시드 ∪ notices 중 낙찰 확정 건, 공개 낙찰금액만 합산. 정정되면 줄어들 수 있음
  - 투찰: OpengCompt `bidders[]` 실측 (`max(live_bids, 낙찰)`)
  - 사업자번호가 있는 투찰 기록은 사업자번호로만 매칭하고, 업체명·지역은 `data/firms.json` 조달업체 기본정보를 씁니다
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
- Go/No-Go의 공동수급 역할(주관사 여부)·동시 수행 여력 게이트: 공고 데이터와 현재 수행 현황이 없어 판정하지 않음
- 지역 제한: 공고 API 필드가 아니라 제안요청서 요약의 "OO 소재" 문구로만 판단하므로 요약이 없는 공고는 보지 못함
- 제안요청서 요약 백로그: 열린 공고 약 240건을 실행당 8건씩 처리 중 (Gemini 무료 등급 한도)
