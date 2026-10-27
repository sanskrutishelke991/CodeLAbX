"use strict";

(function () {
    const MAX_TRANSCRIPT_CHARS = 4000;
    const MAX_RESULT_CHARS = 500;
    let recognition = null;
    let listening = false;
    let activeTarget = null;
    let insertedCharacters = 0;

    const COMMANDS = new Map([
        ["new line", "\n"],
        ["newline", "\n"],
        ["नई लाइन", "\n"],
        ["नवीन ओळ", "\n"],
        ["indent", "    "],
        ["tab", "    "],
        ["इंडेंट", "    "],
        ["टैब", "    "],
        ["टॅब", "    "],
        ["colon", ":"],
        ["कोलन", ":"],
        ["comma", ","],
        ["कॉमा", ","],
        ["स्वल्पविराम", ","],
        ["dot", "."],
        ["period", "."],
        ["open parenthesis", "("],
        ["close parenthesis", ")"],
        ["open bracket", "["],
        ["close bracket", "]"],
        ["open brace", "{"],
        ["close brace", "}"],
        ["equals", " = "],
        ["equal", " = "],
        ["बराबर", " = "],
        ["बरोबर", " = "],
        ["double equals", " == "],
        ["not equals", " != "],
        ["greater than", " > "],
        ["less than", " < "],
        ["arrow", " -> "],
        ["double quote", "\""],
        ["single quote", "'"],
        ["hash", "#"],
    ]);

    function element(id) {
        return document.getElementById(id);
    }

    function setStatus(message) {
        const output = element("voiceStatus");
        if (output) output.textContent = message;
    }

    function setTranscript(message) {
        const output = element("voiceTranscript");
        if (output) output.textContent = message;
    }

    function isWritableField(target) {
        if (!target) return false;
        if (target instanceof HTMLTextAreaElement) return !target.disabled && !target.readOnly;
        if (target instanceof HTMLInputElement) {
            const allowed = new Set(["text", "search", "url", "email"]);
            return allowed.has(target.type) && !target.disabled && !target.readOnly;
        }
        return target.isContentEditable;
    }

    function findTarget() {
        if (isWritableField(document.activeElement)) return document.activeElement;
        const main = element("main-content") || document;
        return Array.from(
            main.querySelectorAll(
                "#code, #chatInput, textarea, input[type='text'], " +
                "input[type='search'], [contenteditable='true']"
            )
        ).find(isWritableField) || null;
    }

    function targetName(target) {
        if (!target) return "";
        return (
            target.getAttribute("aria-label")
            || target.getAttribute("placeholder")
            || target.getAttribute("name")
            || target.id
            || "focused editor"
        );
    }

    function insertText(target, text) {
        if (!target || !text) return;
        if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
            const start = target.selectionStart ?? target.value.length;
            const end = target.selectionEnd ?? target.value.length;
            target.setRangeText(text, start, end, "end");
        } else if (target.isContentEditable) {
            target.focus();
            document.execCommand("insertText", false, text);
        }
        target.dispatchEvent(new Event("input", {bubbles: true}));
    }

    function normalizedResult(transcript) {
        return transcript
            .trim()
            .toLocaleLowerCase()
            .replace(/[.!?]+$/u, "");
    }

    function codeText(transcript) {
        const normalized = normalizedResult(transcript);
        if (COMMANDS.has(normalized)) return COMMANDS.get(normalized);
        return `${transcript.trim()} `;
    }

    function recognitionConstructor() {
        return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    function setListening(next) {
        listening = next;
        const start = element("voiceStartButton");
        const stop = element("voiceStopButton");
        if (start) start.disabled = next;
        if (stop) stop.disabled = !next;
        const toggle = element("voiceToggleButton");
        if (toggle) toggle.classList.toggle("is-listening", next);
    }

    function stopListening(message) {
        if (recognition && listening) recognition.stop();
        setListening(false);
        if (message) setStatus(message);
    }

    function startListening() {
        const Constructor = recognitionConstructor();
        if (!Constructor) {
            setStatus("Voice recognition is not supported by this browser.");
            return;
        }
        activeTarget = findTarget();
        if (!activeTarget) {
            setStatus("Focus a text, chat, problem, or code field before listening.");
            return;
        }
        const language = element("voiceLanguageSelect");
        recognition = new Constructor();
        recognition.lang = language ? language.value : "en-IN";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        insertedCharacters = 0;

        recognition.onstart = function () {
            setListening(true);
            setStatus(`Listening for ${targetName(activeTarget)}.`);
            setTranscript("");
        };
        recognition.onresult = function (event) {
            let interim = "";
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const result = event.results[index];
                const transcript = String(result[0].transcript || "")
                    .slice(0, MAX_RESULT_CHARS);
                if (!result.isFinal) {
                    interim += transcript;
                    continue;
                }
                const normalized = normalizedResult(transcript);
                if (
                    normalized === "stop listening"
                    || normalized === "सुनना बंद करो"
                    || normalized === "ऐकणे थांबवा"
                ) {
                    stopListening("Voice input stopped.");
                    return;
                }
                const insertion = codeText(transcript);
                if (insertedCharacters + insertion.length > MAX_TRANSCRIPT_CHARS) {
                    stopListening("Voice input stopped at the 4,000 character safety limit.");
                    return;
                }
                insertText(activeTarget, insertion);
                insertedCharacters += insertion.length;
            }
            setTranscript(interim.slice(0, MAX_RESULT_CHARS));
        };
        recognition.onerror = function (event) {
            setListening(false);
            const denied = event.error === "not-allowed" || event.error === "service-not-allowed";
            setStatus(
                denied
                    ? "Microphone permission was not granted."
                    : "Voice recognition stopped because the browser reported an error."
            );
        };
        recognition.onend = function () {
            setListening(false);
            setTranscript("");
            if (insertedCharacters) {
                setStatus(`Voice input stopped after inserting ${insertedCharacters} characters.`);
            }
        };
        try {
            recognition.start();
        } catch (error) {
            setListening(false);
            setStatus("Voice recognition could not start.");
        }
    }

    function setPanelOpen(open) {
        const panel = element("voicePanel");
        const toggle = element("voiceToggleButton");
        if (!panel || !toggle) return;
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        if (!open && listening) stopListening("Voice input stopped.");
        if (open) {
            document.dispatchEvent(
                new CustomEvent("codelabx:accessibility-panel", {detail: "voice"})
            );
            activeTarget = findTarget();
            const target = element("voiceTarget");
            if (target) {
                target.textContent = activeTarget
                    ? `Target: ${targetName(activeTarget)}`
                    : "Focus a text or code field before starting.";
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const panel = element("voicePanel");
        const toggle = element("voiceToggleButton");
        const close = element("voiceCloseButton");
        const start = element("voiceStartButton");
        const stop = element("voiceStopButton");
        const language = element("voiceLanguageSelect");
        if (!panel || !toggle || !close || !start || !stop || !language) return;

        const pageLanguage = (document.documentElement.lang || "en").toLowerCase();
        language.value = pageLanguage.startsWith("hi")
            ? "hi-IN"
            : pageLanguage.startsWith("mr") ? "mr-IN" : "en-IN";
        stop.disabled = true;
        if (!recognitionConstructor()) {
            start.disabled = true;
            setStatus("Voice recognition is not supported by this browser.");
        }

        toggle.addEventListener("click", function () {
            setPanelOpen(panel.hidden);
        });
        close.addEventListener("click", function () { setPanelOpen(false); });
        start.addEventListener("click", startListening);
        stop.addEventListener("click", function () {
            stopListening("Voice input stopped.");
        });
        document.addEventListener("focusin", function (event) {
            if (isWritableField(event.target)) activeTarget = event.target;
        });
        document.addEventListener("codelabx:accessibility-panel", function (event) {
            if (event.detail !== "voice" && !panel.hidden) setPanelOpen(false);
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !panel.hidden) setPanelOpen(false);
        });
        document.addEventListener("visibilitychange", function () {
            if (document.hidden && listening) stopListening("Voice input stopped.");
        });
        window.addEventListener("beforeunload", function () {
            if (recognition && listening) recognition.abort();
        });
    });
}());
