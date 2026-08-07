"use strict";
// Mouse tracking for bento cards
        (function() {
            const cards = document.querySelectorAll('.bento-card');
            cards.forEach(card => {
                card.addEventListener('mousemove', (e) => {
                    const rect = card.getBoundingClientRect();
                    const x = ((e.clientX - rect.left) / rect.width) * 100;
                    const y = ((e.clientY - rect.top) / rect.height) * 100;
                    card.style.setProperty('--mouse-x', x + '%');
                    card.style.setProperty('--mouse-y', y + '%');
                });
            });
        })();


        // Product showcase tab switcher
        (function() {
            const tabs = document.querySelectorAll('.showcase-tab');
            const contents = document.querySelectorAll('.browser-content');

            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const target = tab.dataset.tab;

                    tabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    contents.forEach(c => {
                        if (c.dataset.content === target) {
                            c.classList.add('active');
                        } else {
                            c.classList.remove('active');
                        }
                    });
                });
            });
        })();


        // Animated counter for stats
        (function() {
            const counters = document.querySelectorAll('.stat-number[data-count]');

            const animateCounter = (element) => {
                const target = parseInt(element.dataset.count);
                const duration = 2000;
                const startTime = performance.now();

                const update = (currentTime) => {
                    const elapsed = currentTime - startTime;
                    const progress = Math.min(elapsed / duration, 1);

                    // Easing function - ease out cubic
                    const easeProgress = 1 - Math.pow(1 - progress, 3);
                    const current = Math.floor(easeProgress * target);

                    element.textContent = current;

                    if (progress < 1) {
                        requestAnimationFrame(update);
                    } else {
                        element.textContent = target;
                    }
                };

                requestAnimationFrame(update);
            };

            // Observe when stats come into view
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && !entry.target.dataset.animated) {
                        entry.target.dataset.animated = 'true';
                        animateCounter(entry.target);
                    }
                });
            }, { threshold: 0.3 });

            counters.forEach(counter => observer.observe(counter));
        })();


        // FAQ accordion
        (function() {
            const faqItems = document.querySelectorAll('.faq-item');

            faqItems.forEach(item => {
                const question = item.querySelector('.faq-question');

                question.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); question.click(); } });
                question.addEventListener('click', () => {
                    const isOpen = item.classList.contains('open');

                    // Close all other items (accordion behavior)
                    faqItems.forEach(otherItem => {
                        otherItem.classList.remove('open');
                    });

                    // Toggle current item
                    if (!isOpen) {
                        item.classList.add('open');
                    }
                });
            });
        })();

        // Mode Toggle System
        (function() {
            const modeButtons = document.querySelectorAll('.mode-btn');
            const html = document.documentElement;

            // Load saved mode
            const savedMode = localStorage.getItem('codelabx-mode') || 'developer';
            html.setAttribute('data-mode', savedMode);
            updateActiveButton(savedMode);

            function updateActiveButton(mode) {
                modeButtons.forEach(btn => {
                    if (btn.dataset.modeBtn === mode) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }

            modeButtons.forEach(btn => {
                btn.addEventListener('click', function() {
                    const newMode = this.dataset.modeBtn;
                    html.setAttribute('data-mode', newMode);
                    localStorage.setItem('codelabx-mode', newMode);
                    updateActiveButton(newMode);
                });
            });
        })();
