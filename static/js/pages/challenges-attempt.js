"use strict";

const challengeRuntime = document.getElementById("challengeRuntime");
const challengeType = challengeRuntime.dataset.challengeType;
const startedAt = Date.now();
let selectedOption = -1;

window.setInterval(function () {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    const minutes = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const seconds = String(elapsed % 60).padStart(2, "0");
    document.getElementById("timer").textContent = `${minutes}:${seconds}`;
}, 1000);

const hintsButton = document.getElementById("toggleHintsBtn");
if (hintsButton) {
    hintsButton.addEventListener("click", function () {
        const section = document.getElementById("hintsSection");
        const visible = section.style.display !== "none";
        section.style.display = visible ? "none" : "block";
        hintsButton.setAttribute("aria-expanded", String(!visible));
    });
}

document.querySelectorAll("[data-option-index]").forEach(function (button) {
    button.addEventListener("click", function () {
        document.querySelectorAll("[data-option-index]").forEach(function (item) {
            item.classList.remove("selected");
        });
        button.classList.add("selected");
        selectedOption = Number(button.dataset.optionIndex);
        document.getElementById("selectedOption").value = selectedOption;
    });
});

function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
}

async function submitChallenge() {
    const button = document.getElementById("submitBtn");
    const payload = {
        time_taken: Math.floor((Date.now() - startedAt) / 1000),
    };

    if (challengeType === "coding") {
        const code = document.getElementById("codeInput").value.trim();
        if (!code) {
            window.alert("Please write some code first.");
            return;
        }
        payload.code = code;
    } else {
        if (selectedOption < 0) {
            window.alert("Please select an answer.");
            return;
        }
        payload.selected_option = selectedOption;
    }

    button.disabled = true;
    button.textContent = "Submitting…";
    try {
        const response = await fetch(challengeRuntime.dataset.submitUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (response.ok && result.success) {
            window.location.assign(result.redirect_url);
            return;
        }
        window.alert(result.error || "The challenge could not be submitted.");
    } catch (error) {
        window.alert("The challenge could not be submitted. Please try again.");
    } finally {
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-check-lg me-2"></i>Submit Answer';
    }
}

document.getElementById("submitBtn").addEventListener("click", submitChallenge);
