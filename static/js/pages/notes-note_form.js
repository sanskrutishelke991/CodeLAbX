"use strict";

// Extracted page behavior: notes-note_form.js
document.querySelectorAll('.color-option').forEach(option => {
    option.addEventListener('click', function() {
        document.querySelectorAll('.color-option').forEach(o => o.classList.remove('selected'));
        this.classList.add('selected');
        document.getElementById('colorInput').value = this.dataset.color;
    });
});
