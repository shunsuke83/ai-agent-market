import { EmptyState, ListPageLayout } from "@genonai/admin-design-system";

export default function StubPage({
  title,
  description,
  message = "준비 중인 화면입니다.",
}: {
  title: string;
  description?: string;
  message?: string;
}) {
  return (
    <ListPageLayout title={title} description={description}>
      <EmptyState title={message} description="React SPA로 이전 중입니다." />
    </ListPageLayout>
  );
}
