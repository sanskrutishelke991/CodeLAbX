"use strict";

const uploadCard = document.getElementById('uploadCard');
const imageInput = document.getElementById('imageInput');
const previewContainer = document.getElementById('previewContainer');
const previewImage = document.getElementById('previewImage');
const uploadPrompt = document.getElementById('uploadPrompt');

// Click to upload
uploadCard.addEventListener('click', () => {
    if (!previewContainer.style.display || previewContainer.style.display === 'none') {
        imageInput.click();
    }
});

// Drag and drop
uploadCard.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadCard.classList.add('dragover');
});

uploadCard.addEventListener('dragleave', () => {
    uploadCard.classList.remove('dragover');
});

uploadCard.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadCard.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        imageInput.files = e.dataTransfer.files;
        showPreview(e.dataTransfer.files[0]);
    }
});

imageInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        showPreview(e.target.files[0]);
    }
});

function showPreview(file) {
    if (file.size > 5 * 1024 * 1024) {
        alert('File too large! Max 5MB.');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        previewImage.src = e.target.result;
        uploadPrompt.style.display = 'none';
        previewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

function removeImage() {
    imageInput.value = '';
    previewImage.src = '';
    uploadPrompt.style.display = 'block';
    previewContainer.style.display = 'none';
}

function selectType(type, elem) {
    document.querySelectorAll('.type-option').forEach(o => o.classList.remove('selected'));
    elem.classList.add('selected');
    document.getElementById('analysisType').value = type;
}

function getCookie(name) {
    let value = null;
    if (document.cookie) {
        for (let c of document.cookie.split(';')) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                value = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
    }
    return value;
}

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!imageInput.files.length) {
        alert('Please select an image');
        return;
    }

    const submitBtn = document.getElementById('submitBtn');
    const loadingContainer = document.getElementById('loadingContainer');

    submitBtn.disabled = true;
    submitBtn.style.display = 'none';
    loadingContainer.style.display = 'block';

    const formData = new FormData(e.target);

    try {
        const response = await fetch(document.getElementById('uploadForm').dataset.uploadEndpoint, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            window.location.href = data.redirect_url;
        } else {
            alert('Error: ' + data.error);
            submitBtn.disabled = false;
            submitBtn.style.display = 'block';
            loadingContainer.style.display = 'none';
        }
    } catch (error) {
        alert('Error: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.style.display = 'block';
        loadingContainer.style.display = 'none';
    }
});

document.querySelector('[data-remove-image]').addEventListener('click', function (event) {
    event.stopPropagation();
    removeImage();
});

document.querySelectorAll('[data-analysis-type]').forEach(function (option) {
    function activate() {
        selectType(option.dataset.analysisType, option);
    }
    option.addEventListener('click', activate);
    option.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            activate();
        }
    });
});
