/**
 * Search, column filters and "show more" paging for result tables
 * (table.band-results). Works with table-sort.js: paging re-applies after a sort.
 * Search, filters and sort live in the URL (?q=&status=&scope=&sort=) so a
 * link reopens the same view.
 */
(function () {
  "use strict";

  var PAGE = 50;

  function text(el) {
    return (el.textContent || "").replace(/\s+/g, " ").trim();
  }

  function label(th) {
    return text(th).replace(/[▲▼]/g, "").trim();
  }

  function headerIndex(table, name) {
    var ths = table.tHead.rows[0].cells;
    for (var i = 0; i < ths.length; i++) {
      if (label(ths[i]) === name) return i;
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

  function setSelect(sel, value) {
    if (!sel || !value) return;
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === value) {
        sel.value = value;
        return;
      }
    }
  }

  function enhance(table, syncUrl) {
    var tbody = table.tBodies[0];
    if (!table.tHead || !tbody) return;
    var wrap = table.closest(".tbl") || table;
    var rows = Array.prototype.slice.call(tbody.rows);
    if (!rows.length) return;
    var ths = table.tHead.rows[0].cells;

    var statusCol = headerIndex(table, "상태");
    var scopeCol = headerIndex(table, "범위");
    var budgetCol = headerIndex(table, "예산(억)");
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
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "tbl-clear";
    clear.textContent = "초기화";
    tools.appendChild(clear);
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

    function sortState() {
      for (var i = 0; i < ths.length; i++) {
        var s = ths[i].getAttribute("aria-sort");
        if (s === "ascending" || s === "descending") {
          return label(ths[i]) + ":" + (s === "ascending" ? "asc" : "desc");
        }
      }
      return "";
    }

    function writeUrl() {
      if (!syncUrl || !window.history || !window.history.replaceState) return;
      var params = new URLSearchParams(window.location.search);
      var state = {
        q: q.value.trim(),
        status: statusSel ? statusSel.value : "",
        scope: scopeSel ? scopeSel.value : "",
        sort: sortState(),
      };
      Object.keys(state).forEach(function (k) {
        if (state[k]) params.set(k, state[k]);
        else params.delete(k);
      });
      var qs = params.toString();
      window.history.replaceState(
        null,
        "",
        window.location.pathname + (qs ? "?" + qs : "") + window.location.hash
      );
    }

    function apply() {
      var shown = 0;
      var matched = 0;
      var budget = 0;
      var current = tbody.rows;
      for (var i = 0; i < current.length; i++) {
        var row = current[i];
        var ok = matches(row);
        if (ok) {
          matched++;
          if (budgetCol >= 0) {
            var b = parseFloat(text(row.cells[budgetCol]).replace(/,/g, ""));
            if (!isNaN(b)) budget += b;
          }
        }
        var visible = ok && shown < limit;
        if (visible) shown++;
        row.hidden = !visible;
      }
      var budgetTxt =
        budgetCol >= 0
          ? " · 예산 합계 " + Math.round(budget).toLocaleString("ko-KR") + "억"
          : "";
      var filtered = !!(q.value || (statusSel && statusSel.value) || (scopeSel && scopeSel.value));
      count.textContent =
        (filtered ? "검색 결과 " : "전체 ") +
        matched +
        "건" +
        budgetTxt +
        (shown < matched ? " · " + shown + "건 표시" : "");
      var rest = matched - shown;
      more.hidden = rest <= 0;
      more.textContent = "더 보기 (남은 " + rest + "건)";
      clear.hidden = !filtered;
      writeUrl();
    }

    function reset() {
      limit = PAGE;
      apply();
    }

    q.addEventListener("input", reset);
    if (statusSel) statusSel.addEventListener("change", reset);
    if (scopeSel) scopeSel.addEventListener("change", reset);
    clear.addEventListener("click", function () {
      q.value = "";
      if (statusSel) statusSel.value = "";
      if (scopeSel) scopeSel.value = "";
      reset();
      q.focus();
    });
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

    if (syncUrl) {
      var params = new URLSearchParams(window.location.search);
      q.value = params.get("q") || "";
      setSelect(statusSel, params.get("status"));
      setSelect(scopeSel, params.get("scope"));
      var sort = (params.get("sort") || "").split(":");
      var col = sort[0] ? headerIndex(table, sort[0]) : -1;
      if (col >= 0) {
        // table-sort.js toggles asc → desc on repeated clicks.
        ths[col].click();
        if (sort[1] === "desc") ths[col].click();
      }
    }
    apply();
  }

  function init() {
    var tables = document.querySelectorAll("table.band-results");
    for (var i = 0; i < tables.length; i++) enhance(tables[i], i === 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
