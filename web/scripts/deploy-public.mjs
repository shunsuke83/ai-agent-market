/**
 * Deploy the public Cloudflare Pages project without attaching web/functions
 * (or D1). Mirrors collect.yml: copy dist to a temp folder that has no
 * functions/ sibling, strip _routes.json, then wrangler pages deploy.
 */
import { cpSync, existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(webRoot, "dist");
if (!existsSync(join(dist, "index.html"))) {
  console.error("web/dist/index.html missing — run build:public (+ stage-public) first.");
  process.exit(1);
}

const staging = mkdtempSync(join(tmpdir(), "aam-public-"));
const stagedDist = join(staging, "dist");
try {
  cpSync(dist, stagedDist, { recursive: true });
  for (const name of ["_routes.json"]) {
    const p = join(stagedDist, name);
    if (existsSync(p)) rmSync(p);
  }
  writeFileSync(
    join(staging, "wrangler.toml"),
    `name = "ai-agent-market"\ncompatibility_date = "2025-11-01"\npages_build_output_dir = "dist"\n`,
    "utf8",
  );

  const npx = process.platform === "win32" ? "npx.cmd" : "npx";
  const result = spawnSync(
    npx,
    ["--yes", "wrangler", "pages", "deploy", "dist", "--project-name=ai-agent-market", "--commit-dirty=true"],
    { cwd: staging, stdio: "inherit", shell: process.platform === "win32", env: process.env },
  );
  process.exit(result.status ?? 1);
} finally {
  try {
    rmSync(staging, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
}
