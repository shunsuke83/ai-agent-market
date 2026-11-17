/* Shared 관심 list. Stays in this browser until the person copies a link. */
(function () {
  "use strict";

  var KEY = "aam-watch";

  function load() {
    try {
      return JSON.parse(window.localStorage.getItem(KEY) || "{}") || {};
    } catch (e) {
      return {};
    }
  }

  function save(w) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(w));
    } catch (e) {}
  }

  function siteRoot() {
    var path = window.location.pathname;
    var cut = path.search(/\/(bids|reports)\//);
    if (cut >= 0) return path.slice(0, cut + 1);
    return path.replace(/[^/]*$/, "");
  }

  function safe(key) {
    key = String(key || "").replace(/^(\.\.\/)+/, "");
    if (key.indexOf("..") >= 0 || !/^[A-Za-z0-9_./-]+\.html$/.test(key)) return "";
    return key;
  }

  function shareUrl() {
    var keys = Object.keys(load()).map(safe).filter(Boolean);
    return window.location.origin + siteRoot() + "index.html#watch=" + encodeURIComponent(keys.join("|"));
  }

  function takeShared() {
    if (window.location.hash.indexOf("#watch=") !== 0) return;
    var raw = "";
    try {
      raw = decodeURIComponent(window.location.hash.slice(7));
    } catch (e) {
      raw = "";
    }
    var watch = load();
    raw.split("|").forEach(function (key) {
      key = safe(key);
      if (key) watch[key] = 1;
    });
    save(watch);
    if (window.history && history.replaceState) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    var note = document.createElement("p");
    note.className = "note";
    note.textContent = "공유된 관심 " + Object.keys(watch).length + "건을 이 브라우저에 저장했습니다.";
    var main = document.querySelector("main") || document.querySelector(".wrap");
    if (main) main.insertBefore(note, main.firstChild);
  }

  function bindDetail() {
    var toggle = document.getElementById("watch-toggle");
    if (!toggle) return;
    var key = safe(toggle.getAttribute("data-key"));
    if (!key) return;

    function paint() {
      var on = !!load()[key];
      toggle.textContent = on ? "관심 해제" : "관심 등록";
      toggle.setAttribute("aria-pressed", on ? "true" : "false");
    }

    paint();
    toggle.addEventListener("click", function () {
      var watch = load();
      if (watch[key]) delete watch[key];
      else watch[key] = 1;
      save(watch);
      paint();
    });
    var memo = document.getElementById("proposal-copy");
    var pre = document.getElementById("proposal-md");
    if (memo && pre) {
      memo.addEventListener("click", function () {
        var text = pre.textContent || "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            memo.textContent = "메모 복사됨";
          });
        }
      });
    }
    var copy = document.getElementById("copy-link");
    if (!copy) return;
    copy.addEventListener("click", function () {
      var url = window.location.href.split("#")[0];
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () {
          copy.textContent = "링크 복사됨";
        });
      }
    });
  }

  window.aamWatch = { load: load, save: save, shareUrl: shareUrl, safe: safe };
  takeShared();
  bindDetail();
})();
