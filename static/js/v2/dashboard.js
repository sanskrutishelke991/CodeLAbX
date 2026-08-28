(function () {
  "use strict";
  var root = document.documentElement;
  var back = document.getElementById("dial-back");
  var closeBtn = document.getElementById("dial-close");
  var openers = [document.getElementById("open-dial"), document.getElementById("tab-dial")];
  var tl = document.getElementById("tl");
  var td = document.getElementById("td");

  function theme(t) {
    root.setAttribute("data-theme", t);
    if (tl) tl.setAttribute("aria-pressed", t === "light" ? "true" : "false");
    if (td) td.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    try { localStorage.setItem("codelabx-v2-theme", t); } catch (e) {}
  }
  if (tl) tl.addEventListener("click", function () { theme("light"); });
  if (td) td.addEventListener("click", function () { theme("dark"); });
  var start = "light";
  try { start = localStorage.getItem("codelabx-v2-theme") || start; } catch (e) {}
  theme(start === "dark" ? "dark" : "light");

  function openDial() {
    if (!back) return;
    back.hidden = false;
    if (closeBtn) closeBtn.focus();
  }
  function closeDial() {
    if (!back) return;
    back.hidden = true;
  }
  openers.forEach(function (el) {
    if (el) el.addEventListener("click", openDial);
  });
  if (closeBtn) closeBtn.addEventListener("click", closeDial);
  if (back) {
    back.addEventListener("mousedown", function (e) {
      if (e.target === back) closeDial();
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDial();
  });
})();
