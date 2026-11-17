/* 협상계약 가격점수 = 10 × 최저 투찰가 ÷ 해당 투찰가, 상한 10점. */
(function () {
  "use strict";

  var low = document.getElementById("calc-low");
  var ours = document.getElementById("calc-ours");
  var rival = document.getElementById("calc-rival");
  var out = document.getElementById("calc-out");
  if (!low || !ours || !out) return;

  function score(lowAmt, bid) {
    return Math.min(10, (10 * lowAmt) / bid);
  }

  function run() {
    var a = parseFloat(low.value);
    var b = parseFloat(ours.value);
    var r = rival ? parseFloat(rival.value) : NaN;
    if (!(a > 0) || !(b > 0)) {
      out.textContent =
        "최저 투찰가와 해당 투찰가를 입력하세요. 가격점수 = 10 × 최저투찰가 ÷ 해당투찰가.";
      return;
    }
    var oursScore = score(a, b);
    var text = "가격점수 " + oursScore.toFixed(3) + "점 (상한 10점).";
    if (r > 0) {
      var rivalScore = score(a, r);
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
})();
