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
  const score =
    item.fit_score != null && Number.isFinite(Number(item.fit_score))
      ? ` ${item.fit_score}점`
      : "";
  return `<span class="fit" data-verdict="${esc(item.fit_verdict)}">${esc(label)}${esc(score)}</span>`;
}

let listOffset = 0;
const PAGE = 100;

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

async function loadList({ append = false } = {}) {
  const form = document.getElementById("filters");
  const fd = new FormData(form);
  const params = new URLSearchParams();
  const q = String(fd.get("q") || "").trim();
  if (q) params.set("q", q);
  if (fd.get("excluded")) params.set("excluded", "1");
  if (!fd.get("open")) params.set("open", "0");
  const fit = String(fd.get("fit") || "");
  if (fit) params.set("fit", fit);
  if (!append) listOffset = 0;
  params.set("limit", String(PAGE));
  params.set("offset", String(listOffset));

  let data;
  try {
    const res = await fetch(`/api/notices?${params}`);
    data = await res.json();
  } catch {
    document.getElementById("count").textContent = "목록 조회 실패";
    return;
  }
  const total = data.total ?? 0;
  document.getElementById("count").textContent = `총 ${total.toLocaleString?.() ?? total}건`;

  const tbody = document.getElementById("rows");
  const rowsHtml = (data.items || [])
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
  if (!append) {
    tbody.innerHTML = rowsHtml || `<tr><td colspan="6" class="meta">조건에 맞는 공고가 없습니다.</td></tr>`;
  } else if (rowsHtml) {
    tbody.insertAdjacentHTML("beforeend", rowsHtml);
  }
  listOffset += (data.items || []).length;
  const more = document.getElementById("more");
  if (more) more.hidden = listOffset >= total;
}

document.getElementById("filters").addEventListener("submit", (e) => {
  e.preventDefault();
  loadList();
});
const moreBtn = document.getElementById("more");
if (moreBtn) {
  moreBtn.addEventListener("click", () => loadList({ append: true }));
}

loadMeta();
loadList();
