(function () {
  "use strict";
  var root = document.documentElement;
  var tl = document.getElementById("tl");
  var td = document.getElementById("td");
  if (!tl || !td) return;

  function setTheme(t) {
    root.setAttribute("data-theme", t);
    tl.setAttribute("aria-pressed", t === "light" ? "true" : "false");
    td.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    try { localStorage.setItem("codelabx-v2-theme", t); } catch (err) {}
  }

  tl.addEventListener("click", function () { setTheme("light"); });
  td.addEventListener("click", function () { setTheme("dark"); });
  var start = "light";
  try { start = localStorage.getItem("codelabx-v2-theme") || start; } catch (err) {}
  setTheme(start === "dark" ? "dark" : "light");
})();
