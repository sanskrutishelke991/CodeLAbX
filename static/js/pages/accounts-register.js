"use strict";

// Extracted page behavior: accounts-register.js
// Add password strength indicator (basic)
    document.getElementById('id_password1').addEventListener('input', function() {
        const password = this.value;
        const strengthIndicator = document.getElementById('password-strength');

        // Remove existing indicator if any
        if (strengthIndicator) {
            strengthIndicator.remove();
        }

        if (password.length > 0) {
            const indicator = document.createElement('div');
            indicator.id = 'password-strength';
            indicator.className = 'form-text mt-1';

            let strength = 0;
            if (password.length >= 8) strength++;
            if (password.match(/[a-z]/) && password.match(/[A-Z]/)) strength++;
            if (password.match(/\d/)) strength++;
            if (password.match(/[^a-zA-Z\d]/)) strength++;

            const messages = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong'];
            const colors = ['#dc3545', '#dc3545', '#ffc107', '#28a745', '#28a745'];

            indicator.textContent = `Password strength: ${messages[strength]}`;
            indicator.style.color = colors[strength];

            this.parentNode.appendChild(indicator);
        }
    });
