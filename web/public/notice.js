function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitPill(verdict, score) {
  if (!verdict) return "";
  const label = { GO: "참여", REVIEW: "검토", "NO-GO": "보류" }[verdict] || verdict;
  return `<span class="fit" data-verdict="${esc(verdict)}">${esc(label)} ${score ?? ""}점</span>`;
}

const id = new URLSearchParams(location.search).get("id");
const main = document.getElementById("main");

if (!id) {
  main.innerHTML = `<p class="meta">id 파라미터가 필요합니다.</p>`;
} else {
  fetch(`/api/notices/${encodeURIComponent(id)}`)
    .then((r) => {
      if (!r.ok) throw new Error("not found");
      return r.json();
    })
    .then((n) => {
      document.title = `${n.title || id} · 내부`;
      const reasons = (n.fit_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("");
      const g2b = n.g2b_url
        ? `<tr><th>나라장터</th><td><a href="${esc(n.g2b_url)}" target="_blank" rel="noopener">원문 ↗</a></td></tr>`
        : "";
      main.innerHTML = `
        <p class="meta">${esc(n.bid_no)}-${esc(n.bid_ord)} · 갱신 ${esc(n.updated_at || "")}</p>
        <h1>${esc(n.title)}</h1>
        <p>${fitPill(n.fit_verdict, n.fit_score)}
          ${n.soft_excluded ? `<span class="meta">제외: ${esc(n.exclude_reason || "")}</span>` : ""}</p>
        ${reasons ? `<ul class="reasons">${reasons}</ul>` : ""}
        <div class="tbl" style="margin-top:16px">
          <table class="kv">
            <tbody>
              <tr><th>수요기관</th><td>${esc(n.org)}</td></tr>
              <tr><th>분류</th><td>${esc([n.scope, n.nature, ...(n.fields || [])].filter(Boolean).join(" · "))}</td></tr>
              <tr><th>예산</th><td>${n.budget_eok != null ? esc(n.budget_eok) + "억" : ""}</td></tr>
              <tr><th>공고일</th><td>${esc(n.notice_date)}</td></tr>
              <tr><th>입찰 마감</th><td>${esc(n.close_at)}</td></tr>
              <tr><th>개찰</th><td>${esc(n.open_date || n.open_at)}</td></tr>
              <tr><th>계약 방식</th><td>${esc(n.contract_method)}</td></tr>
              <tr><th>낙찰/1순위</th><td>${esc(n.winner || n.first_rank)}</td></tr>
              ${g2b}
            </tbody>
          </table>
        </div>`;
    })
    .catch(() => {
      main.innerHTML = `<p class="meta">공고를 찾지 못했습니다.</p>`;
    });
}
