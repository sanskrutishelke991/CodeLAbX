(function () {
  "use strict";
  var box = document.getElementById("vid-actions");
  if (!box) return;

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

  function post(url) {
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json"
      }
    }).then(function (res) { return res.json(); });
  }

  var watchBtn = document.getElementById("watch-btn");
  var favBtn = document.getElementById("fav-btn");

  if (watchBtn) {
    watchBtn.addEventListener("click", function () {
      watchBtn.disabled = true;
      post(box.getAttribute("data-watch"))
        .then(function (data) {
          if (data && data.success) {
            watchBtn.textContent = "Watched";
            watchBtn.className = "btn-ghost btn-on";
          }
          watchBtn.disabled = false;
        })
        .catch(function () { watchBtn.disabled = false; });
    });
  }

  if (favBtn) {
    favBtn.addEventListener("click", function () {
      favBtn.disabled = true;
      post(box.getAttribute("data-fav"))
        .then(function (data) {
          if (data && data.success) {
            var on = !!data.is_favorited;
            favBtn.textContent = on ? "Saved" : "Save";
            favBtn.classList.toggle("btn-on", on);
          }
          favBtn.disabled = false;
        })
        .catch(function () { favBtn.disabled = false; });
    });
  }
})();
