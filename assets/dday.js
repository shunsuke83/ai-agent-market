/* Recalculate D-day badges from data-close using the visitor's local date (B-09 / N-07).
   Collapse only applies inside table.closing-soon (T-03); label count updates live (T-08). */
(function () {
  "use strict";

  var URGENT = 3;

  function daysUntil(close) {
    var day = (close || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
    var end = new Date(day + "T00:00:00");
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((end - today) / 86400000);
  }

  function paint(el) {
    var days = daysUntil(el.getAttribute("data-close") || "");
    if (days == null) return;
    if (days < 0) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    var label = days === 0 ? "D-day" : "D-" + days;
    el.textContent = days <= URGENT ? label + " 임박" : label;
    el.classList.toggle("urgent", days <= URGENT);
  }

  /** T-03: only rows in the 마감 임박 table are collapsible. */
  function syncCollapse(tr) {
    var badge = tr.querySelector(".dday[data-close]");
    if (!badge) return;
    var days = daysUntil(badge.getAttribute("data-close") || "");
    if (days == null || days < 0) {
      tr.classList.remove("dday-collapse");
      return;
    }
    tr.classList.toggle("dday-collapse", days <= URGENT);
  }

  function updateUrgentLabel() {
    var label = document.getElementById("urgent-label");
    if (!label) return;
    var n = document.querySelectorAll("table.closing-soon tbody tr.dday-collapse").length;
    label.textContent = "D-" + URGENT + " 이하 " + n + "건도 펼치기";
  }

  function refresh() {
    document.querySelectorAll(".dday[data-close]").forEach(paint);
    document.querySelectorAll("table.closing-soon tbody tr").forEach(function (tr) {
      if (tr.querySelector(".dday[data-close]")) syncCollapse(tr);
    });
    updateUrgentLabel();
  }

  refresh();
})();
