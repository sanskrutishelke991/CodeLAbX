"use strict";

function getCookie(name) {
    let value = null;
    if (document.cookie) {
        for (let cookie of document.cookie.split(";")) {
            cookie = cookie.trim();
            if (cookie.startsWith(`${name}=`)) {
                value = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return value;
}

async function deleteAnalysis(id) {
    if (!window.confirm("Delete this analysis?")) return;

    try {
        const response = await fetch(`/ai-tools/image/${id}/delete/`, {
            method: "POST",
            headers: {"X-CSRFToken": getCookie("csrftoken") || ""},
        });
        const data = await response.json();
        if (response.ok && data.success) {
            window.location.reload();
            return;
        }
    } catch (error) {
        // The public message below intentionally hides browser/provider details.
    }
    window.alert("The analysis could not be deleted. Please try again.");
}

document.querySelectorAll("[data-delete-analysis]").forEach(function (button) {
    button.addEventListener("click", function () {
        deleteAnalysis(button.dataset.deleteAnalysis);
    });
});
