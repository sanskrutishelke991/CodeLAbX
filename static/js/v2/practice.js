(function () {
  "use strict";
  var lang = document.getElementById("language");
  var tmpl = document.getElementById("template");
  var problem = document.getElementById("problem");
  var code = document.getElementById("code");
  var checkBtn = document.getElementById("check-btn");
  var clearBtn = document.getElementById("clear-btn");
  var emptyEl = document.getElementById("fb-empty");
  var loadEl = document.getElementById("fb-load");
  var outEl = document.getElementById("fb-out");
  if (!code || !checkBtn) return;

  var templates = {
    two_sum: {
      problem: "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
      python: "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n    return []\n\nprint(two_sum([2, 7, 11, 15], 9))",
      javascript: "function twoSum(nums, target) {\n  const seen = {};\n  for (let i = 0; i < nums.length; i++) {\n    if (target - nums[i] in seen) return [seen[target - nums[i]], i];\n    seen[nums[i]] = i;\n  }\n  return [];\n}\nconsole.log(twoSum([2, 7, 11, 15], 9));"
    },
    fibonacci: {
      problem: "Return the nth Fibonacci number.",
      python: "def fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b\n\nprint(fibonacci(10))",
      javascript: "function fibonacci(n) {\n  if (n <= 1) return n;\n  let a = 0, b = 1;\n  for (let i = 2; i <= n; i++) [a, b] = [b, a + b];\n  return b;\n}\nconsole.log(fibonacci(10));"
    },
    palindrome: {
      problem: "Check if a string is a palindrome.",
      python: "def is_palindrome(s):\n    s = ''.join(ch.lower() for ch in s if ch.isalnum())\n    return s == s[::-1]\n\nprint(is_palindrome('A man a plan a canal Panama'))",
      javascript: "function isPalindrome(s) {\n  s = s.toLowerCase().replace(/[^a-z0-9]/g, '');\n  return s === s.split('').reverse().join('');\n}\nconsole.log(isPalindrome('A man a plan a canal Panama'));"
    },
    binary_search: {
      problem: "Implement binary search. Return the index of target, or -1.",
      python: "def binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        if arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1\n\nprint(binary_search([1, 3, 5, 7, 9, 11], 7))",
      javascript: "function binarySearch(arr, target) {\n  let left = 0, right = arr.length - 1;\n  while (left <= right) {\n    const mid = Math.floor((left + right) / 2);\n    if (arr[mid] === target) return mid;\n    if (arr[mid] < target) left = mid + 1;\n    else right = mid - 1;\n  }\n  return -1;\n}\nconsole.log(binarySearch([1, 3, 5, 7, 9, 11], 7));"
    },
    reverse_string: {
      problem: "Reverse a string.",
      python: "def reverse_string(s):\n    return s[::-1]\n\nprint(reverse_string('Hello, World!'))",
      javascript: "function reverseString(s) {\n  return s.split('').reverse().join('');\n}\nconsole.log(reverseString('Hello, World!'));"
    }
  };

  function csrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    if (el && el.value) return el.value;
    var cookies = document.cookie ? document.cookie.split(";") : [];
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.indexOf("csrftoken=") === 0) return decodeURIComponent(c.slice(10));
    }
    return "";
  }

  function show(which) {
    emptyEl.hidden = which !== "empty";
    loadEl.hidden = which !== "load";
    outEl.hidden = which !== "out";
  }

  if (tmpl) {
    tmpl.addEventListener("change", function () {
      var name = tmpl.value;
      if (!name || !templates[name]) return;
      var pack = templates[name];
      var key = lang && (lang.value === "javascript" || lang.value === "typescript") ? "javascript" : "python";
      problem.value = pack.problem;
      code.value = pack[key] || pack.python;
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      if (!window.confirm("Clear the editor and problem?")) return;
      code.value = "";
      problem.value = "";
      if (tmpl) tmpl.value = "";
      outEl.textContent = "";
      show("empty");
    });
  }

  checkBtn.addEventListener("click", function () {
    var src = code.value.trim();
    if (!src) {
      outEl.textContent = "Write some code first.";
      show("out");
      return;
    }
    show("load");
    checkBtn.disabled = true;
    fetch("/practice/api/check-code/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        Accept: "application/json"
      },
      body: JSON.stringify({
        code: src,
        language: lang ? lang.value : "python",
        problem: problem.value.trim()
      })
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (pack) {
        if (pack.data && pack.data.success) {
          outEl.innerHTML = pack.data.feedback || "";
        } else {
          outEl.textContent = (pack.data && pack.data.error) || "Review failed.";
        }
        show("out");
      })
      .catch(function () {
        outEl.textContent = "Could not reach the reviewer.";
        show("out");
      })
      .then(function () { checkBtn.disabled = false; });
  });
})();
