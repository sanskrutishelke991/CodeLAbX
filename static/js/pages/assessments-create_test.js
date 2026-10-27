"use strict";

// Set topic from chip
    function setTopic(topic) {
        document.getElementById('topicInput').value = topic;
        document.getElementById('topicInput').focus();
    }

    // Select difficulty
    function selectDifficulty(diff, elem) {
        document.querySelectorAll('.difficulty-card').forEach(card => {
            card.classList.remove('selected');
        });
        elem.classList.add('selected');
        document.getElementById('difficultyInput').value = diff;
        updateXPPreview();
    }

    // Select time preset
    function selectTime(minutes, elem) {
        document.querySelectorAll('.time-preset').forEach(p => {
            p.classList.remove('selected');
        });
        elem.classList.add('selected');
        document.getElementById('timeInput').value = minutes;
        document.getElementById('previewTime').textContent = minutes + ' min';
    }

    // Update question count
    function updateCount(value) {
        document.getElementById('countDisplay').textContent = value;
        document.getElementById('previewQuestions').textContent = value;
        updateXPPreview();
    }

    // Update XP preview
    function updateXPPreview() {
        const questions = parseInt(document.getElementById('countSlider').value);
        const difficulty = document.getElementById('difficultyInput').value;
        const multiplier = { easy: 5, medium: 8, hard: 12 };
        const xp = questions * (multiplier[difficulty] || 5);
        document.getElementById('previewXP').textContent = '+' + xp + ' XP';
    }

    document.getElementById('testForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = document.getElementById('submitBtn');
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i><span>Generating with AI...</span>';

        try {
            const response = await fetch(document.getElementById('testForm').dataset.generateEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    topic: document.getElementById('topicInput').value,
                    difficulty: document.getElementById('difficultyInput').value,
                    num_questions: parseInt(document.getElementById('countSlider').value),
                    time_limit_minutes: parseInt(document.getElementById('timeInput').value)
                })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Unable to generate the assessment.');
            }
            window.location.href = data.redirect_url;
        } catch (error) {
            alert(error.message);
            btn.disabled = false;
            btn.innerHTML = original;
        }
    });

    // Initialize
    updateXPPreview();

document.querySelectorAll('[data-test-topic]').forEach(function (button) {
    button.addEventListener('click', function () {
        setTopic(button.dataset.testTopic);
    });
});

function bindKeyboardChoice(selector, callback) {
    document.querySelectorAll(selector).forEach(function (element) {
        function activate() { callback(element); }
        element.addEventListener('click', activate);
        element.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                activate();
            }
        });
    });
}

bindKeyboardChoice('[data-test-difficulty]', function (element) {
    selectDifficulty(element.dataset.testDifficulty, element);
});
bindKeyboardChoice('[data-test-time]', function (element) {
    selectTime(Number(element.dataset.testTime), element);
});
document.querySelector('[data-question-count]').addEventListener('input', function (event) {
    updateCount(event.target.value);
});
