(function () {
  "use strict";
  var root = document.documentElement;
  var back = document.getElementById("dial-back");
  var closeBtn = document.getElementById("dial-close");
  var openDialBtn = document.getElementById("open-dial");
  var tog = document.getElementById("theme-toggle");
  var dock = document.getElementById("dock");
  var wheel = document.getElementById("wheel");
  var kicker = document.getElementById("day-kicker");
  var heading = document.getElementById("day-h");
  var lede = document.getElementById("day-lede");
  var cont = document.getElementById("continue");
  var rows = document.querySelectorAll(".path-row");
  var wedges = wheel ? wheel.querySelectorAll(".wedge") : [];
  var slices = wheel ? wheel.querySelectorAll(".slice") : [];
  var listLinks = document.querySelectorAll("#dlist a");
  var selected = 0;

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

  function setSel(i, rot) {
    selected = ((i % 8) + 8) % 8;
    var n;
    for (n = 0; n < wedges.length; n++) {
      wedges[n].classList.toggle("on", Number(wedges[n].getAttribute("data-i")) === selected);
    }
    for (n = 0; n < slices.length; n++) {
      var on = Number(slices[n].getAttribute("data-i")) === selected;
      slices[n].classList.toggle("on", on);
      if (on) slices[n].setAttribute("aria-current", "true");
      else slices[n].removeAttribute("aria-current");
    }
    for (n = 0; n < listLinks.length; n++) {
      listLinks[n].classList.toggle("on", Number(listLinks[n].getAttribute("data-i")) === selected);
    }
    if (wheel) {
      var deg = rot == null ? selected * 45 + 22.5 : rot;
      wheel.style.setProperty("--rot", deg + "deg");
    }
  }

  function pointerAngle(ev) {
    if (!wheel) return null;
    var rect = wheel.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var dx = ev.clientX - cx;
    var dy = ev.clientY - cy;
    var dist = Math.sqrt(dx * dx + dy * dy);
    var r = rect.width / 2;
    if (dist < r * 0.2 || dist > r * 1.02) return null;
    var ang = Math.atan2(dx, -dy) * (180 / Math.PI);
    if (ang < 0) ang += 360;
    return ang;
  }

  function goSelected() {
    var a = null;
    for (var n = 0; n < slices.length; n++) {
      if (Number(slices[n].getAttribute("data-i")) === selected) {
        a = slices[n];
        break;
      }
    }
    if (a && a.href) window.location.assign(a.href);
  }

  function openDial() {
    if (!back) return;
    back.hidden = false;
    setSel(selected);
    if (wheel) wheel.focus();
  }
  function closeDial() {
    if (!back) return;
    back.hidden = true;
    if (openDialBtn) openDialBtn.focus();
  }
  function dialOpen() {
    return back && !back.hidden;
  }
  if (openDialBtn) openDialBtn.addEventListener("click", openDial);
  if (closeBtn) closeBtn.addEventListener("click", closeDial);
  if (back) {
    back.addEventListener("mousedown", function (e) {
      if (e.target === back) closeDial();
    });
  }
  var skipClick = false;
  var touchMoved = false;

  function tracePoint(pt) {
    if (!pt) return null;
    var ang = pointerAngle(pt);
    if (ang == null) return null;
    setSel(Math.floor(ang / 45) % 8, ang);
    return ang;
  }

  if (wheel) {
    wheel.addEventListener("mousemove", function (e) {
      if (!dialOpen()) return;
      tracePoint(e);
    });
    wheel.addEventListener("click", function (e) {
      if (!dialOpen()) return;
      if (skipClick) {
        skipClick = false;
        return;
      }
      if (tracePoint(e) == null) return;
      goSelected();
    });
    wheel.addEventListener("touchstart", function (e) {
      if (!dialOpen()) return;
      touchMoved = false;
      skipClick = true;
      var t = e.touches[0];
      if (t) tracePoint(t);
    }, { passive: true });
    wheel.addEventListener("touchmove", function (e) {
      if (!dialOpen()) return;
      if (e.cancelable) e.preventDefault();
      touchMoved = true;
      var t = e.touches[0];
      if (t) tracePoint(t);
    }, { passive: false });
    wheel.addEventListener("touchend", function (e) {
      if (!dialOpen()) return;
      var t = e.changedTouches[0];
      if (t) tracePoint(t);
      if (!touchMoved) goSelected();
    });
  }
  for (var li = 0; li < listLinks.length; li++) {
    (function (link) {
      link.addEventListener("mouseenter", function () {
        if (!dialOpen()) return;
        var i = Number(link.getAttribute("data-i"));
        if (!isNaN(i)) setSel(i);
      });
    })(listLinks[li]);
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeDial();
      return;
    }
    if (!dialOpen()) return;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") {
      e.preventDefault();
      setSel(selected + 1);
    } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
      e.preventDefault();
      setSel(selected - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      goSelected();
    }
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
