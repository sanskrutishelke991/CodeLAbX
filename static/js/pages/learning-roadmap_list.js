"use strict";

function navigateWithParameter(name, value) {
    const url = new URL(window.location.href);
    url.searchParams.set(name, value);
    url.searchParams.delete("page");
    window.location.assign(url.toString());
}

const roadmapSearch = document.querySelector("[data-roadmap-search]");
if (roadmapSearch) {
    roadmapSearch.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            navigateWithParameter("search", roadmapSearch.value.trim());
        }
    });
}

const roadmapSort = document.querySelector("[data-roadmap-sort]");
if (roadmapSort) {
    roadmapSort.addEventListener("change", function () {
        navigateWithParameter("sort", roadmapSort.value);
    });
}

document.querySelectorAll("[data-roadmap-view]").forEach(function (button) {
    button.addEventListener("click", function () {
        navigateWithParameter("view", button.dataset.roadmapView);
    });
});
