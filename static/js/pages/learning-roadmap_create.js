"use strict";

const topicSelect = document.getElementById("topicSelect");
const topicOptions = document.querySelectorAll(".topic-option[data-topic]");

topicOptions.forEach(function (option) {
    option.addEventListener("click", function () {
        topicOptions.forEach(function (item) {
            item.classList.remove("selected");
        });
        option.classList.add("selected");
        topicSelect.value = option.dataset.topic;
    });
    if (option.dataset.topic === topicSelect.value) {
        option.classList.add("selected");
    }
});
