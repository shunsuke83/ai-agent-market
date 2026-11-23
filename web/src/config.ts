export const APP_MODE = import.meta.env.VITE_APP_MODE === "internal" ? "internal" : "public";
export const IS_INTERNAL = APP_MODE === "internal";
export const SITE_TITLE = "AI 사업 입찰·수주 분석";
