/**
 * Search, column filters and "show more" paging for long result tables
 * (table.band-results). Works with table-sort.js: paging re-applies after a sort.
 */
(function () {
  "use strict";

  var PAGE = 50;

  function text(el) {
    return (el.textContent || "").replace(/\s+/g, " ").trim();
  }

  function headerIndex(table, label) {
    var ths = table.tHead.rows[0].cells;
    for (var i = 0; i < ths.length; i++) {
      if (text(ths[i]).replace(/[▲▼]/g, "").trim() === label) return i;
    }
    return -1;
  }

  function buildSelect(rows, col, allLabel) {
    var counts = {};
    var order = [];
    for (var i = 0; i < rows.length; i++) {
      var v = text(rows[i].cells[col]);
      if (!v) continue;
      if (!(v in counts)) {
        counts[v] = 0;
        order.push(v);
      }
      counts[v]++;
    }
    order.sort(function (a, b) {
      return counts[b] - counts[a];
    });
    var sel = document.createElement("select");
    sel.setAttribute("aria-label", allLabel);
    var all = document.createElement("option");
    all.value = "";
    all.textContent = allLabel;
    sel.appendChild(all);
    for (var j = 0; j < order.length; j++) {
      var o = document.createElement("option");
      o.value = order[j];
      o.textContent = order[j] + " (" + counts[order[j]] + ")";
      sel.appendChild(o);
    }
    return sel;
  }

  function enhance(table) {
    var tbody = table.tBodies[0];
    if (!table.tHead || !tbody) return;
    var wrap = table.closest(".tbl") || table;
    var rows = Array.prototype.slice.call(tbody.rows);
    if (rows.length <= PAGE) return;

    var statusCol = headerIndex(table, "상태");
    var scopeCol = headerIndex(table, "범위");
    var searchCols = ["사업명", "수요기관", "낙찰자"]
      .map(function (l) {
        return headerIndex(table, l);
      })
      .filter(function (i) {
        return i >= 0;
      });

    var tools = document.createElement("div");
    tools.className = "tbl-tools";
    var q = document.createElement("input");
    q.type = "search";
    q.placeholder = "사업명·수요기관·낙찰자 검색";
    q.setAttribute("aria-label", "공고 검색");
    tools.appendChild(q);
    var statusSel = statusCol >= 0 ? buildSelect(rows, statusCol, "상태 전체") : null;
    if (statusSel) tools.appendChild(statusSel);
    var scopeSel = scopeCol >= 0 ? buildSelect(rows, scopeCol, "범위 전체") : null;
    if (scopeSel) tools.appendChild(scopeSel);
    var count = document.createElement("span");
    count.className = "tbl-count";
    count.setAttribute("aria-live", "polite");
    tools.appendChild(count);
    wrap.parentNode.insertBefore(tools, wrap);

    var more = document.createElement("button");
    more.type = "button";
    more.className = "tbl-more";
    wrap.parentNode.insertBefore(more, wrap.nextSibling);

    var limit = PAGE;

    function matches(row) {
      if (statusSel && statusSel.value && text(row.cells[statusCol]) !== statusSel.value) return false;
      if (scopeSel && scopeSel.value && text(row.cells[scopeCol]) !== scopeSel.value) return false;
      var needle = q.value.trim().toLocaleLowerCase("ko");
      if (!needle) return true;
      for (var i = 0; i < searchCols.length; i++) {
        if (text(row.cells[searchCols[i]]).toLocaleLowerCase("ko").indexOf(needle) >= 0) return true;
      }
      return false;
    }

    function apply() {
      var shown = 0;
      var matched = 0;
      var current = tbody.rows;
      for (var i = 0; i < current.length; i++) {
        var row = current[i];
        var ok = matches(row);
        if (ok) matched++;
        var visible = ok && shown < limit;
        if (visible) shown++;
        row.hidden = !visible;
      }
      count.textContent = matched + "건 중 " + shown + "건 표시";
      var rest = matched - shown;
      more.hidden = rest <= 0;
      more.textContent = "더 보기 (남은 " + rest + "건)";
    }

    function reset() {
      limit = PAGE;
      apply();
    }

    q.addEventListener("input", reset);
    if (statusSel) statusSel.addEventListener("change", reset);
    if (scopeSel) scopeSel.addEventListener("change", reset);
    more.addEventListener("click", function () {
      limit += PAGE * 2;
      apply();
    });
    // table-sort.js reorders rows on header click; re-page in the new order.
    table.tHead.addEventListener("click", function () {
      setTimeout(apply, 0);
    });
    table.tHead.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") setTimeout(apply, 0);
    });

    apply();
  }

  function init() {
    var tables = document.querySelectorAll("table.band-results");
    for (var i = 0; i < tables.length; i++) enhance(tables[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
