(function () {
  "use strict";
  var root = document.documentElement;
  var back = document.getElementById("dial-back");
  var closeBtn = document.getElementById("dial-close");
  var openDialBtn = document.getElementById("open-dial");
  var tog = document.getElementById("theme-toggle");
  var dock = document.getElementById("dock");
  var kicker = document.getElementById("day-kicker");
  var heading = document.getElementById("day-h");
  var lede = document.getElementById("day-lede");
  var cont = document.getElementById("continue");
  var rows = document.querySelectorAll(".path-row");

  function theme(t) {
    root.setAttribute("data-theme", t);
    if (tog) {
      tog.setAttribute(
        "aria-label",
        t === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
    }
    try { localStorage.setItem("codelabx-v2-theme", t); } catch (e) {}
  }
  if (tog) {
    tog.addEventListener("click", function () {
      theme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  }
  var start = "light";
  try { start = localStorage.getItem("codelabx-v2-theme") || start; } catch (e) {}
  theme(start === "dark" ? "dark" : "light");

  function selectPath(row) {
    if (!row) return;
    rows.forEach(function (r) {
      r.classList.toggle("on", r === row);
      r.setAttribute("aria-current", r === row ? "true" : "false");
    });
    if (kicker) kicker.textContent = row.getAttribute("data-kicker") || "";
    var day = row.getAttribute("data-day") || "";
    if (heading) heading.textContent = day ? "Day " + day : heading.textContent;
    if (lede) lede.textContent = row.getAttribute("data-title") || "";
    if (cont) {
      var href = row.getAttribute("data-href");
      if (href) cont.setAttribute("href", href);
    }
    try { sessionStorage.setItem("codelabx-v2-path", row.getAttribute("data-id") || ""); } catch (e) {}
  }
  rows.forEach(function (row) {
    row.addEventListener("click", function () { selectPath(row); });
  });
  try {
    var saved = sessionStorage.getItem("codelabx-v2-path");
    if (saved) {
      rows.forEach(function (row) {
        if (row.getAttribute("data-id") === saved) selectPath(row);
      });
    }
  } catch (e) {}

  function openDial() {
    if (!back) return;
    back.hidden = false;
    if (closeBtn) closeBtn.focus();
  }
  function closeDial() {
    if (!back) return;
    back.hidden = true;
    if (openDialBtn) openDialBtn.focus();
  }
  if (openDialBtn) openDialBtn.addEventListener("click", openDial);
  if (closeBtn) closeBtn.addEventListener("click", closeDial);
  if (back) {
    back.addEventListener("mousedown", function (e) {
      if (e.target === back) closeDial();
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDial();
  });

  function reduceMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function isMobile() {
    return window.matchMedia("(max-width: 880px)").matches;
  }
  function resetDock() {
    if (!dock) return;
    var icons = dock.querySelectorAll(".dock-i");
    for (var i = 0; i < icons.length; i++) icons[i].style.setProperty("--s", "1");
  }
  function magnify(ev) {
    if (!dock || reduceMotion() || isMobile()) return;
    var icons = dock.querySelectorAll(".dock-i");
    for (var i = 0; i < icons.length; i++) {
      var icon = icons[i];
      if (!icon.getClientRects().length) continue;
      var rect = icon.getBoundingClientRect();
      var dist = Math.abs(ev.clientX - (rect.left + rect.width / 2));
      var t = Math.min(1, dist / 110);
      var scale = t === 1 ? 1 : 1 + 0.72 * Math.cos(t * Math.PI / 2);
      icon.style.setProperty("--s", String(scale));
    }
  }
  if (dock) {
    dock.addEventListener("mousemove", magnify);
    dock.addEventListener("mouseleave", resetDock);
  }
  window.addEventListener("resize", function () {
    if (isMobile() || reduceMotion()) resetDock();
  });
})();
