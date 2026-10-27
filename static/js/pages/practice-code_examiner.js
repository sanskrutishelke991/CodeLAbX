"use strict";

// Extracted page behavior: practice-code_examiner.js
// Language configurations
    const languageConfig = {
        python: { ext: 'py', color: '#3776AB', comment: '#' },
        javascript: { ext: 'js', color: '#FFD43B', comment: '//' },
        java: { ext: 'java', color: '#ED8B00', comment: '//' },
        cpp: { ext: 'cpp', color: '#00599C', comment: '//' },
        typescript: { ext: 'ts', color: '#3178C6', comment: '//' },
        go: { ext: 'go', color: '#00ADD8', comment: '//' },
        rust: { ext: 'rs', color: '#DEA584', comment: '//' },
        ruby: { ext: 'rb', color: '#CC342D', comment: '#' },
    };

    // Templates
    const templates = {
        two_sum: {
            problem: "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
            code: {
                python: "def two_sum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i+1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]\n    return []\n\n# Test\nprint(two_sum([2, 7, 11, 15], 9))",
                javascript: "function twoSum(nums, target) {\n    for (let i = 0; i < nums.length; i++) {\n        for (let j = i + 1; j < nums.length; j++) {\n            if (nums[i] + nums[j] === target) {\n                return [i, j];\n            }\n        }\n    }\n    return [];\n}\n\nconsole.log(twoSum([2, 7, 11, 15], 9));"
            }
        },
        fibonacci: {
            problem: "Return the nth Fibonacci number.",
            code: {
                python: "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\nprint(fibonacci(10))",
                javascript: "function fibonacci(n) {\n    if (n <= 1) return n;\n    return fibonacci(n-1) + fibonacci(n-2);\n}\n\nconsole.log(fibonacci(10));"
            }
        },
        palindrome: {
            problem: "Check if a string is a palindrome.",
            code: {
                python: "def is_palindrome(s):\n    s = s.lower().replace(' ', '')\n    return s == s[::-1]\n\nprint(is_palindrome('A man a plan a canal Panama'))",
                javascript: "function isPalindrome(s) {\n    s = s.toLowerCase().replace(/ /g, '');\n    return s === s.split('').reverse().join('');\n}\n\nconsole.log(isPalindrome('A man a plan a canal Panama'));"
            }
        },
        binary_search: {
            problem: "Implement binary search algorithm.",
            code: {
                python: "def binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1\n\nprint(binary_search([1, 3, 5, 7, 9, 11], 7))",
                javascript: "function binarySearch(arr, target) {\n    let left = 0, right = arr.length - 1;\n    while (left <= right) {\n        let mid = Math.floor((left + right) / 2);\n        if (arr[mid] === target) return mid;\n        else if (arr[mid] < target) left = mid + 1;\n        else right = mid - 1;\n    }\n    return -1;\n}\n\nconsole.log(binarySearch([1, 3, 5, 7, 9, 11], 7));"
            }
        },
        reverse_string: {
            problem: "Reverse a string.",
            code: {
                python: "def reverse_string(s):\n    return s[::-1]\n\nprint(reverse_string('Hello, World!'))",
                javascript: "function reverseString(s) {\n    return s.split('').reverse().join('');\n}\n\nconsole.log(reverseString('Hello, World!'));"
            }
        }
    };

    // Update editor stats
    function updateEditor() {
        const code = document.getElementById('code').value;
        const lines = code.split('\n');
        const lineCount = lines.length;
        const charCount = code.length;

        document.getElementById('lineCount').textContent = `${lineCount} lines`;
        document.getElementById('charCount').textContent = `${charCount} chars`;

        // Update line numbers
        let numbers = '';
        for (let i = 1; i <= lineCount; i++) {
            numbers += i + '\n';
        }
        document.getElementById('lineNumbers').textContent = numbers.trim();
    }

    // Update language
    function updateLanguage() {
        const lang = document.getElementById('language').value;
        const config = languageConfig[lang];

        document.getElementById('fileName').textContent = `main.${config.ext}`;
        document.getElementById('langDot').style.background = config.color;
    }

    // Load template
    function loadTemplate() {
        const templateName = document.getElementById('template').value;
        const lang = document.getElementById('language').value;

        if (!templateName) return;

        const template = templates[templateName];
        if (template) {
            document.getElementById('problem').value = template.problem;
            const code = template.code[lang] || template.code.python;
            document.getElementById('code').value = code.replace(/\\n/g, '\n');
            updateEditor();
        }
    }

    // Clear code
    function clearCode() {
        if (confirm('Clear all code and problem statement?')) {
            document.getElementById('code').value = '';
            document.getElementById('problem').value = '';
            document.getElementById('template').value = '';
            updateEditor();
        }
    }

    // Copy code
    function copyCode() {
        const code = document.getElementById('code').value;
        navigator.clipboard.writeText(code);

        // Show toast if available
        if (typeof showToast === 'function') {
            showToast('xp', 'Copied!', 'Code copied to clipboard', '📋');
        }
    }

    // Copy feedback
    function copyFeedback() {
        const feedback = document.getElementById('feedbackResult').innerText;
        navigator.clipboard.writeText(feedback);
        if (typeof showToast === 'function') {
            showToast('xp', 'Copied!', 'Feedback copied', '📋');
        }
    }

    // Toggle fullscreen (basic)
    function toggleFullscreen() {
        const wrapper = document.querySelector('.editor-wrapper');
        if (!document.fullscreenElement) {
            wrapper.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    // Get CSRF token
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

    // Check code with AI
    async function checkCode() {
        const code = document.getElementById('code').value.trim();
        const language = document.getElementById('language').value;
        const problem = document.getElementById('problem').value.trim();

        if (!code) {
            alert('Please write some code first!');
            return;
        }

        // Show loading
        document.getElementById('emptyFeedback').style.display = 'none';
        document.getElementById('feedbackResult').classList.remove('active');
        document.getElementById('loadingFeedback').classList.add('active');
        document.getElementById('checkBtn').disabled = true;
        document.getElementById('checkBtn').innerHTML = '<i class="bi bi-hourglass-split"></i><span>Analyzing...</span>';

        try {
            const response = await fetch('/practice/api/check-code/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ code, language, problem })
            });

            const data = await response.json();

            document.getElementById('loadingFeedback').classList.remove('active');

            if (data.success) {
                document.getElementById('feedbackResult').innerHTML = data.feedback;
                document.getElementById('feedbackResult').classList.add('active');
                document.getElementById('copyFeedbackBtn').style.display = 'flex';

                // Show XP toast if available
                if (data.xp_earned && typeof handleProgressResponse === 'function') {
                    handleProgressResponse(data);
                }
            } else {
                document.getElementById('feedbackResult').innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <i class="bi bi-exclamation-triangle" style="font-size: 3rem; color: #EF4444;"></i>
                        <h3 style="color: #EF4444; margin-top: 16px;">Error</h3>
                        <p>${data.error || 'Something went wrong'}</p>
                    </div>
                `;
                document.getElementById('feedbackResult').classList.add('active');
            }
        } catch (error) {
            document.getElementById('loadingFeedback').classList.remove('active');
            document.getElementById('feedbackResult').innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <i class="bi bi-wifi-off" style="font-size: 3rem; color: #EF4444;"></i>
                    <h3 style="color: #EF4444; margin-top: 16px;">Connection Error</h3>
                    <p>${error.message}</p>
                </div>
            `;
            document.getElementById('feedbackResult').classList.add('active');
        } finally {
            document.getElementById('checkBtn').disabled = false;
            document.getElementById('checkBtn').innerHTML = '<i class="bi bi-magic"></i><span>Analyze My Code</span>';
        }
    }

    document.querySelector('[data-code-action="copy"]').addEventListener('click', copyCode);
    document.querySelector('[data-code-action="fullscreen"]').addEventListener('click', toggleFullscreen);
    document.querySelector('[data-code-action="clear"]').addEventListener('click', clearCode);
    document.querySelector('[data-code-action="copy-feedback"]').addEventListener('click', copyFeedback);
    document.querySelector('[data-code-language]').addEventListener('change', updateLanguage);
    document.querySelector('[data-code-template]').addEventListener('change', loadTemplate);
    document.querySelector('[data-code-editor]').addEventListener('input', updateEditor);
    document.getElementById('checkBtn').addEventListener('click', checkCode);

    // Initialize
    updateLanguage();
    updateEditor();
