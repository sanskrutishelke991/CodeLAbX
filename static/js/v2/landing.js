(function () {
  "use strict";
  var svg = document.getElementById("topo");
  var NS = "http://www.w3.org/2000/svg";
  var tl = document.getElementById("tl");
  var td = document.getElementById("td");
  if (!svg || !tl || !td) return;

  function ringPath(cx, cy, base, w1, f1, p1, w2, f2, p2) {
    var pts = [];
    var a, t, r;
    for (a = 0; a <= 360; a += 5) {
      t = (a * Math.PI) / 180;
      r = base * (1 + w1 * Math.sin(f1 * t + p1) + w2 * Math.sin(f2 * t + p2));
      pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
    }
    var d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    var i, x1, y1, x2, y2;
    for (i = 1; i < pts.length - 1; i++) {
      x1 = pts[i][0];
      y1 = pts[i][1];
      x2 = pts[i + 1][0];
      y2 = pts[i + 1][1];
      d += " Q" + x1.toFixed(1) + "," + y1.toFixed(1) + " " + ((x1 + x2) / 2).toFixed(1) + "," + ((y1 + y2) / 2).toFixed(1);
    }
    return d + "Z";
  }

  function peak(x, y, r0, step, rings, seed, stroke) {
    var i, p;
    for (i = 0; i < rings; i++) {
      p = document.createElementNS(NS, "path");
      p.setAttribute("d", ringPath(x, y, r0 + i * step, 0.16, 3, 1.1 + seed, 0.06, 5, 2.4 + seed * 2));
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", stroke);
      p.setAttribute("stroke-width", "1.05");
      svg.appendChild(p);
    }
  }

  function paint() {
    while (svg.lastChild) svg.removeChild(svg.lastChild);
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    var stroke = dark ? "rgba(236,232,222,0.10)" : "rgba(80,84,74,0.28)";
    peak(180, 160, 28, 32, 9, 0.2, stroke);
    peak(720, 220, 24, 30, 8, 1.1, stroke);
    peak(1180, 140, 26, 28, 8, 0.7, stroke);
    peak(320, 520, 30, 34, 9, 2.0, stroke);
    peak(980, 560, 28, 32, 8, 0.4, stroke);
    peak(60, 780, 22, 26, 7, 1.6, stroke);
    peak(1320, 720, 20, 24, 6, 0.9, stroke);
  }

  function setTheme(t) {
    if (t === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    tl.setAttribute("aria-pressed", t === "light" ? "true" : "false");
    td.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    try { localStorage.setItem("codelabx-v2-theme", t); } catch (e) {}
    paint();
  }

  tl.addEventListener("click", function () { setTheme("light"); });
  td.addEventListener("click", function () { setTheme("dark"); });
  var start = "light";
  try { start = localStorage.getItem("codelabx-v2-theme") || start; } catch (e) {}
  if (start === "dark") setTheme("dark");
  else paint();
})();
