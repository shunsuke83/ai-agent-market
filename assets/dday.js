/* Recalculate D-day badges from data-close using the visitor's local date (B-09 / N-07). */
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

  /** N-07: collapse/expand 임박 rows from the visitor's date, not render-time. */
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

  function refresh() {
    document.querySelectorAll(".dday[data-close]").forEach(paint);
    document.querySelectorAll("tr.dday-collapse, table.home-list tbody tr").forEach(function (tr) {
      if (tr.querySelector(".dday[data-close]")) syncCollapse(tr);
    });
  }

  refresh();
})();
