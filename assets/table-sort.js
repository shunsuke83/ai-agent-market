/**
 * Click-to-sort for static data tables (.tbl table).
 * Progressive enhancement: no markup changes required beyond including this script.
 */
(function () {
  "use strict";

  var EMPTY = { empty: true, type: "empty", v: "" };

  function cellText(td) {
    return (td.textContent || "").replace(/\s+/g, " ").trim();
  }

  function parseCell(text, preferNum) {
    if (!text || text === "—" || text === "-" || text === "–") return EMPTY;

    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
      return { empty: false, type: "date", v: text };
    }

    var pct = text.match(/^(-?[\d,]+(?:\.\d+)?)\s*%$/);
    if (pct) {
      return { empty: false, type: "num", v: parseFloat(pct[1].replace(/,/g, "")) };
    }

    var pure = text.match(/^(-?[\d,]+(?:\.\d+)?)$/);
    if (pure) {
      return { empty: false, type: "num", v: parseFloat(pure[1].replace(/,/g, "")) };
    }

    if (preferNum) {
      var loose = text.replace(/[^\d.\-]/g, "");
      if (loose && /^-?\d+(?:\.\d+)?$/.test(loose)) {
        return { empty: false, type: "num", v: parseFloat(loose) };
      }
    }

    return { empty: false, type: "str", v: text.toLocaleLowerCase("ko") };
  }

  function columnPrefersNum(rows, col) {
    var numeric = 0;
    var seen = 0;
    for (var i = 0; i < rows.length; i++) {
      var cells = rows[i].cells;
      if (!cells || col >= cells.length) continue;
      var td = cells[col];
      var text = cellText(td);
      if (!text) continue;
      seen++;
      if (
        td.classList.contains("num") ||
        /^(-?[\d,]+(?:\.\d+)?)\s*%?$/.test(text) ||
        /^\d{4}-\d{2}-\d{2}$/.test(text)
      ) {
        numeric++;
      }
      if (seen >= 12) break;
    }
    return seen > 0 && numeric / seen >= 0.6;
  }

  function compare(a, b, dir) {
    if (a.empty && b.empty) return 0;
    if (a.empty) return 1;
    if (b.empty) return -1;
    var av = a.v;
    var bv = b.v;
    var cmp;
    if (a.type === "num" && b.type === "num") {
      cmp = av === bv ? 0 : av < bv ? -1 : 1;
    } else if (typeof av === "string" && typeof bv === "string") {
      cmp = av.localeCompare(bv, "ko");
    } else {
      cmp = av === bv ? 0 : String(av) < String(bv) ? -1 : 1;
    }
    return dir === "desc" ? -cmp : cmp;
  }

  function setIndicator(ths, active, dir) {
    for (var i = 0; i < ths.length; i++) {
      var th = ths[i];
      th.removeAttribute("aria-sort");
      th.classList.remove("is-sorted", "is-asc", "is-desc");
      var mark = th.querySelector(".sort-ind");
      if (mark) mark.textContent = "";
    }
    if (active == null) return;
    var thActive = ths[active];
    thActive.classList.add("is-sorted", dir === "asc" ? "is-asc" : "is-desc");
    thActive.setAttribute("aria-sort", dir === "asc" ? "ascending" : "descending");
    var ind = thActive.querySelector(".sort-ind");
    if (ind) ind.textContent = dir === "asc" ? "▲" : "▼";
  }

  function enhanceTable(table) {
    var thead = table.tHead;
    var tbody = table.tBodies[0];
    if (!thead || !tbody) return;
    var headerRow = thead.rows[0];
    if (!headerRow) return;
    var ths = headerRow.cells;
    if (!ths.length) return;

    table.classList.add("sortable");

    var state = { col: null, dir: "asc" };

    for (var i = 0; i < ths.length; i++) {
      (function (col) {
        var th = ths[col];
        th.classList.add("sortable-th");
        th.tabIndex = 0;
        th.setAttribute("role", "columnheader");
        th.setAttribute("aria-sort", "none");
        if (!th.querySelector(".sort-ind")) {
          var span = document.createElement("span");
          span.className = "sort-ind";
          span.setAttribute("aria-hidden", "true");
          th.appendChild(span);
        }

        function activate() {
          if (state.col === col) {
            state.dir = state.dir === "asc" ? "desc" : "asc";
          } else {
            state.col = col;
            state.dir = "asc";
          }
          sortBy(col, state.dir);
          setIndicator(ths, state.col, state.dir);
        }

        th.addEventListener("click", activate);
        th.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            activate();
          }
        });
      })(i);
    }

    function sortBy(col, dir) {
      var rows = Array.prototype.slice.call(tbody.rows);
      var preferNum = columnPrefersNum(rows, col);
      var decorated = rows.map(function (row, idx) {
        var cells = row.cells;
        var td = cells[col];
        var parsed = td ? parseCell(cellText(td), preferNum) : EMPTY;
        return { row: row, parsed: parsed, idx: idx };
      });
      decorated.sort(function (a, b) {
        var c = compare(a.parsed, b.parsed, dir);
        return c !== 0 ? c : a.idx - b.idx;
      });
      var frag = document.createDocumentFragment();
      for (var j = 0; j < decorated.length; j++) frag.appendChild(decorated[j].row);
      tbody.appendChild(frag);
    }
  }

  function init() {
    var tables = document.querySelectorAll(".tbl table");
    for (var i = 0; i < tables.length; i++) enhanceTable(tables[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
