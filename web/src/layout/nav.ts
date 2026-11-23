import type { NavGroup } from "@genonai/admin-design-system";

/** Mirrors collector/g2b/site.py NAV_GROUPS as SPA paths. */
export const NAV_GROUPS: NavGroup[] = [
  { items: [{ to: "/", label: "홈" }] },
  {
    label: "시장 분석",
    items: [
      { to: "/band", label: "8~30억 분석" },
      { to: "/awards", label: "수주 현황" },
      { to: "/pricing", label: "투찰·경쟁" },
      { to: "/plans", label: "발주 예정" },
      { to: "/prespecs", label: "사전규격" },
    ],
  },
  {
    label: "검색",
    items: [
      { to: "/bidders", label: "입찰이력 검색" },
      { to: "/agencies", label: "발주기관 검색" },
      { to: "/alerts", label: "알림 구독" },
    ],
  },
  {
    label: "기업·리포트",
    items: [
      { to: "/competitors", label: "국내 전문기업" },
      { to: "/reports", label: "리포트 목록" },
      { to: "/deliverables", label: "산출물 안내" },
    ],
  },
];
