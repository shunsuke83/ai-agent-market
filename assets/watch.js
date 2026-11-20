/* Shared 관심 list. Stays in this browser until the person copies a link. */
(function () {
  "use strict";

  var KEY = "aam-watch";

  function load() {
    // N-12: only plain objects; strings/numbers/arrays used to throw on detail toggle.
    try {
      var raw = JSON.parse(window.localStorage.getItem(KEY) || "{}");
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
      return raw;
    } catch (e) {
      return {};
    }
  }

  function save(w) {
    try {
      if (!w || typeof w !== "object" || Array.isArray(w)) return;
      window.localStorage.setItem(KEY, JSON.stringify(w));
    } catch (e) {}
  }

  function siteRoot() {
    var path = window.location.pathname;
    var cut = path.search(/\/(bids|reports)\//);
    if (cut >= 0) return path.slice(0, cut + 1);
    return path.replace(/[^/]*$/, "");
  }

  /** B-07: allow bids/*.html and list-page keys (bid nos, #anchors), not only *.html. */
  function safe(key) {
    key = String(key || "").replace(/^(\.\.\/)+/, "").trim();
    if (!key || key.indexOf("..") >= 0) return "";
    if (!/^[A-Za-z0-9][A-Za-z0-9_./#%+-]*$/.test(key)) return "";
    return key;
  }

  function shareUrl() {
    var keys = Object.keys(load()).map(safe).filter(Boolean);
    if (!keys.length) return "";
    return (
      window.location.origin +
      siteRoot() +
      "index.html#watch=" +
      encodeURIComponent(keys.join("|"))
    );
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
    var added = 0;
    raw.split("|").forEach(function (key) {
      key = safe(key);
      if (!key) return;
      if (!watch[key]) added++;
      watch[key] = watch[key] || 1;
    });
    save(watch);
    if (window.history && history.replaceState) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    if (!added && !Object.keys(watch).length) return;
    var note = document.createElement("p");
    note.className = "note";
    note.setAttribute("data-watch-shared", "1");
    note.textContent =
      "공유된 관심 " + Object.keys(watch).length + "건을 이 브라우저에 저장했습니다.";
    var old = document.querySelector("[data-watch-shared]");
    if (old) old.remove();
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
          navigator.clipboard.writeText(text).then(
            function () {
              memo.textContent = "메모 복사됨";
            },
            function () {
              memo.textContent = "복사 실패";
            }
          );
        } else {
          memo.textContent = "복사 불가";
        }
      });
    }
    var copy = document.getElementById("copy-link");
    if (!copy) return;
    copy.addEventListener("click", function () {
      var url = window.location.href.split("#")[0];
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(
          function () {
            copy.textContent = "링크 복사됨";
          },
          function () {
            copy.textContent = "복사 실패";
          }
        );
      } else {
        copy.textContent = "복사 불가";
      }
    });
  }

  window.aamWatch = { load: load, save: save, shareUrl: shareUrl, safe: safe };
  takeShared();
  // B-08: same-tab share links and back/forward.
  window.addEventListener("hashchange", takeShared);
  bindDetail();
})();
