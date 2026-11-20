/* Recalculate D-day badges from data-close using the visitor's local date (B-09). */
(function () {
  "use strict";

  var URGENT = 3;

  function paint(el) {
    var close = el.getAttribute("data-close") || "";
    var day = close.slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return;
    var end = new Date(day + "T00:00:00");
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var days = Math.round((end - today) / 86400000);
    if (days < 0) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    var label = days === 0 ? "D-day" : "D-" + days;
    el.textContent = days <= URGENT ? label + " 임박" : label;
    el.classList.toggle("urgent", days <= URGENT);
  }

  function refresh() {
    document.querySelectorAll(".dday[data-close]").forEach(paint);
  }

  refresh();
})();
