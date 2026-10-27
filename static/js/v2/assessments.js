(function () {
  "use strict";

  function csrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    if (el && el.value) return el.value;
    var cookies = document.cookie ? document.cookie.split(";") : [];
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.indexOf("csrftoken=") === 0) return decodeURIComponent(c.slice(10));
    }
    return "";
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json"
      },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().then(function (data) {
        data._ok = res.ok;
        return data;
      });
    });
  }

  function markOn(nodes, attr, value) {
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].classList.toggle("on", nodes[i].getAttribute(attr) === value);
    }
  }

  function reducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  var pctEl = document.querySelector(".hero-pct");
  if (pctEl) {
    var target = parseFloat(pctEl.getAttribute("data-pct"));
    var bar = document.querySelector(".as-bar > i");
    if (bar) {
      var fill = parseFloat(bar.getAttribute("data-p"));
      if (!isNaN(fill)) bar.style.width = fill + "%";
    }
    if (!isNaN(target) && !reducedMotion()) {
      pctEl.textContent = "0%";
      var t0 = window.performance.now();
      var dur = 720;
      function tick(now) {
        var p = Math.min(1, (now - t0) / dur);
        var eased = 1 - Math.pow(1 - p, 3);
        var val = target * eased;
        pctEl.textContent = (Math.round(val * 10) / 10) + "%";
        if (p < 1) window.requestAnimationFrame(tick);
        else pctEl.textContent = target + "%";
      }
      window.requestAnimationFrame(tick);
    }
  }

  var form = document.getElementById("make-test");
  if (form) {
    var topic = document.getElementById("topic");
    var statusEl = document.getElementById("gen-status");
    var genBtn = document.getElementById("gen-test");
    var difficulty = "medium";
    var numQ = 10;
    var mins = 10;
    var chips = document.getElementById("topic-chips");
    var diffs = document.getElementById("diff-picks");
    var ns = document.getElementById("n-picks");
    var ts = document.getElementById("t-picks");

    if (chips) {
      chips.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-topic]");
        if (!btn) return;
        topic.value = btn.getAttribute("data-topic");
        markOn(chips.querySelectorAll("[data-topic]"), "data-topic", topic.value);
        topic.focus();
      });
    }
    if (diffs) {
      diffs.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-diff]");
        if (!btn) return;
        difficulty = btn.getAttribute("data-diff");
        markOn(diffs.querySelectorAll("[data-diff]"), "data-diff", difficulty);
      });
    }
    if (ns) {
      ns.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-n]");
        if (!btn) return;
        numQ = parseInt(btn.getAttribute("data-n"), 10);
        markOn(ns.querySelectorAll("[data-n]"), "data-n", String(numQ));
      });
    }
    if (ts) {
      ts.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-t]");
        if (!btn) return;
        mins = parseInt(btn.getAttribute("data-t"), 10);
        markOn(ts.querySelectorAll("[data-t]"), "data-t", String(mins));
      });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var t = (topic.value || "").trim();
      if (!t) {
        statusEl.textContent = "Name a topic.";
        topic.focus();
        return;
      }
      genBtn.disabled = true;
      statusEl.textContent = "Generating…";
      postJson("/assessments/api/generate/", {
        topic: t,
        difficulty: difficulty,
        num_questions: numQ,
        time_limit: mins
      })
        .then(function (data) {
          if (data && data.success && data.test_id) {
            window.location.href = "/assessments/take/" + data.test_id + "/";
            return;
          }
          statusEl.textContent = (data && data.error) || "Could not generate.";
          genBtn.disabled = false;
        })
        .catch(function () {
          statusEl.textContent = "Could not reach the generator.";
          genBtn.disabled = false;
        });
    });
  }

  var exam = document.getElementById("exam");
  if (!exam) return;

  var raw = document.getElementById("quiz-json");
  var questions = [];
  try {
    questions = raw ? JSON.parse(raw.textContent) : [];
  } catch (err) {
    questions = [];
  }
  if (!questions.length) return;

  var testId = exam.getAttribute("data-id");
  var limit = parseInt(exam.getAttribute("data-mins"), 10) || 10;
  var remaining = limit * 60;
  var current = 0;
  var answers = {};
  var storeKey = "test_" + testId + "_answers";
  var sending = false;

  try {
    var saved = window.localStorage.getItem(storeKey);
    if (saved) answers = JSON.parse(saved) || {};
  } catch (err2) {
    answers = {};
  }

  var qText = document.getElementById("q-text");
  var opts = document.getElementById("opts");
  var kicker = document.getElementById("q-kicker");
  var timerEl = document.getElementById("timer");
  var hair = document.getElementById("q-hair");
  var answeredEl = document.getElementById("answered");
  var dots = document.getElementById("dots");
  var prevBtn = document.getElementById("prev-q");
  var nextBtn = document.getElementById("next-q");
  var submitBtn = document.getElementById("submit-q");
  var saveBtn = document.getElementById("save-q");

  function answeredCount() {
    var n = 0;
    for (var i = 0; i < questions.length; i++) {
      if (answers[String(i)] !== undefined && answers[String(i)] !== null) n += 1;
    }
    return n;
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function paintTimer() {
    var m = Math.floor(remaining / 60);
    var s = remaining % 60;
    timerEl.textContent = m + ":" + pad(s);
    timerEl.classList.toggle("warn", remaining <= 60);
  }

  function paintDots() {
    dots.textContent = "";
    for (var i = 0; i < questions.length; i++) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "dot";
      if (answers[String(i)] !== undefined && answers[String(i)] !== null) b.classList.add("on");
      if (i === current) b.classList.add("now");
      b.setAttribute("data-i", String(i));
      b.setAttribute("aria-label", "Question " + (i + 1));
      b.textContent = String(i + 1);
      dots.appendChild(b);
    }
  }

  function paint() {
    var q = questions[current] || {};
    qText.textContent = q.question || "";
    kicker.textContent = "Question " + (current + 1) + " of " + questions.length;
    opts.textContent = "";
    var list = q.options || [];
    var chosen = answers[String(current)];
    for (var i = 0; i < list.length; i++) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "opt" + (chosen === i ? " on" : "");
      btn.setAttribute("data-i", String(i));
      var em = document.createElement("em");
      em.textContent = String.fromCharCode(65 + i);
      btn.appendChild(em);
      btn.appendChild(document.createTextNode(" " + list[i]));
      opts.appendChild(btn);
    }
    prevBtn.disabled = current === 0;
    var last = current === questions.length - 1;
    nextBtn.hidden = last;
    submitBtn.hidden = !last;
    if (hair) hair.style.width = Math.round(((current + 1) / questions.length) * 100) + "%";
    answeredEl.textContent = "Answered " + answeredCount() + " of " + questions.length;
    paintDots();
  }

  function persist() {
    try {
      window.localStorage.setItem(storeKey, JSON.stringify(answers));
    } catch (err3) {}
  }

  function selectOpt(i) {
    answers[String(current)] = i;
    persist();
    paint();
  }

  function go(i) {
    if (i < 0 || i >= questions.length) return;
    current = i;
    paint();
  }

  function submitPaper(force) {
    if (sending) return;
    var n = answeredCount();
    if (!force) {
      var msg = "Submit this paper? You answered " + n + " of " + questions.length + ".";
      if (!window.confirm(msg)) return;
    }
    sending = true;
    var taken = Math.max(0, limit * 60 - remaining);
    postJson("/assessments/api/submit/" + testId + "/", {
      answers: answers,
      time_taken: taken
    })
      .then(function (data) {
        if (data && data.success) {
          try {
            window.localStorage.removeItem(storeKey);
          } catch (err4) {}
          window.location.href = "/assessments/result/" + testId + "/";
          return;
        }
        sending = false;
        window.alert((data && data.error) || "Could not submit.");
      })
      .catch(function () {
        sending = false;
        window.alert("Could not submit.");
      });
  }

  opts.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-i]");
    if (!btn) return;
    selectOpt(parseInt(btn.getAttribute("data-i"), 10));
  });
  dots.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-i]");
    if (!btn) return;
    go(parseInt(btn.getAttribute("data-i"), 10));
  });
  prevBtn.addEventListener("click", function () { go(current - 1); });
  nextBtn.addEventListener("click", function () { go(current + 1); });
  submitBtn.addEventListener("click", function () { submitPaper(false); });
  if (saveBtn) {
    saveBtn.addEventListener("click", function () {
      persist();
      saveBtn.textContent = "Saved";
      window.setTimeout(function () { saveBtn.textContent = "Save progress"; }, 1200);
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    var k = e.key;
    if (k === "ArrowLeft") go(current - 1);
    else if (k === "ArrowRight") go(current + 1);
    else if (k === "1" || k === "a" || k === "A") selectOpt(0);
    else if (k === "2" || k === "b" || k === "B") selectOpt(1);
    else if (k === "3" || k === "c" || k === "C") selectOpt(2);
    else if (k === "4" || k === "d" || k === "D") selectOpt(3);
  });

  paintTimer();
  paint();
  window.setInterval(function () {
    if (sending) return;
    remaining -= 1;
    if (remaining <= 0) {
      remaining = 0;
      paintTimer();
      submitPaper(true);
      return;
    }
    paintTimer();
  }, 1000);
})();
