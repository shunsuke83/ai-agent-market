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
| 공개 (정적, 무프로필) | https://ai-agent-market.pages.dev/ |

D1 `ai-agent-market` · 마이그레이션 적용됨 · notices 동기화됨.

GitHub Actions secrets (일부 등록됨):

- `CLOUDFLARE_ACCOUNT_ID` — 등록됨
- `CLOUDFLARE_D1_DATABASE_ID` — 등록됨
- `CLOUDFLARE_API_TOKEN` — **아직 필요** (대시보드에서 API Token 발급, D1 edit + Pages deploy)
- `COMPANY_PROFILE` — sync 시 적합도 컬럼

내부 사이트는 Cloudflare Zero Trust **Access**로 회사 메일만 허용하세요.

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

공개 빌드에는 `COMPANY_PROFILE`을 넣지 않습니다.
