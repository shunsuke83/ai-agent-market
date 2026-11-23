import { useState } from "react";
import { Outlet } from "react-router-dom";
import { AppShellFrame, AppSidebar, AppTopbar, Badge, Button } from "@genonai/admin-design-system";
import { IS_INTERNAL, SITE_TITLE } from "../config";
import { NAV_GROUPS } from "./nav";

export default function Shell() {
  const [open, setOpen] = useState(false);

  const brand = (
    <>
      <span>{SITE_TITLE}</span>
      {IS_INTERNAL ? <Badge tone="brand">내부</Badge> : null}
    </>
  );

  return (
    <AppShellFrame
      sidebar={
        <AppSidebar
          brand={brand}
          groups={NAV_GROUPS}
          open={open}
          onNavigate={() => setOpen(false)}
          footer={IS_INTERNAL ? "내부 전용 · Cloudflare Access" : "공개 데이터 기반 분석"}
        />
      }
      topbar={
        <AppTopbar title={brand}>
          <Button variant="secondary" onClick={() => setOpen((v) => !v)}>
            {open ? "닫기" : "메뉴"}
          </Button>
        </AppTopbar>
      }
    >
      <Outlet />
    </AppShellFrame>
  );
}
