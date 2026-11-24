import { Alert, Card, DetailPageLayout, Text } from "@genonai/admin-design-system";
import { IS_INTERNAL } from "../config";

const FEEDS = [
  { href: "/feeds/genai.xml", label: "생성형 AI RSS" },
  { href: "/feeds/band-build.xml", label: "8~30억 구축 RSS" },
  { href: "/feeds/isp.xml", label: "ISP·컨설팅 RSS" },
  { href: "/feeds/large.xml", label: "대형 사업 RSS" },
  { href: "/feeds/deadlines.ics", label: "마감 캘린더 (ICS)" },
  { href: "/feeds/renewals.ics", label: "갱신 캘린더 (ICS)" },
];

export default function AlertsPage() {
  return (
    <DetailPageLayout title="알림 구독" description="RSS·캘린더로 공고 변화를 받아보세요">
      {IS_INTERNAL ? (
        <Alert tone="info" title="내부 모드">
          공개 피드와 동일한 경로를 제공합니다. Access 뒤에서만 열립니다.
        </Alert>
      ) : null}
      <Card>
        <Text as="h2" variant="heading">
          구독 링크
        </Text>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.8 }}>
          {FEEDS.map((f) => (
            <li key={f.href}>
              <a href={f.href}>{f.label}</a>
            </li>
          ))}
        </ul>
      </Card>
    </DetailPageLayout>
  );
}
