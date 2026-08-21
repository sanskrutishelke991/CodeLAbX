"use strict";

const dayRuntime = document.getElementById('dayRuntime');

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async function generateContent() {
        const contentArea = document.getElementById('contentArea');
        const loadingState = document.getElementById('loadingState');
        const generateEmpty = document.getElementById('generateEmpty');

        if (generateEmpty) generateEmpty.style.display = 'none';
        loadingState.style.display = 'block';

        try {
            const response = await fetch(dayRuntime.dataset.generateUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
            });

            const data = await response.json();

            loadingState.style.display = 'none';

            if (data.success) {
                contentArea.innerHTML = `<div id="aiContent">${data.content}</div>`;

                // Reload page to show regenerate button
                setTimeout(() => location.reload(), 500);
            } else {
                alert('Error: ' + (data.error || 'Failed to generate content'));
                if (generateEmpty) generateEmpty.style.display = 'block';
            }
        } catch (error) {
            loadingState.style.display = 'none';
            if (generateEmpty) generateEmpty.style.display = 'block';
            alert('Error: ' + error.message);
        }
    }

    function regenerateContent() {
        if (confirm('Regenerate content? This will replace the current content.')) {
            const contentArea = document.getElementById('contentArea');
            contentArea.innerHTML = '<div class="generate-empty" id="generateEmpty"><i class="bi bi-stars"></i></div>';
            generateContent();
        }
    }

    async function markComplete() {
        const btn = document.getElementById('completeBtn');
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Marking...';

        try {
            const response = await fetch(dayRuntime.dataset.completeUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
            });

            const data = await response.json();

            if (data.success) {
                btn.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Completed!';
                setTimeout(() => location.reload(), 1000);
            }
        } catch (error) {
            alert('Error: ' + error.message);
            btn.disabled = false;
        }
    }

    const generateButton = document.getElementById('generateBtn');
    if (generateButton) generateButton.addEventListener('click', generateContent);
    const completeButton = document.getElementById('completeBtn');
    if (completeButton) completeButton.addEventListener('click', markComplete);
    const regenerateButton = document.getElementById('regenerateBtn');
    if (regenerateButton) regenerateButton.addEventListener('click', regenerateContent);
