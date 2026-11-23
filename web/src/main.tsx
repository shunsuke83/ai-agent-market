import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@genonai/admin-design-system/styles.css";
import App from "./App";
import { SITE_TITLE } from "./config";

document.title = SITE_TITLE;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
