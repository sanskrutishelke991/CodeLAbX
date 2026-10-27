"use strict";

const runtime = document.getElementById('testRuntime');
const storageKey = runtime.dataset.storageKey;
const questions = JSON.parse(
    document
        .getElementById('test-questions-data')
        .textContent
);
let currentQuestion = 0;
let answers = {};
let timeRemaining = Number(runtime.dataset.secondsRemaining);
let timerInterval;

// Load saved answers from localStorage
function loadSavedAnswers() {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
        answers = JSON.parse(saved);
    }
}

// Save answers to localStorage
function saveProgress() {
    localStorage.setItem(storageKey, JSON.stringify(answers));
}

// Render current question
function renderQuestion() {
    const q = questions[currentQuestion];
    document.getElementById('qNumber').textContent = currentQuestion + 1;
    document.getElementById('currentQ').textContent = currentQuestion + 1;
    document.getElementById('questionText').textContent = q.question;

    // Update progress bar
    const progress = ((currentQuestion + 1) / questions.length) * 100;
    document.getElementById('progressBar').style.width = progress + '%';

    // Render options
    const container = document.getElementById('optionsContainer');
    container.innerHTML = '';

    q.options.forEach((option, index) => {
        const isSelected = answers[currentQuestion] === index;
        const label = document.createElement('label');
        label.className = 'option-label' + (isSelected ? ' selected' : '');
        const input = document.createElement(
            'input'
        );

        input.type = 'radio';
        input.name = 'option';
        input.className = 'option-input';
        input.value = index;
        input.checked = isSelected;

        const text = document.createElement(
            'span'
        );

        text.className = 'option-text';
        text.textContent = (
            `${String.fromCharCode(65 + index)}. `
            + option
        );

        label.appendChild(input);
        label.appendChild(text);
        label.addEventListener('click', () => selectOption(index));
        container.appendChild(label);
    });

    // Update buttons
    document.getElementById('prevBtn').disabled = currentQuestion === 0;

    if (currentQuestion === questions.length - 1) {
        document.getElementById('nextBtn').style.display = 'none';
        document.getElementById('submitBtn').style.display = 'inline-block';
    } else {
        document.getElementById('nextBtn').style.display = 'inline-block';
        document.getElementById('submitBtn').style.display = 'none';
    }
}

// Select an option
function selectOption(index) {
    answers[currentQuestion] = index;
    renderQuestion();
    saveProgress();
}

// Navigate questions
function nextQuestion() {
    if (currentQuestion < questions.length - 1) {
        currentQuestion++;
        renderQuestion();
    }
}

function prevQuestion() {
    if (currentQuestion > 0) {
        currentQuestion--;
        renderQuestion();
    }
}

// Timer
function updateTimer() {
    const minutes = Math.floor(timeRemaining / 60);
    const seconds = timeRemaining % 60;
    const timerEl = document.getElementById('timer');

    timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

    if (timeRemaining <= 60) {
        timerEl.classList.add('timer-warning');
    }

    if (timeRemaining <= 0) {
        clearInterval(timerInterval);
        alert('Time is up! Submitting your test...');
        submitTest();
    }

    timeRemaining--;
}

// Show submit modal
function showSubmitModal() {
    const answered = Object.keys(answers).length;
    document.getElementById('answeredCount').textContent = answered;
    new bootstrap.Modal(document.getElementById('submitModal')).show();
}

// Submit test
async function submitTest() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('submitModal'));
    if (modal) modal.hide();

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = 'Submitting...';

    clearInterval(timerInterval);

    try {
        const response = await fetch(runtime.dataset.submitUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                answers: answers,
                attempt_id: Number(runtime.dataset.attemptId)
            })
        });

        const data = await response.json();

        if (data.success) {
            localStorage.removeItem(storageKey);
            window.location.href = runtime.dataset.resultUrl;
        } else {
            alert('Error submitting test: ' + data.error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Submit Test';
        }
    } catch (error) {
        alert('Error: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Submit Test';
    }
}

function getCookie(name) {
    let v = null;
    if (document.cookie) {
        for (let c of document.cookie.split(';')) {
            c = c.trim();
            if (c.startsWith(name + '=')) { v = decodeURIComponent(c.substring(name.length + 1)); break; }
        }
    }
    return v;
}

document.getElementById('saveProgressBtn').addEventListener('click', saveProgress);
document.getElementById('prevBtn').addEventListener('click', prevQuestion);
document.getElementById('nextBtn').addEventListener('click', nextQuestion);
document.getElementById('submitBtn').addEventListener('click', showSubmitModal);
document.getElementById('confirmSubmitBtn').addEventListener('click', submitTest);

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadSavedAnswers();
    renderQuestion();
    timerInterval = setInterval(updateTimer, 1000);
});

// Auto-save on page unload
window.addEventListener('beforeunload', function() {
    saveProgress();
});
