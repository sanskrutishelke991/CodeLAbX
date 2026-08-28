(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function ringPath(cx, cy, base, w1, f1, p1, w2, f2, p2) {
    var pts = [];
    var a, t, r;
    for (a = 0; a <= 360; a += 4) {
      t = (a * Math.PI) / 180;
      r = base * (1 + w1 * Math.sin(f1 * t + p1) + w2 * Math.sin(f2 * t + p2));
      pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
    }
    var d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    var i, x1, y1, x2, y2;
    for (i = 1; i < pts.length - 1; i++) {
      x1 = pts[i][0]; y1 = pts[i][1]; x2 = pts[i + 1][0]; y2 = pts[i + 1][1];
      d += " Q" + x1.toFixed(1) + "," + y1.toFixed(1) + " " + ((x1 + x2) / 2).toFixed(1) + "," + ((y1 + y2) / 2).toFixed(1);
    }
    return d + "Z";
  }

  function peak(svg, x, y, r0, step, rings, style, seed, amberInner) {
    var i, p, p2, d;
    for (i = 0; i < rings; i++) {
      d = ringPath(x, y, r0 + i * step, 0.17, 3, 1.2 + seed, 0.07, 5, 2.6 + seed * 2);
      p = document.createElementNS(NS, "path");
      p.setAttribute("d", d);
      p.setAttribute("fill", "none");
      if (amberInner && i < 3) {
        p.setAttribute("stroke", style.amberInner);
        p.setAttribute("stroke-width", "1.3");
      } else {
        p.setAttribute("stroke", style.line);
        p.setAttribute("stroke-width", style.width);
      }
      if (style.emboss) p.setAttribute("transform", "translate(" + style.embossX + " " + style.embossY + ")");
      svg.appendChild(p);
      if (style.emboss) {
        p2 = document.createElementNS(NS, "path");
        p2.setAttribute("d", d);
        p2.setAttribute("fill", "none");
        p2.setAttribute("stroke", style.lineHi);
        p2.setAttribute("stroke-width", style.width);
        svg.appendChild(p2);
      }
    }
  }

  function dot(svg, x, y, r, color, glow) {
    var g, c;
    if (glow) {
      g = document.createElementNS(NS, "circle");
      g.setAttribute("cx", x); g.setAttribute("cy", y); g.setAttribute("r", r * 3.4);
      g.setAttribute("fill", color); g.setAttribute("opacity", "0.14");
      svg.appendChild(g);
    }
    c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", r);
    c.setAttribute("fill", color);
    svg.appendChild(c);
  }

  function build(id, mode) {
    var svg = document.getElementById(id);
    if (!svg) return;
    if (mode === "light") {
      var style = { line: "rgba(80,84,74,0.40)", width: "1.05", amberInner: "rgba(229,169,61,0.75)" };
      var defs = document.createElementNS(NS, "defs");
      var grad = document.createElementNS(NS, "radialGradient");
      grad.setAttribute("id", "basin");
      grad.setAttribute("cx", "0.5"); grad.setAttribute("cy", "0.5"); grad.setAttribute("r", "0.5");
      var s0 = document.createElementNS(NS, "stop"); s0.setAttribute("offset", "0"); s0.setAttribute("stop-color", "#E5A93D"); s0.setAttribute("stop-opacity", "0.42");
      var s1 = document.createElementNS(NS, "stop"); s1.setAttribute("offset", "0.7"); s1.setAttribute("stop-color", "#E5A93D"); s1.setAttribute("stop-opacity", "0.12");
      var s2 = document.createElementNS(NS, "stop"); s2.setAttribute("offset", "1"); s2.setAttribute("stop-color", "#E5A93D"); s2.setAttribute("stop-opacity", "0");
      grad.appendChild(s0); grad.appendChild(s1); grad.appendChild(s2);
      defs.appendChild(grad); svg.appendChild(defs);
      peak(svg, 108, 140, 24, 27, 8, style, 0.2);
      peak(svg, 524, 220, 22, 25, 7, style, 1.1);
      peak(svg, 150, 520, 26, 27, 8, style, 2.0);
      peak(svg, 486, 596, 24, 26, 7, style, 0.7);
      peak(svg, 96, 716, 18, 21, 6, style, 1.6);
      var e = document.createElementNS(NS, "ellipse");
      e.setAttribute("cx", "320"); e.setAttribute("cy", "336"); e.setAttribute("rx", "105"); e.setAttribute("ry", "82");
      e.setAttribute("fill", "url(#basin)"); svg.appendChild(e);
      peak(svg, 320, 336, 20, 20, 5, style, 0.4, true);
      [[150, 300], [120, 560], [520, 182], [300, 706], [434, 472]].forEach(function (xy) { dot(svg, xy[0], xy[1], 6, "#35C99A"); });
      dot(svg, 172, 384, 5.5, "#E5A93D");
      dot(svg, 320, 336, 8, "#E5A93D");
    } else {
      var dstyle = {
        line: "rgba(4,6,10,0.55)", lineHi: "rgba(236,232,222,0.16)", width: "1.2",
        emboss: true, embossX: 0.8, embossY: 1.1, amberInner: "rgba(229,169,61,0.30)"
      };
      peak(svg, 120, 150, 26, 29, 9, dstyle, 0.3);
      peak(svg, 520, 200, 24, 27, 8, dstyle, 1.2);
      peak(svg, 170, 540, 28, 29, 8, dstyle, 2.1);
      peak(svg, 470, 616, 26, 28, 8, dstyle, 0.8);
      peak(svg, 340, 330, 30, 32, 9, dstyle, 0.5);
      var route = document.createElementNS(NS, "polyline");
      route.setAttribute("points", "92,140 150,236 236,332 330,424 296,540 370,640");
      route.setAttribute("fill", "none");
      route.setAttribute("stroke", "rgba(53,201,154,0.28)");
      route.setAttribute("stroke-width", "1.4");
      route.setAttribute("stroke-linecap", "round");
      svg.appendChild(route);
      [[92, 140], [236, 332], [330, 424], [370, 640]].forEach(function (xy) { dot(svg, xy[0], xy[1], 4, "#E5A93D", true); });
      dot(svg, 150, 236, 3.5, "#35C99A", true);
      dot(svg, 296, 540, 3.5, "#35C99A", true);
      dot(svg, 500, 300, 3, "rgba(165,172,184,0.8)");
    }
  }

  build("topo-light", "light");
  build("topo-dark", "dark");

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
