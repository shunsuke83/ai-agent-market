function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitPill(item) {
  if (!item.fit_verdict) return "";
  const label = { GO: "참여", REVIEW: "검토", "NO-GO": "보류" }[item.fit_verdict] || item.fit_verdict;
  const score = item.fit_score != null ? ` ${item.fit_score}점` : "";
  return `<span class="fit" data-verdict="${esc(item.fit_verdict)}">${esc(label)}${esc(score)}</span>`;
}

async function loadMeta() {
  try {
    const res = await fetch("/api/meta");
    const data = await res.json();
    const stamp = data.meta?.synced_at || data.meta?.collect_success_at;
    document.getElementById("stamp").textContent = stamp
      ? `D1 sync ${stamp}`
      : "D1 메타 없음 — sync-d1 실행 후 갱신됩니다";
  } catch {
    document.getElementById("stamp").textContent = "메타 조회 실패";
  }
}

async function loadList() {
  const form = document.getElementById("filters");
  const fd = new FormData(form);
  const params = new URLSearchParams();
  const q = String(fd.get("q") || "").trim();
  if (q) params.set("q", q);
  if (fd.get("excluded")) params.set("excluded", "1");
  if (!fd.get("open")) params.set("open", "0");
  const fit = String(fd.get("fit") || "");
  if (fit) params.set("fit", fit);
  params.set("limit", "100");

  const res = await fetch(`/api/notices?${params}`);
  const data = await res.json();
  document.getElementById("count").textContent = `총 ${data.total?.toLocaleString?.() ?? data.total}건`;

  const tbody = document.getElementById("rows");
  if (!data.items?.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="meta">조건에 맞는 공고가 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = data.items
    .map((n) => {
      const id = esc(n.id);
      return `<tr>
        <td>${fitPill(n)}</td>
        <td>${esc((n.close_at || "").slice(0, 16))}</td>
        <td>${esc(n.org)}</td>
        <td><a href="/notice.html?id=${id}">${esc(n.title)}</a></td>
        <td class="num">${n.budget_eok != null ? esc(n.budget_eok) : ""}</td>
        <td class="meta">${n.soft_excluded ? esc(n.exclude_reason || "제외") : ""}</td>
      </tr>`;
    })
    .join("");
}

document.getElementById("filters").addEventListener("submit", (e) => {
  e.preventDefault();
  loadList();
});

loadMeta();
loadList();
