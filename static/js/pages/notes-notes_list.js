"use strict";

function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
}

async function togglePin(noteId, button) {
    button.disabled = true;
    try {
        const response = await fetch(`/notes/${noteId}/pin/`, {
            method: "POST",
            headers: {"X-CSRFToken": csrfToken()},
        });
        const data = await response.json();
        if (!response.ok || !data.success) return;
        const icon = button.querySelector("i");
        icon.className = data.is_pinned ? "bi bi-pin-fill" : "bi bi-pin";
        button.classList.toggle("pinned", data.is_pinned);
        window.setTimeout(function () {
            window.location.reload();
        }, 500);
    } finally {
        button.disabled = false;
    }
}

document.querySelectorAll("[data-note-pin]").forEach(function (button) {
    button.addEventListener("click", function () {
        togglePin(button.dataset.notePin, button);
    });
});
