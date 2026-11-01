# AI Agent Market

공공 AI·Agent 사업 시장 리서치 사이트입니다. 나라장터(조달청) Open API로 AI 관련 공고·사전규격·낙찰 결과를 매일 수집하고, 정적 HTML 페이지로 렌더해 GitHub Pages로 공개합니다.

- **사이트:** https://shunsuke83.github.io/ai-agent-market/
- **원본:** [sungkyu-pm/ai-agent-market](https://github.com/sungkyu-pm/ai-agent-market) ([사이트](https://sungkyu-pm.github.io/ai-agent-market/))

이 저장소는 report_ai 프로젝트에서 독립적으로 고도화하기 위해 원본을 복제한 것으로, 이관 시점의 이력을 보존합니다. 원본 콘텐츠의 저작권은 원저자에게 있습니다.

## 사이트 구성

| 페이지 | 내용 | 갱신 |
|--------|------|------|
| [`index.html`](index.html) | 오늘의 사업 기회: 마감 임박·새 공고·의견 접수 중 사전규격·최근 개찰, 분석 페이지 링크 | 자동 |
| [`band.html`](band.html) | 예산 8~30억 AI 사업 공고별 결과 | 자동 |
| [`awards.html`](awards.html) | 30억 이상 낙찰, 수주 상위 업체, 연도별 추이, 개찰 확인 필요 | 자동 |
| [`competitors.html`](competitors.html) | 국내 전문기업 실적(투찰·낙찰·금액)과 업체 프로필 | 실적 자동, 프로필 편집 |
| [`prespecs.html`](prespecs.html) | AI 사업 사전규격과 의견 접수 상태 | 자동 |
| [`bids/`](bids/) | AI 공고별 사업 상세 페이지 | 자동 |
| [`reports/`](reports/) | 주간 브리프·월간 리포트 | 자동 |
| [`deliverables.html`](deliverables.html) | 리포트 체계와 분류 기준 | 편집 |
| [`research/`](research/) | 시장 1차 리서치, Gen Agent 업체 프로필·아키텍처 비교 | 편집 |

"자동" 페이지는 수집기가 `data/`의 JSON으로 다시 만들기 때문에 직접 고치면 다음 실행에서 덮어써집니다. 내용을 바꾸려면 [`collector/g2b/`](collector/g2b/)의 렌더 코드를 고칩니다.

## 저장소 구조

```text
.github/workflows/collect.yml   매일 수집·렌더·커밋하는 Actions 워크플로
collector/                      수집기 (Python 패키지 g2b, 설정, 테스트, API 문서)
  config/keywords.yaml          AI 공고 분류 키워드 (범위·분야·사업 성격)
  config/competitors.yaml       경쟁사 목록과 별칭
  docs/                         Open API 정리, 키 재발급 절차
data/                           수집 데이터(JSON)와 실행 상태, 동결 시드
assets/                         공통 CSS, 표 정렬·필터 스크립트
*.html, bids/, reports/         렌더된 사이트
research/                       편집 리서치 페이지
```

## 데이터 흐름

1. **수집:** 나라장터 Open API(입찰공고·낙찰·사전규격·사용자정보)에서 AI 관련 공고를 가져와 `data/notices.json`, `data/prespecs.json`, `data/firms.json`에 병합합니다.
2. **분류:** `keywords.yaml` 기준으로 범위(생성형·Agent / AI SW 확대)·분야·사업 성격을 붙입니다.
3. **보강:** 낙찰자·투찰 업체 순위·조달업체 기본정보를 붙입니다(주간 실행).
4. **렌더·배포:** 위 사이트 페이지를 다시 만들어 커밋하면 GitHub Pages에 반영됩니다.

단계별 성공 여부는 `data/run_status.json`에 남고, 사이트의 `데이터 기준` 날짜는 렌더 날짜가 아니라 마지막으로 수집에 성공한 날짜입니다. 수집이 실패하면 기존 데이터를 그대로 보여 줍니다.

## 자동 수집 일정

| 실행 | 언제 | 하는 일 |
|------|------|---------|
| 일일 | 매일 13:17 KST (월요일 제외) | 최근 3일 공고·사전규격 수집 → 렌더 → 커밋 |
| 주간 | 월요일 13:17 KST, 그리고 수동 실행(Run workflow) | 14일 수집 + 낙찰·투찰업체·업체 정보 보강 |

예약 실행은 GitHub 사정으로 늦게 시작할 수 있습니다. 실패했을 때 확인하는 방법은 [`collector/README.md`](collector/README.md#github-actions)를 보세요.

## 설정

- repo secret `DATA_GO_KR_SERVICE_KEY`에 data.go.kr 인증키를 넣습니다. 입찰공고·낙찰·사전규격·사용자정보 서비스는 각각 활용신청이 필요합니다.
- 키 재발급 절차: [`collector/docs/key-rotation.md`](collector/docs/key-rotation.md)

## 문서

- [`collector/README.md`](collector/README.md): 데이터 모델, Open API, 명령어 사용법, Actions 동작, 렌더 범위
- [`data/README.md`](data/README.md): 데이터 파일별 생성 명령과 내용
