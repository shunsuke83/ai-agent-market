/* bidders.html: 사업자번호·업체명으로 data/bidders.json 검색 */
(function () {
  "use strict";

  var LIST_LIMIT = 50;
  var RIVALS_SHOWN = 8;
  var box = document.getElementById("bidder-results");
  var input = document.getElementById("bidder-q");
  if (!box || !input) return;

  var data = null;
  var byNotice = [];
  var keys = [];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function digits(s) {
    return String(s || "").replace(/\D/g, "");
  }
  function fmtBizno(bz) {
    return bz.length === 10 ? bz.slice(0, 3) + "-" + bz.slice(3, 5) + "-" + bz.slice(5) : bz;
  }
  function normName(s) {
    return String(s || "")
      .replace(/\(주\)|㈜|주식회사|\(유\)|유한회사|\(재\)|재단법인|\(사\)|사단법인/g, "")
      .replace(/\s+/g, "")
      .toLowerCase();
  }
  function num(v, digitsAfter) {
    return v == null ? "" : Number(v).toFixed(digitsAfter);
  }
  function median(xs) {
    if (!xs.length) return null;
    var s = xs.slice().sort(function (a, b) { return a - b; });
    var m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function msg(text) {
    box.innerHTML = '<p class="meta">' + esc(text) + "</p>";
  }

  function prepare(json) {
    data = json;
    byNotice = json.notices.map(function () { return []; });
    keys = Object.keys(json.firms);
    keys.forEach(function (bz) {
      json.firms[bz][2].forEach(function (b) {
        byNotice[b[0]].push([bz, b[1]]);
      });
    });
  }

  function isRate(v) {
    return v != null && v >= 50 && v <= 110;
  }

  function result(notice, bz, rank) {
    var winner = notice[5];
    if (winner === bz) return "<b>낙찰</b>";
    if (winner) {
      var name = data.firms[winner] ? data.firms[winner][0] : fmtBizno(winner);
      return '<a href="#' + winner + '" title="낙찰 업체">' + esc(name) + "</a> 낙찰";
    }
    if (notice[6] === "낙찰") return "다른 업체 낙찰";
    if (rank === 1) return "1순위";
    return esc(notice[6] || "");
  }

  function rivals(bz, bids) {
    var faced = {};
    bids.forEach(function (b) {
      byNotice[b[0]].forEach(function (o) {
        if (o[0] === bz) return;
        var r = faced[o[0]] || (faced[o[0]] = { n: 0, beat: 0, lost: 0 });
        r.n += 1;
        if (b[1] != null && o[1] != null) {
          if (b[1] < o[1]) r.beat += 1;
          else if (b[1] > o[1]) r.lost += 1;
        }
      });
    });
    return Object.keys(faced)
      .sort(function (a, b) { return faced[b].n - faced[a].n || (data.firms[a][0] < data.firms[b][0] ? -1 : 1); })
      .slice(0, RIVALS_SHOWN)
      .map(function (o) {
        var r = faced[o];
        return '<a href="#' + o + '">' + esc(data.firms[o][0] || fmtBizno(o)) + "</a> " +
          r.n + "회(앞섬 " + r.beat + "·뒤짐 " + r.lost + ")";
      });
  }

  function showFirm(bz) {
    var firm = data.firms[bz];
    if (!firm) {
      msg("사업자번호 " + fmtBizno(bz) + "로 투찰한 AI 사업 공고가 없습니다.");
      return;
    }
    var bids = firm[2].slice().sort(function (a, b) {
      return (data.notices[b[0]][0] || "").localeCompare(data.notices[a[0]][0] || "");
    });
    var wins = 0;
    var firsts = 0;
    var rates = [];
    bids.forEach(function (b) {
      var n = data.notices[b[0]];
      if (n[5] === bz) wins += 1;
      else if (!n[5] && n[6] !== "낙찰" && b[1] === 1) firsts += 1;
      if (isRate(b[2])) rates.push(b[2]);
    });
    var med = median(rates);
    var head = ["사업자번호 " + fmtBizno(bz)];
    if (firm[1]) head.push(firm[1]);
    var rv = rivals(bz, bids);
    var changes = (firm[3] || []).map(function (c) {
      return esc(c[0]) + (c[2] ? "" : "(확인일)") + " " + esc(c[1]);
    });
    var rows = bids.map(function (b) {
      var n = data.notices[b[0]];
      var title = n[4] ? '<a href="' + esc(n[4]) + '">' + esc(n[2]) + "</a>" : esc(n[2]);
      return "<tr><td>" + esc(n[0]) + "</td><td>" + esc(n[1]) + "</td><td>" + title + "</td>" +
        '<td class="num">' + num(n[3], 1) + "</td>" +
        '<td class="num">' + (b[1] == null ? "" : b[1] + "/" + byNotice[b[0]].length) + "</td>" +
        (isRate(b[2]) ? '<td class="num">' + num(b[2], 2) + "</td>"
          : '<td class="num" title="협상계약 가격점수 등 투찰률이 아닌 값">-</td>') +
        '<td class="num">' + num(b[3], 2) + "</td>" +
        "<td>" + result(n, bz, b[1]) + "</td></tr>";
    });
    box.innerHTML =
      "<h2>" + esc(firm[0] || fmtBizno(bz)) + "</h2>" +
      '<p class="meta">' + esc(head.join(" · ")) + "</p>" +
      (changes.length ? '<p class="meta">나라장터 등록정보 변경: ' + changes.join(" / ") + "</p>" : "") +
      '<div class="stats">' +
      '<div class="stat"><div class="v">' + bids.length + '건</div><div class="l">투찰</div></div>' +
      '<div class="stat"><div class="v">' + wins + '건</div><div class="l">낙찰 확정</div></div>' +
      '<div class="stat"><div class="v">' + firsts + '건</div><div class="l">1순위 (확정 전)</div></div>' +
      '<div class="stat"><div class="v">' + (med == null ? "-" : med.toFixed(2) + "%") +
      '</div><div class="l">투찰률 중앙값 (' + rates.length + "건)</div></div>" +
      "</div>" +
      (rv.length ? '<p class="meta rivals">자주 맞붙은 업체(개찰 순위 기준): ' + rv.join(", ") + "</p>" : "") +
      '<div class="tbl"><table class="notices bidder-history"><thead><tr><th>개찰일</th><th>수요기관</th>' +
      '<th>사업명</th><th class="num">예산(억)</th><th class="num">순위</th><th class="num">투찰률(%)</th>' +
      '<th class="num">투찰금액(억)</th><th>결과</th></tr></thead><tbody>' + rows.join("") +
      "</tbody></table></div>" +
      '<p class="note">순위 옆 숫자는 그 공고의 투찰 업체 수입니다. 투찰률은 예정가격 대비 값(50~110%)만 보여 주고, ' +
      "협상계약의 가격점수처럼 이 범위 밖의 값은 '-'로 둡니다.</p>";
  }

  function showList(matches, q) {
    matches.sort(function (a, b) {
      return data.firms[b][2].length - data.firms[a][2].length || (data.firms[a][0] < data.firms[b][0] ? -1 : 1);
    });
    var rows = matches.slice(0, LIST_LIMIT).map(function (bz) {
      var f = data.firms[bz];
      var wins = f[2].filter(function (b) { return data.notices[b[0]][5] === bz; }).length;
      return '<tr><td><a href="#' + bz + '">' + esc(f[0] || fmtBizno(bz)) + "</a></td><td>" + fmtBizno(bz) +
        "</td><td>" + esc(f[1] || "") + '</td><td class="num">' + f[2].length + '</td><td class="num">' + wins + "</td></tr>";
    });
    var more = matches.length > LIST_LIMIT ? " 투찰이 많은 순으로 " + LIST_LIMIT + "곳만 보여 줍니다." : "";
    box.innerHTML =
      '<p class="meta">"' + esc(q) + '"에 맞는 업체 ' + matches.length + "곳." + more + "</p>" +
      '<div class="tbl"><table class="notices"><thead><tr><th>업체</th><th>사업자번호</th><th>지역·규모</th>' +
      '<th class="num">투찰</th><th class="num">낙찰</th></tr></thead><tbody>' + rows.join("") + "</tbody></table></div>";
  }

  function search() {
    if (!data) return;
    var q = input.value.trim();
    if (!q) {
      msg("사업자번호(하이픈 있어도 됨)나 업체명 일부를 입력하세요.");
      return;
    }
    var d = digits(q);
    var numeric = /^[\d\s-]+$/.test(q);
    if (numeric && d.length === 10) {
      showFirm(d);
      return;
    }
    if (numeric && d.length < 3) {
      msg("사업자번호는 3자리 이상 입력하세요.");
      return;
    }
    var nq = normName(q);
    var matches = keys.filter(function (bz) {
      return numeric ? bz.indexOf(d) === 0 : nq && normName(data.firms[bz][0]).indexOf(nq) !== -1;
    });
    if (!matches.length) msg('"' + q + '"에 맞는 업체가 없습니다.');
    else if (matches.length === 1) showFirm(matches[0]);
    else showList(matches, q);
  }

  function fromHash() {
    var bz = digits(location.hash);
    if (bz.length === 10 && data) {
      input.value = fmtBizno(bz);
      showFirm(bz);
      window.scrollTo(0, box.offsetTop - 80);
    }
  }

  var timer = null;
  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(search, 200);
  });
  window.addEventListener("hashchange", fromHash);

  msg("업체 목록을 불러오는 중입니다…");
  fetch(box.getAttribute("data-src"))
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function (json) {
      prepare(json);
      if (digits(location.hash).length === 10) fromHash();
      else search();
    })
    .catch(function () {
      msg("업체 목록을 불러오지 못했습니다. 잠시 뒤 새로고침해 주세요.");
    });
})();
