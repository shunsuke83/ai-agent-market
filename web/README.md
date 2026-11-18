# 내부 웹 (Cloudflare Pages + D1)

내부 직원용 앱입니다. 공개 사이트와 분리되어 있으며, Access 뒤에서 D1을 조회합니다.

## 구성

| 항목 | 설명 |
|------|------|
| `public/` | 정적 UI (목록·상세) |
| `functions/api/` | D1 조회 API |
| `migrations/` | D1 스키마 |
| 수집 | repo root에서 `python -m g2b.collect sync-d1` |

## 한 번만 할 설정

```bash
cd web
npm install
npx wrangler login
npx wrangler d1 create ai-agent-market
# 출력된 database_id 를 wrangler.toml 에 붙여 넣기
npm run db:migrate:remote
npx wrangler pages project create ai-agent-market-internal
npx wrangler pages project create ai-agent-market   # 공개용
```

GitHub Actions secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` (D1 edit + Pages deploy)
- `CLOUDFLARE_D1_DATABASE_ID`
- `COMPANY_PROFILE` (이미 사용 중 — sync 시 적합도 컬럼)

Cloudflare Zero Trust **Access**로 `ai-agent-market-internal` 프로젝트에 회사 메일만 허용합니다.

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
