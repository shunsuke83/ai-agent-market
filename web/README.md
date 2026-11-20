# 내부 웹 (Cloudflare Pages + D1)

내부 직원용 앱입니다. 공개 사이트와 분리되어 있으며, Access 뒤에서 D1을 조회합니다.

## 구성

| 항목 | 설명 |
|------|------|
| `public/` | 정적 UI (목록·상세) |
| `functions/api/` | D1 조회 API |
| `migrations/` | D1 스키마 |
| 수집 | repo root에서 `python -m g2b.collect sync-d1` |

## 현재 배포 (초기 셋업 완료)

| 구분 | URL |
|------|-----|
| 내부 (D1+적합도) | https://ai-agent-market-internal.pages.dev/ |
| 공개 (정적 HTML+적합도) | https://ai-agent-market.pages.dev/ |

D1 `ai-agent-market` · 마이그레이션 적용됨 · notices 동기화됨.

GitHub Actions secrets (일부 등록됨):

- `CLOUDFLARE_ACCOUNT_ID` — 등록됨
- `CLOUDFLARE_D1_DATABASE_ID` — 등록됨
- `CLOUDFLARE_API_TOKEN` — **아직 필요** (대시보드에서 API Token 발급, D1 edit + Pages deploy)
- `COMPANY_PROFILE` — D1 sync·공개/내부 렌더 적합도 (YAML은 data/에 안 넣음)

공개·내부 모두 적합도를 표시합니다. 내부는 D1 실시간, 공개는 수집 시 렌더한 정적 HTML입니다.
적합도는 GenON 솔루션 매칭(S/A) + 구축·제품 여부 기준입니다. 순수 운영 용역·B등급은 참여(GO)가 나오지 않습니다.

### Access (`@genon.ai`만 허용)

1. https://one.dash.cloudflare.com/ 에서 **Zero Trust** 조직 생성(팀 이름 입력, Free 플랜·결제수단 등록은 필수이나 과금 없음).
2. 완료 후 로컬에서:

```powershell
cd web
python _setup_access.py
```

`ai-agent-market-internal.pages.dev` (+ 프리뷰 `*.…pages.dev`)에 `@genon.ai` 메일만 Allow 정책을 만듭니다. 로그인 방식은 Zero Trust 기본 IdP(원타임 PIN 이메일 등)를 사용합니다.

## 로컬

```bash
cd web
npm run db:migrate:local
# 다른 터미널(collector/)
# set CLOUDFLARE_* 없이 --dry-run 으로 행 확인
python -m g2b.collect sync-d1 --dry-run --limit 5
# 로컬 D1에 넣으려면 wrangler d1 execute 또는 remote sync
npm run dev
```

브라우저: http://127.0.0.1:8788/

## 공개 배포

수집 Actions가 프로필 **없이** `render all` 한 뒤:

```bash
# repo root 산출물을 public-dist 로 모은 다음
npx wrangler pages deploy public-dist --project-name=ai-agent-market
```

공개 사이트에도 적합도를 넣으려면 수집 렌더에 `COMPANY_PROFILE`이 필요합니다(YAML은 data/에 쓰지 않음).
