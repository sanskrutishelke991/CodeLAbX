"use strict";

(function () {
    const button = document.getElementById('shareProfileButton');
    const feedback = document.getElementById('copyFeedback');
    const label = document.getElementById('shareButtonLabel');
    if (!button) return;

    const profileUrl = button.dataset.profileUrl;

    function showCopied(message) {
        feedback.textContent = message;
        label.textContent = 'Copied';
        window.setTimeout(function () {
            feedback.textContent = '';
            label.textContent = 'Share';
        }, 2200);
    }

    async function copyUrl() {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(profileUrl);
        } else {
            const area = document.createElement('textarea');
            area.value = profileUrl;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            document.execCommand('copy');
            area.remove();
        }
        showCopied('Profile link copied to clipboard.');
    }

    button.addEventListener('click', async function () {
        try {
            if (navigator.share) {
                await navigator.share({
                    title: button.dataset.shareTitle,
                    text: 'View this CodeLabX learner profile.',
                    url: profileUrl
                });
            } else {
                await copyUrl();
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                try {
                    await copyUrl();
                } catch (copyError) {
                    feedback.textContent = 'Could not copy the profile link.';
                }
            }
        }
    });
})();
