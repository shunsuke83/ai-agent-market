# 웹 (Vite + React SPA + Cloudflare Pages + D1)

공개 사이트와 내부 직원용 앱을 **하나의 React SPA**로 빌드합니다. 모드(`public` / `internal`)에 따라 데이터 소스만 달라집니다.

## 구성

| 항목 | 설명 |
|------|------|
| `index.html`, `src/` | React SPA (Vite, React Router) |
| `vendor/genonai-admin-design-system/` | 로컬 DS 패키지 (아래 참고) |
| `public/` | 정적 자산만 (`_redirects`, `_routes.json`) — 빌드 시 `dist/`로 복사 |
| `functions/api/` | Pages Functions: D1 조회 API (내부 모드에서 사용) |
| `migrations/` | D1 스키마 |
| `dist/` | 빌드 산출물 (`wrangler.toml`의 `pages_build_output_dir`) |
| 수집 | repo root에서 `python -m g2b.collect sync-d1` |

## 디자인 시스템 (`@genonai/admin-design-system`)

공개 npm에는 `@genonai/admin-design-system`이 없습니다(비공개 GitHub Packages).
그래서 같은 이름의 **로컬 대체 패키지**를 `vendor/genonai-admin-design-system/` 에 두고
`"@genonai/admin-design-system": "file:./vendor/genonai-admin-design-system"` 로 의존합니다.

- 토큰·스타일: `vendor/.../src/styles.css` (`--color-action-primary-default: #7540ee` 등, Pretendard 폰트)
- 컴포넌트: `AppSidebar`, `AppTopbar`, `DashboardPageLayout`, `ListPageLayout`, `DetailPageLayout`, `PageHeader`,
  `StatCard`, `MetricCard`, `DataTable`, `Badge`, `Tag`, `Alert`, `DescriptionList`, `ListControl`, `EmptyState`,
  `Spinner`, `Button`, `Input`, `Text` (+ 보조: `Card`, `AppShellFrame`)
- 실제 비공개 패키지를 쓰려면 `.npmrc.example`을 `.npmrc`로 복사하고 `NODE_AUTH_TOKEN`을 설정한 뒤,
  `package.json`의 의존성을 레지스트리 버전으로 교체하세요.

## 모드

| 모드 | env | 데이터 | 비고 |
|------|-----|--------|------|
| `public` | `.env.public` (`VITE_APP_MODE=public`) | 정적 JSON: `/data/spa/summary.json`, `/data/spa/notices.json`, `/data/spa/notices/<id>.json`, `/data/prespecs.json` 등 | `stage-public`이 `dist/data/` 아래에 배치해야 함 |
| `internal` | `.env.internal` (`VITE_APP_MODE=internal`) | `/api/meta`, `/api/notices`, `/api/notices/:id` (D1) | 헤더에 "내부" 배지, Cloudflare Access 뒤 |

`npm run dev`는 `.env.development`(public)를 사용합니다. 내부 모드로 로컬 실행: `npx vite --mode internal`
(API는 `npm run dev:pages`로 띄운 wrangler로 프록시하거나, 빌드 후 `dev:pages` 사용).

## 로컬

```bash
cd web
npm install
npm run dev              # Vite, http://localhost:5173
npm run build:public     # tsc -b && vite build --mode public  → dist/
npm run build:internal   # tsc -b && vite build --mode internal → dist/
npm run preview
```

D1 + Functions까지 로컬로 확인하려면:

```bash
npm run db:migrate:local
npm run build:internal
npm run dev:pages        # wrangler pages dev dist --d1=DB ...  → http://127.0.0.1:8788/
```

## 배포

내부 (Pages `ai-agent-market-internal`):

```bash
cd web
npm run build:internal
npm run deploy:internal   # wrangler pages deploy dist --project-name=ai-agent-market-internal
```

공개 (Pages `ai-agent-market`) — React dist + SPA JSON:

```bash
cd web
npm run build:public
# repo root
PYTHONPATH=collector python -m g2b.collect export-spa
PYTHONPATH=collector python -m g2b.collect stage-public   # merges into web/dist
cd web && npm run deploy:public
```

수집 Actions(`collect.yml`)가 공개·내부 CF Pages와 GitHub Pages(`main/` + `VITE_BASE=/ai-agent-market/`)까지 빌드·배포합니다.
레거시 HTML은 `RENDER_HTML=0`(기본)일 때 비활성입니다. 필요 시 repo variable `RENDER_HTML=1`.

- SPA 라우팅은 `public/_redirects` (`/*  /index.html  200`)로 처리합니다.
- `public/_routes.json`은 `/api/*` 만 Functions로 보냅니다.
- 서브패스 배포(GitHub Pages 등)는 `VITE_BASE=/repo/ npm run build:public`.
- 구 URL(`/band.html`, `/index.html`, `/bids/<id>.html`)은 SPA 안에서 새 경로로 리다이렉트됩니다.

## 현재 배포 (초기 셋업 완료)

| 구분 | URL |
|------|-----|
| 내부 (D1+적합도) | https://ai-agent-market-internal.pages.dev/ |
| 공개 (정적+적합도) | https://ai-agent-market.pages.dev/ |

D1 `ai-agent-market` · 마이그레이션 적용됨 · notices 동기화됨.

GitHub Actions secrets (등록됨):

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_D1_DATABASE_ID`
- `CLOUDFLARE_API_TOKEN` (D1 edit; 공개 Pages deploy는 `Account` → `Cloudflare Pages` → `Edit` 권한도 필요)
- `COMPANY_PROFILE` — D1 sync·공개/내부 적합도 (YAML은 data/에 안 넣음)

적합도는 GenON 솔루션 매칭(S/A) + 구축·제품 여부 기준입니다. 순수 운영 용역·B등급은 참여(GO)가 나오지 않습니다.

### Access (`@genon.ai`만 허용)

1. https://one.dash.cloudflare.com/ 에서 **Zero Trust** 조직 생성(Free 플랜).
2. 완료 후 로컬에서:

```powershell
cd web
python _setup_access.py
```

`ai-agent-market-internal.pages.dev` (+ 프리뷰 `*.…pages.dev`)에 `@genon.ai` 메일만 Allow 정책을 만듭니다.
