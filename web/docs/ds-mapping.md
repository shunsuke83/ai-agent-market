# GenON Admin DS — 화면 ↔ 템플릿 매핑

쇼케이스: https://genonai.github.io/admin-design-system  
패키지: `@genonai/admin-design-system` (사내 비공개)

## 접근

| 항목 | 상태 |
|------|------|
| 공개 npm (`registry.npmjs.org`) | 404 — 패키지 비공개 |
| GitHub Packages (`npm.pkg.github.com/@genonai`) | `read:packages` 스코프 필요 |
| 로컬 개발 | `web/vendor/genonai-admin-design-system` (`file:` 의존)로 동일 import 경로 유지 |

레지스트리 토큰이 생기면 `.npmrc.example`을 `.npmrc`로 복사하고 `NODE_AUTH_TOKEN`을 넣은 뒤:

```bash
npm install @genonai/admin-design-system@latest --save-exact
# package.json의 file: vendor 의존을 레지스트리 버전으로 교체
```

핀 버전은 설치 직후 `package-lock.json`에 고정한다.

## 화면 매핑

| 앱 화면 | 라우트 | DS 템플릿 / 컴포넌트 |
|---------|--------|---------------------|
| 셸 | 전체 | [app-layout](https://genonai.github.io/admin-design-system?item=app-layout) · `AppSidebar` / `AppTopbar` |
| 홈 | `/` | [dashboard-page](https://genonai.github.io/admin-design-system?item=dashboard-page) · `DashboardPageLayout` · `StatCard` / `MetricCard` |
| band·수주·사전규격 등 목록 | `/band` `/awards` … | [list-page](https://genonai.github.io/admin-design-system?item=list-page) · `ListPageLayout` · `ListControl` · `DataTable` · `Badge` |
| 공고 상세 | `/bids/:id` | [detail-tabs-page](https://genonai.github.io/admin-design-system?item=detail-tabs-page) · `DetailPageLayout` · `DescriptionList` · `Alert`(적합도) |
| 적합도 | 목록·상세 | `Badge` / `Tag` — GO→참여, REVIEW→검토, NO-GO→보류 |

## 바이브 규칙

- 컴포넌트 재구현 금지 — `@genonai/admin-design-system`에서 import
- 색·간격·타이포는 토큰만 (`--color-action-primary-default` = `#7540ee` 등)
- 가이드: [guide-vibe-coding](https://genonai.github.io/admin-design-system?item=guide-vibe-coding) · [guide-review-method](https://genonai.github.io/admin-design-system?item=guide-review-method)

## 모드

`VITE_APP_MODE=public|internal` — 한 코드베이스. 내부만 Access 전제 카피·배지.
