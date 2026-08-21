"use strict";

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

async function markWatched() {
    const btn = document.getElementById('watchedBtn');

    try {
        const response = await fetch(btn.dataset.endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        const data = await response.json();

        if (data.success) {
            btn.classList.add('watched');
            btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> <span>Watched</span>';

            if (typeof showToast === 'function') {
                showToast('xp', '+10 XP', 'Video marked as watched!', '⚡');
            }
        }
    } catch (error) {
        console.error(error);
    }
}

async function toggleFavorite() {
    const btn = document.getElementById('favoriteBtn');

    try {
        const response = await fetch(btn.dataset.endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        const data = await response.json();

        if (data.success) {
            if (data.is_favorited) {
                btn.classList.add('favorited');
                btn.innerHTML = '<i class="bi bi-heart-fill"></i> <span>Favorited</span>';
            } else {
                btn.classList.remove('favorited');
                btn.innerHTML = '<i class="bi bi-heart"></i> <span>Favorite</span>';
            }
        }
    } catch (error) {
        console.error(error);
    }
}

document.getElementById('watchedBtn').addEventListener('click', markWatched);
document.getElementById('favoriteBtn').addEventListener('click', toggleFavorite);
