# Phase 5 — DS 검수 · 리다이렉트 · 레거시 퇴역

검수 기준: [guide-review-method](https://genonai.github.io/admin-design-system?item=guide-review-method)

## 화면 대조

| 화면 | DS 템플릿 | 확인 |
|------|-----------|------|
| 홈 `/` | dashboard-page · StatCard | 스탬프 · GO/REVIEW 건수 · 신규/적합/마감 표 |
| 목록 `/band` 등 | list-page · ListControl · DataTable · Badge | 필터 · 적합도 배지 · 모바일 폭 |
| 상세 `/bids/:id` | detail · DescriptionList · Alert | 적합도 Alert · KV · 404 |
| 셸 | app-layout | 사이드 네비 · 내부 배지(`VITE_APP_MODE=internal`) |

## 공개 / 내부

- 공개: `/data/spa/summary.json` 스탬프와 CF 미러 일치
- 내부: `/api/meta` 스탬프 · Access `@genon.ai`
- 적합도 건수: SPA summary `go_count` / D1 `fit=GO` 근사 일치

## 리다이렉트 (유지 기간)

| 구 URL | 신 경로 |
|--------|---------|
| `band.html` … `deliverables.html` | `/band` … `/deliverables` |
| `bids/<id>.html` | `/bids/<id>` (앱 라우트 + 404→SPA) |
| `index.html` | `/` |

CF: `web/public/_redirects` · GH: `write-spa-redirects` 스텁 + `404.html`=SPA

## 레거시 퇴역

- `RENDER_HTML=0`(기본): Python `render all` HTML 비활성 · 피드/ICS/sitemap/D1/SPA JSON 유지
- `bids/*.html` 커밋 중단(collect 커밋 단계에서 제거)
- 사내 npm 토큰(`NODE_AUTH_TOKEN`) 등록 후 `vendor/` → 레지스트리 `@genonai/admin-design-system` 교체
