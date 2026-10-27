"use strict";

const confettiContainer = document.getElementById('confettiContainer');
if (confettiContainer.dataset.celebrate === 'true') {
    function createConfetti() {
        const container = document.getElementById('confettiContainer');
        const colors = ['#14B8A6', '#00D4AA', '#FF6B6B', '#ffc107', '#4a90e2'];

        for (let i = 0; i < 100; i++) {
            setTimeout(() => {
                const piece = document.createElement('div');
                piece.className = 'confetti-piece';
                piece.style.left = Math.random() * 100 + 'vw';
                piece.style.background = colors[Math.floor(Math.random() * colors.length)];
                piece.style.animationDuration = (Math.random() * 2 + 2) + 's';
                piece.style.width = (Math.random() * 10 + 5) + 'px';
                piece.style.height = piece.style.width;
                container.appendChild(piece);

                setTimeout(() => piece.remove(), 4000);
            }, i * 30);
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(createConfetti, 500);
    });
}
