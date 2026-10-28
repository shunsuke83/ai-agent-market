# BidPublicInfoService (입찰공고) — 참고 요약

출처: 조달청 OpenAPI 참고자료 나라장터 입찰공고정보서비스 1.2 (docx, 사용자 제공)

- Base: `https://apis.data.go.kr/1230000/ad/BidPublicInfoService`
- Auth: query `serviceKey` (일반 인증키)
- Format: `type=json|xml`
- AI 수집에 쓰는 검색 오퍼레이션:
  - `getBidPblancListInfoServcPPSSrch` (용역)
  - `getBidPblancListInfoThngPPSSrch` (물품)
- 주요 요청: `inqryDiv=1`, `inqryBgnDt`/`inqryEndDt` (`YYYYMMDDHHMM`, 보통 1개월 이내), `bidNtceNm`, `pageNo`, `numOfRows`
- 주요 응답: `bidNtceNo`, `bidNtceOrd`, `bidNtceNm`, `bidNtceDt`, `opengDt`, `dminsttNm`, `asignBdgtAmt`(원), `presmptPrce`(원), `cntrctCnclsMthdNm`

인증키는 GitHub Actions secret `DATA_GO_KR_SERVICE_KEY`에만 보관. 레포·문서에 커밋하지 말 것.
