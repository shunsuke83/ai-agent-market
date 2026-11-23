import { Card, DetailPageLayout, Text } from "@genonai/admin-design-system";

export default function DeliverablesPage() {
  return (
    <DetailPageLayout title="산출물 안내" description="이 사이트가 매일 만드는 데이터와 화면">
      <Card>
        <Text as="h2" variant="heading">
          데이터
        </Text>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.7 }}>
          <li>나라장터 Open API 기반 AI 공고·낙찰·사전규격·발주계획 스냅샷</li>
          <li>공개: 정적 JSON (`/data/spa/…`) · 내부: Cloudflare D1 + `/api/notices`</li>
          <li>적합도(참여/검토/보류)는 수집 시점 회사 프로파일 기준으로 산출</li>
        </ul>
      </Card>
      <Card>
        <Text as="h2" variant="heading">
          UI
        </Text>
        <p style={{ margin: "8px 0 0", color: "var(--color-text-secondary)" }}>
          GenON Admin Design System(`@genonai/admin-design-system`) 템플릿 — 대시보드·리스트·상세.
        </p>
      </Card>
    </DetailPageLayout>
  );
}
