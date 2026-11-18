"""Create Cloudflare Access app for internal Pages — allow @genon.ai only."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = "cb5fd8f2bd7d6aef3fd6042aa374e8b3"
DOMAIN = "ai-agent-market-internal.pages.dev"
APP_NAME = "AI agent market internal"


def token() -> str:
    env = __import__("os").environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if env:
        return env
    cfg = Path.home() / "AppData/Roaming/xdg.config/.wrangler/config/default.toml"
    m = re.search(r'oauth_token\s*=\s*"([^"]+)"', cfg.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(
            "CLOUDFLARE_API_TOKEN 또는 wrangler login 필요 "
            "(Access 쓰기는 API Token에 Access: Apps and Policies Write 필요)"
        )
    return m.group(1)


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "authorization": f"Bearer {token()}",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code == 403 and "not_enabled" in detail:
            raise SystemExit(
                "Access(Zero Trust)가 아직 켜져 있지 않습니다.\n"
                "https://one.dash.cloudflare.com/ 에서 조직 생성(Free) 후 다시 실행하세요."
            ) from e
        raise SystemExit(f"HTTP {e.code}: {detail}") from e
    if not payload.get("success"):
        raise SystemExit(payload.get("errors"))
    return payload


def main() -> None:
    listed = api("GET", f"/accounts/{ACCOUNT_ID}/access/apps")
    existing = [
        a
        for a in (listed.get("result") or [])
        if a.get("domain") == DOMAIN or a.get("name") == APP_NAME
    ]
    if existing:
        app = existing[0]
        print(json.dumps({"already": True, "id": app.get("id"), "domain": app.get("domain")}, ensure_ascii=False))
        return

    # Also cover preview URLs: *.ai-agent-market-internal.pages.dev
    created = api(
        "POST",
        f"/accounts/{ACCOUNT_ID}/access/apps",
        {
            "type": "self_hosted",
            "name": APP_NAME,
            "domain": DOMAIN,
            "self_hosted_domains": [DOMAIN, f"*.{DOMAIN}"],
            "session_duration": "24h",
            "auto_redirect_to_identity": False,
            "policies": [
                {
                    "name": "Allow genon.ai",
                    "decision": "allow",
                    "include": [{"email_domain": {"domain": "genon.ai"}}],
                }
            ],
        },
    )
    result = created.get("result") or {}
    print(
        json.dumps(
            {
                "created": True,
                "id": result.get("id"),
                "domain": result.get("domain"),
                "self_hosted_domains": result.get("self_hosted_domains"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
