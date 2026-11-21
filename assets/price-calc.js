/* 협상계약 가격점수 = 배점 × 최저 투찰가 ÷ 해당 투찰가 (상한=배점). B-12: 배점 가변. B-23: 천단위 쉼표. */
(function () {
  "use strict";

  var low = document.getElementById("calc-low");
  var ours = document.getElementById("calc-ours");
  var rival = document.getElementById("calc-rival");
  var maxEl = document.getElementById("calc-max");
  var out = document.getElementById("calc-out");
  if (!low || !ours || !out) return;

  function num(v) {
    // Strip thousands commas so "1,234" → 1234 (not 1.234).
    return parseFloat(String(v == null ? "" : v).replace(/,/g, ""));
  }

  function maxPts() {
    var m = maxEl ? num(maxEl.value) : 10;
    return Number.isFinite(m) && m > 0 ? m : 10;
  }

  function score(lowAmt, bid, cap) {
    if (!(bid > 0)) return NaN;
    return Math.min(cap, (cap * lowAmt) / bid);
  }

  function run() {
    var a = num(low.value);
    var b = num(ours.value);
    var r = rival ? num(rival.value) : NaN;
    var cap = maxPts();
    if (!(a > 0) || !(b > 0)) {
      out.textContent =
        "최저 투찰가와 해당 투찰가를 입력하세요. 가격점수 = 배점 × 최저투찰가 ÷ 해당투찰가.";
      return;
    }
    var oursScore = score(a, b, cap);
    var text =
      "가격점수 " +
      oursScore.toFixed(3) +
      "점 (상한 " +
      cap +
      "점).";
    if (b < a) {
      text += " 투찰가가 최저보다 낮습니다(비정상 입력).";
    }
    if (r > 0) {
      var rivalScore = score(a, r, cap);
      var diff = oursScore - rivalScore;
      text +=
        " 경쟁사 과거 투찰 " +
        r +
        "억이면 " +
        rivalScore.toFixed(3) +
        "점 · 차이 " +
        (diff >= 0 ? "+" : "") +
        diff.toFixed(3) +
        "점.";
    }
    out.textContent = text;
  }

  low.addEventListener("input", run);
  ours.addEventListener("input", run);
  if (rival) rival.addEventListener("input", run);
  if (maxEl) maxEl.addEventListener("input", run);
  run();
})();
