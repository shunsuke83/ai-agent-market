import { Link } from "react-router-dom";
import { Card, EmptyState } from "@genonai/admin-design-system";

export default function NotFoundPage() {
  return (
    <Card>
      <EmptyState title="페이지를 찾을 수 없습니다" description="주소를 확인해 주세요." />
      <div style={{ textAlign: "center" }}>
        <Link to="/">홈으로</Link>
      </div>
    </Card>
  );
}
