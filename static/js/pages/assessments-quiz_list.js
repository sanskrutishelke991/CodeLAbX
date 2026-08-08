"use strict";

function navigateAssessmentParameter(name, value) {
    const url = new URL(window.location.href);
    url.searchParams.set(name, value);
    url.searchParams.delete("page");
    window.location.assign(url.toString());
}

const assessmentSearch = document.querySelector("[data-assessment-search]");
if (assessmentSearch) {
    assessmentSearch.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            navigateAssessmentParameter(
                "search",
                assessmentSearch.value.trim(),
            );
        }
    });
}

const assessmentSort = document.querySelector("[data-assessment-sort]");
if (assessmentSort) {
    assessmentSort.addEventListener("change", function () {
        navigateAssessmentParameter("sort", assessmentSort.value);
    });
}
