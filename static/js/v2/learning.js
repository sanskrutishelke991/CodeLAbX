(function () {
  "use strict";

  var hairs = document.querySelectorAll(".hair > i[data-p]");
  for (var h = 0; h < hairs.length; h++) {
    var pct = Number(hairs[h].getAttribute("data-p") || "0");
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    hairs[h].style.width = pct + "%";
  }

  var topicInput = document.getElementById("id_topic");
  var topicBtns = document.querySelectorAll(".topic[data-topic]");
  function pickTopic(code) {
    if (topicInput) topicInput.value = code;
    for (var i = 0; i < topicBtns.length; i++) {
      topicBtns[i].classList.toggle("on", topicBtns[i].getAttribute("data-topic") === code);
    }
  }
  for (var t = 0; t < topicBtns.length; t++) {
    (function (btn) {
      btn.addEventListener("click", function () {
        pickTopic(btn.getAttribute("data-topic"));
      });
    })(topicBtns[t]);
  }
  var form = document.getElementById("create-path");
  if (form) {
    form.addEventListener("submit", function (e) {
      if (topicInput && !topicInput.value) {
        e.preventDefault();
        pickTopic("ML");
        form.submit();
      }
    });
  }

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

  var panel = document.getElementById("theory-panel");
  if (!panel) return;
  var rm = panel.getAttribute("data-roadmap");
  var day = panel.getAttribute("data-day");
  var statusEl = document.getElementById("theory-status");

  function setStatus(text, show) {
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.hidden = !show;
  }

  function generate() {
    setStatus("Preparing theory…", true);
    var gen = document.getElementById("gen-btn");
    var regen = document.getElementById("regen-btn");
    if (gen) gen.disabled = true;
    if (regen) regen.disabled = true;
    fetch("/learning/roadmaps/" + rm + "/day/" + day + "/generate/", {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "Content-Type": "application/json",
        Accept: "application/json"
      }
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (pack) {
        if (pack.ok && pack.data && pack.data.success) {
          window.location.reload();
          return;
        }
        setStatus((pack.data && pack.data.error) || "Could not generate theory.", true);
        if (gen) gen.disabled = false;
        if (regen) regen.disabled = false;
      })
      .catch(function () {
        setStatus("Could not generate theory.", true);
        if (gen) gen.disabled = false;
        if (regen) regen.disabled = false;
      });
  }

  var genBtn = document.getElementById("gen-btn");
  if (genBtn) genBtn.addEventListener("click", generate);
  var regenBtn = document.getElementById("regen-btn");
  if (regenBtn) {
    regenBtn.addEventListener("click", function () {
      if (window.confirm("Replace the current theory?")) generate();
    });
  }

  var completeBtn = document.getElementById("complete-btn");
  if (completeBtn) {
    completeBtn.addEventListener("click", function () {
      completeBtn.disabled = true;
      fetch("/learning/roadmaps/" + rm + "/day/" + day + "/complete/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken(),
          "Content-Type": "application/json",
          Accept: "application/json"
        }
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success) {
            window.location.reload();
            return;
          }
          completeBtn.disabled = false;
        })
        .catch(function () { completeBtn.disabled = false; });
    });
  }
})();
