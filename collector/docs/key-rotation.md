# data.go.kr 인증키 로테이션

채팅·로그·이슈에 `DATA_GO_KR_SERVICE_KEY`가 노출됐거나 의심되면 **즉시 재발급**하세요.
에이전트/CI는 포털에서 키를 재발급할 수 없습니다 — 소유자 작업입니다.

## 체크리스트

1. [ ] https://www.data.go.kr 로그인 → 마이페이지 → 오픈API → **인증키 발급현황** → **재발급**
2. [ ] 새 **일반 인증키(Decoding)** 복사 (채팅에 붙여 넣지 말 것)
3. [ ] GitHub → Settings → Secrets and variables → Actions  
       → `DATA_GO_KR_SERVICE_KEY` **Update** (이름 유지, 값만 교체)  
       https://github.com/shunsuke83/ai-agent-market/settings/secrets/actions
4. [ ] Actions → **Collect G2B AI notices** → Run workflow (스모크)
5. [ ] 성공하면 예전 키는 포털에서 폐기된 상태로 두면 됨

상세 발급 절차: 에이전트 스토어 `docs/data-go-kr-api-key.md` · `docs/collect-secret-setup.md`

## 로컬

```bash
export DATA_GO_KR_SERVICE_KEY='(새 키 — 셸 히스토리에 남지 않게 주의)'
cd collector && python -m g2b.collect classify "생성형 AI 플랫폼 구축"
```

## 코드 측 가드

- HTTP 예외 메시지에서 `serviceKey=` 값을 `***`로 마스킹 (`g2b.client.redact_secrets`)
- 레포·문서에 키를 커밋하지 말 것
