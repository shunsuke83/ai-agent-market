# Structured market data

| File | Producer | Description |
|------|----------|-------------|
| `notices.json` | `python -m g2b.collect collect` (+ `enrich-awards`, `enrich-bidders`, `reclassify`, `sanitize-budgets`) | AI notices from 나라장터 Open API, with awards and bidder rankings merged in |
| `prespecs.json` | `python -m g2b.collect collect-prespecs` | AI 사전규격 (pre-specifications) |
| `firms.json` | `python -m g2b.collect enrich-firms` | 조달업체 기본정보 by 사업자번호, refreshed after 30 days |
| `order_plans.json` | `python -m g2b.collect collect-plans` | AI 발주계획 for this month onward, replaced each run |
| `contracts.json` | `python -m g2b.collect collect-contracts` | AI 용역 계약 of 1억+ (기간·종료일·공동수급 지분), merged by 계약번호 |
| `alerts_state.json` | `python -m g2b.collect alerts` | Items already sent to Slack, pruned after 180 days |
| `reports.json` | `python -m g2b.collect render reports` | Weekly / monthly report index read by `index.html` |
| `run_status.json` | `python -m g2b.collect mark-run` | Per-stage last attempt, outcome and last success (`collect`, `prespecs`, `plans`, `contracts`, `awards`, `bidders`, `firms`) |
| `seed/editorial-2026-10-28.json` | — (frozen) | Hand-entered values from the original HTML. Read-only; never regenerate from rendered pages |

`python -m g2b.collect bootstrap --out <path>` extracts the current static HTML into JSON for migration or recovery only; it is not stored here.

Schema: see [`collector/README.md`](../collector/README.md).
