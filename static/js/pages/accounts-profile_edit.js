"use strict";

// Extracted page behavior: accounts-profile_edit.js
// Preview avatar on upload
document.querySelector('input[type="file"]').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('avatarPreview');
            preview.outerHTML = `<img src="${e.target.result}" alt="Preview" id="avatarPreview" style="width: 100%; height: 100%; object-fit: cover;">`;
        };
        reader.readAsDataURL(file);
    }
});
