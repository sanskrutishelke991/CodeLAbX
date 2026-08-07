"use strict";

(function () {
    function element(id) {
        return document.getElementById(id);
    }

    function showToast(type, title, description, icon) {
        const container = element("toastContainer");
        if (!container) return;

        const allowedTypes = new Set(["badge", "xp", "level", "success", "error"]);
        const toast = document.createElement("div");
        toast.className = `custom-toast ${allowedTypes.has(type) ? type : "success"}-toast`;

        const iconBox = document.createElement("div");
        iconBox.className = "toast-icon";
        iconBox.textContent = String(icon || "");

        const body = document.createElement("div");
        body.className = "toast-body";
        const heading = document.createElement("div");
        heading.className = "toast-title";
        heading.textContent = String(title || "Notification");
        const detail = document.createElement("div");
        detail.className = "toast-desc";
        detail.textContent = String(description || "");
        body.append(heading, detail);
        toast.append(iconBox, body);
        container.appendChild(toast);

        window.setTimeout(function () {
            toast.style.animation = "fadeOutRight 0.3s ease forwards";
            window.setTimeout(function () { toast.remove(); }, 300);
        }, 4000);
    }

    function handleProgressResponse(data) {
        if (!data || typeof data !== "object") return;
        if (Array.isArray(data.new_badges)) {
            data.new_badges.forEach(function (badge) {
                showToast("badge", "Badge Unlocked!", badge.name, badge.icon);
            });
        }
        if (data.xp_earned) {
            showToast("xp", `+${data.xp_earned} XP`, data.xp_reason || "Keep learning!", "⚡");
        }
        if (data.leveled_up) {
            showToast("level", "Level Up!", `Now Level ${data.new_level}`, "👑");
        }
    }

    window.showToast = showToast;
    window.handleProgressResponse = handleProgressResponse;

    const savedTheme = localStorage.getItem("codelabx-theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);

    function initializeTheme() {
        const themeToggle = element("themeToggle");
        const themeIcon = element("themeIcon");
        if (themeIcon) {
            themeIcon.className = savedTheme === "light" ? "bi bi-sun-fill" : "bi bi-moon-fill";
        }
        if (!themeToggle) return;
        themeToggle.addEventListener("click", function () {
            const current = document.documentElement.getAttribute("data-theme") || "dark";
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("codelabx-theme", next);
            if (themeIcon) {
                themeIcon.className = next === "light" ? "bi bi-sun-fill" : "bi bi-moon-fill";
            }
        });
    }

    function initializeNavigation() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".nav-btn").forEach(function (button) {
            const href = button.getAttribute("href");
            if (href && href !== "/" && currentPath.startsWith(href)) {
                button.classList.add("active");
            }
        });
    }

    function initializeChat() {
        const root = element("chatWidget");
        if (!root) return;

        const chatWindow = element("chatWindow");
        const toggleButton = element("chatToggleBtn");
        const toggleIcon = element("chatToggleIcon");
        const input = element("chatInput");
        const sendButton = element("chatSendBtn");
        const messages = element("chatMessages");
        let currentSessionId = null;
        let isOpen = false;

        function setOpen(nextOpen) {
            isOpen = nextOpen;
            chatWindow.classList.toggle("open", isOpen);
            toggleButton.classList.toggle("active", isOpen);
            toggleIcon.className = isOpen ? "bi bi-x-lg" : "bi bi-chat-dots-fill";
            toggleButton.setAttribute("aria-expanded", String(isOpen));
            if (isOpen) input.focus();
        }

        function toggleChat() {
            setOpen(!isOpen);
        }

        function newChat() {
            currentSessionId = null;
            messages.replaceChildren();
            const welcome = document.createElement("div");
            welcome.className = "welcome-message";
            welcome.innerHTML = '<div class="welcome-icon"><i class="bi bi-stars"></i></div><h5>New Chat Started</h5><p>Ask a learning question.</p>';
            messages.appendChild(welcome);
        }

        function addMessage(role, content, isHtml) {
            const welcome = messages.querySelector(".welcome-message");
            if (welcome) welcome.remove();

            const message = document.createElement("div");
            message.className = `chat-message ${role}`;
            const avatar = document.createElement("div");
            avatar.className = `message-avatar ${role === "user" ? "user" : "assistant"}`;
            if (role === "user") {
                avatar.textContent = root.dataset.userInitial || "?";
            } else {
                avatar.innerHTML = '<i class="bi bi-robot"></i>';
            }
            const contentBox = document.createElement("div");
            contentBox.className = "message-content";
            if (isHtml) {
                contentBox.innerHTML = String(content || "");
            } else {
                contentBox.textContent = String(content || "");
            }
            message.append(avatar, contentBox);
            messages.appendChild(message);
            messages.scrollTop = messages.scrollHeight;
        }

        function showTyping() {
            const typing = document.createElement("div");
            typing.id = "typingIndicator";
            typing.className = "chat-message assistant";
            typing.innerHTML = '<div class="message-avatar assistant"><i class="bi bi-robot"></i></div><div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
            messages.appendChild(typing);
            messages.scrollTop = messages.scrollHeight;
        }

        function removeTyping() {
            const typing = element("typingIndicator");
            if (typing) typing.remove();
        }

        async function sendMessage() {
            const message = input.value.trim();
            if (!message || sendButton.disabled) return;

            addMessage("user", message, false);
            input.value = "";
            sendButton.disabled = true;
            showTyping();

            try {
                const tokenMatch = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
                const response = await fetch(root.dataset.chatUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": tokenMatch ? decodeURIComponent(tokenMatch[1]) : "",
                    },
                    body: JSON.stringify({message: message, session_id: currentSessionId}),
                });
                const data = await response.json();
                removeTyping();
                if (response.ok && data.success) {
                    currentSessionId = data.session_id;
                    addMessage("assistant", data.response, true);
                } else {
                    addMessage("assistant", data.error || "The assistant is unavailable right now.", false);
                }
            } catch (error) {
                removeTyping();
                addMessage("assistant", "The assistant is unavailable right now.", false);
            } finally {
                sendButton.disabled = false;
                input.focus();
            }
        }

        toggleButton.addEventListener("click", toggleChat);
        root.querySelectorAll("[data-chat-close]").forEach(function (button) {
            button.addEventListener("click", function () { setOpen(false); });
        });
        root.querySelectorAll("[data-chat-new]").forEach(function (button) {
            button.addEventListener("click", newChat);
        });
        root.querySelectorAll("[data-chat-suggestion]").forEach(function (button) {
            button.addEventListener("click", function () {
                input.value = button.textContent.trim();
                sendMessage();
            });
        });
        sendButton.addEventListener("click", sendMessage);
        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });
        input.addEventListener("input", function () {
            input.style.height = "auto";
            input.style.height = `${Math.min(input.scrollHeight, 80)}px`;
        });
        document.querySelectorAll("[data-open-chat]").forEach(function (button) {
            button.addEventListener("click", function () { setOpen(true); });
        });
        window.toggleChat = toggleChat;
    }

    function initializeOmnitrix() {
        const backdrop = element("omnitrixBackdrop");
        const dial = element("omnitrixDial");
        const toggleButton = document.querySelector(".nav-btn-more");
        if (!backdrop || !dial || !toggleButton) return;

        function setOpen(open) {
            backdrop.classList.toggle("show", open);
            dial.classList.toggle("show", open);
            toggleButton.classList.toggle("active", open);
            toggleButton.setAttribute("aria-expanded", String(open));
            document.body.style.overflow = open ? "hidden" : "";
        }
        function toggle() {
            setOpen(!dial.classList.contains("show"));
        }
        function close() {
            setOpen(false);
        }

        toggleButton.addEventListener("click", toggle);
        backdrop.addEventListener("click", close);
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") close();
        });

        const labelName = dial.querySelector(".omni-label-name");
        const labelDescription = dial.querySelector(".omni-label-desc");
        dial.querySelectorAll(".omni-btn").forEach(function (button) {
            button.addEventListener("mouseenter", function () {
                if (labelName) labelName.textContent = button.dataset.name || "Feature";
                if (labelDescription) labelDescription.textContent = button.dataset.desc || "Open feature";
            });
        });
        dial.addEventListener("mouseleave", function () {
            if (labelName) labelName.textContent = "Select Feature";
            if (labelDescription) labelDescription.textContent = "Hover any icon";
        });
        window.toggleOmnitrixNew = toggle;
        window.closeOmnitrixNew = close;
    }

    function initializeToolFilters() {
        const controls = document.querySelectorAll("[data-tool-filter]");
        const cards = document.querySelectorAll("[data-tool-categories]");
        if (!controls.length || !cards.length) return;
        controls.forEach(function (control) {
            control.addEventListener("click", function () {
                const filter = control.dataset.toolFilter;
                controls.forEach(function (item) {
                    const active = item === control;
                    item.classList.toggle("active", active);
                    item.setAttribute("aria-pressed", String(active));
                });
                cards.forEach(function (card) {
                    const categories = (card.dataset.toolCategories || "").split(" ");
                    card.hidden = filter !== "all" && !categories.includes(filter);
                });
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initializeTheme();
        initializeNavigation();
        initializeChat();
        initializeOmnitrix();
        initializeToolFilters();
    });
}());
