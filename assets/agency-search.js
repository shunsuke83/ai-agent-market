/* agencies.html: 수요기관명으로 data/agencies.json 검색 */
(function () {
  "use strict";

  var LIST_LIMIT = 50;
  var WINNERS_SHOWN = 10;
  var box = document.getElementById("agency-results");
  var input = document.getElementById("agency-q");
  if (!box || !input) return;

  var rows = [];
  var byOrg = {};
  var orgs = [];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function norm(s) {
    return String(s || "").replace(/\s+/g, "").toLowerCase();
  }
  function eok(v) {
    return v == null ? "" : Number(v).toFixed(1);
  }
  function msg(text) {
    box.innerHTML = '<p class="meta">' + esc(text) + "</p>";
  }
  function orgLink(org) {
    return '<a href="#org=' + encodeURIComponent(org) + '">' + esc(org) + "</a>";
  }
  function firmLink(name, bz) {
    return bz ? '<a href="bidders.html#' + esc(bz) + '" title="입찰이력 보기">' + esc(name) + "</a>" : esc(name);
  }

  function prepare(json) {
    rows = json.notices;
    rows.forEach(function (r, i) {
      (byOrg[r[1]] || (byOrg[r[1]] = [])).push(i);
    });
    orgs = Object.keys(byOrg);
  }

  function winnerCell(r) {
    if (!r[5]) return "";
    if (r[8] === "낙찰") return firmLink(r[5], r[6]);
    return firmLink(r[5], r[6]) + ' <span class="meta" title="개찰 1순위, 낙찰 확정 전">(1순위)</span>';
  }

  function showOrg(org) {
    var list = byOrg[org];
    if (!list) {
      msg('"' + org + '" 기관의 AI 사업 공고가 없습니다.');
      return;
    }
    var budget = 0;
    var won = 0;
    var award = 0;
    var awardN = 0;
    var core = 0;
    var counts = [];
    var winners = {};
    list.forEach(function (i) {
      var r = rows[i];
      if (r[3] != null) budget += r[3];
      if (r[10]) core += 1;
      if (r[9] != null) counts.push(r[9]);
      if (r[8] !== "낙찰" || !r[5]) return;
      won += 1;
      if (r[7] != null) { award += r[7]; awardN += 1; }
      var k = r[6] || r[5];
      var w = winners[k] || (winners[k] = { name: r[5], bz: r[6], n: 0, amt: 0 });
      w.n += 1;
      if (r[7] != null) w.amt += r[7];
    });
    var avgBids = counts.length
      ? (counts.reduce(function (a, b) { return a + b; }, 0) / counts.length).toFixed(1) + "곳"
      : "-";
    var top = Object.keys(winners)
      .sort(function (a, b) { return winners[b].n - winners[a].n || winners[b].amt - winners[a].amt; })
      .slice(0, WINNERS_SHOWN)
      .map(function (k) {
        var w = winners[k];
        return firmLink(w.name, w.bz) + " " + w.n + "건" + (w.amt ? "(" + eok(w.amt) + "억)" : "");
      });
    var body = list.map(function (i) {
      var r = rows[i];
      var title = r[4] ? '<a href="' + esc(r[4]) + '">' + esc(r[2]) + "</a>" : esc(r[2]);
      return "<tr><td>" + esc(r[0]) + "</td><td>" + title + (r[10] ? ' <span class="meta">생성형·Agent</span>' : "") +
        '</td><td class="num">' + eok(r[3]) + "</td><td>" + esc(r[8] || "") + "</td><td>" + winnerCell(r) +
        '</td><td class="num">' + eok(r[7]) + '</td><td class="num">' + (r[9] == null ? "" : r[9]) + "</td></tr>";
    });
    box.innerHTML =
      "<h2>" + esc(org) + "</h2>" +
      '<div class="stats">' +
      '<div class="stat"><div class="v">' + list.length + '건</div><div class="l">AI 사업 공고 (생성형·Agent ' + core + "건)</div></div>" +
      '<div class="stat"><div class="v">' + eok(budget) + '억</div><div class="l">예산 합계</div></div>' +
      '<div class="stat"><div class="v">' + won + '건</div><div class="l">낙찰 확정</div></div>' +
      '<div class="stat"><div class="v">' + (awardN ? eok(award) + "억" : "-") +
      '</div><div class="l">낙찰금액 합계 (공개 ' + awardN + "건)</div></div>" +
      '<div class="stat"><div class="v">' + avgBids + '</div><div class="l">평균 응찰 업체 수</div></div>' +
      "</div>" +
      (top.length ? '<p class="meta rivals">이 기관 사업을 낙찰받은 업체: ' + top.join(", ") + "</p>" : "") +
      '<div class="tbl"><table class="notices agency-history"><thead><tr><th>공고일</th><th>사업명</th>' +
      '<th class="num">예산(억)</th><th>상태</th><th>낙찰 업체</th><th class="num">낙찰금액(억)</th>' +
      '<th class="num">응찰</th></tr></thead><tbody>' + body.join("") + "</tbody></table></div>" +
      '<p class="note">업체 이름을 누르면 그 업체의 입찰이력으로 갑니다. 사업자번호를 확인한 업체만 연결됩니다.</p>';
  }

  function showList(matches, q) {
    var nq = norm(q);
    matches.sort(function (a, b) {
      return (norm(b) === nq) - (norm(a) === nq) || byOrg[b].length - byOrg[a].length || (a < b ? -1 : 1);
    });
    var body = matches.slice(0, LIST_LIMIT).map(function (org) {
      var list = byOrg[org];
      var won = list.filter(function (i) { return rows[i][8] === "낙찰"; }).length;
      var budget = list.reduce(function (s, i) { return s + (rows[i][3] || 0); }, 0);
      return "<tr><td>" + orgLink(org) + '</td><td class="num">' + list.length + '</td><td class="num">' + won +
        '</td><td class="num">' + eok(budget) + "</td><td>" + esc(rows[list[0]][0]) + "</td></tr>";
    });
    var more = matches.length > LIST_LIMIT ? " 공고가 많은 순으로 " + LIST_LIMIT + "곳만 보여 줍니다." : "";
    box.innerHTML =
      '<p class="meta">"' + esc(q) + '"에 맞는 기관 ' + matches.length + "곳." + more + "</p>" +
      '<div class="tbl"><table class="notices"><thead><tr><th>수요기관</th><th class="num">공고</th>' +
      '<th class="num">낙찰</th><th class="num">예산 합계(억)</th><th>최근 공고일</th></tr></thead><tbody>' +
      body.join("") + "</tbody></table></div>";
  }

  function search() {
    if (!rows.length) return;
    var q = input.value.trim();
    var nq = norm(q);
    if (nq.length < 2) {
      msg("기관명을 2글자 이상 입력하세요.");
      return;
    }
    var matches = orgs.filter(function (o) { return norm(o).indexOf(nq) !== -1; });
    if (!matches.length) msg('"' + q + '"에 맞는 기관이 없습니다.');
    else if (matches.length === 1) showOrg(matches[0]);
    else showList(matches, q);
  }

  function hashOrg() {
    var m = /^#org=(.+)$/.exec(location.hash);
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return null; }
  }
  function fromHash() {
    var org = hashOrg();
    if (org && rows.length) {
      input.value = org;
      showOrg(org);
      window.scrollTo(0, box.offsetTop - 80);
    }
  }

  var timer = null;
  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(search, 200);
  });
  window.addEventListener("hashchange", fromHash);

  msg("기관 목록을 불러오는 중입니다…");
  fetch(box.getAttribute("data-src"))
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function (json) {
      prepare(json);
      if (hashOrg()) fromHash();
      else msg("기관명 일부를 입력하세요.");
    })
    .catch(function () {
      msg("기관 목록을 불러오지 못했습니다. 잠시 뒤 새로고침해 주세요.");
    });
})();
