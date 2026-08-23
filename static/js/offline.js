"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const button = document.querySelector("[data-offline-retry]");
    if (button) {
        button.addEventListener("click", function () {
            window.location.reload();
        });
    }
});
