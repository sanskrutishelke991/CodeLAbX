"use strict";

(function () {
    const MAX_SPEAK_CHARS = 12000;
    const CHUNK_SIZE = 220;
    let chunks = [];
    let chunkIndex = 0;
    let activeUtterance = null;
    let speechRun = 0;

    function element(id) {
        return document.getElementById(id);
    }

    function status(message) {
        const output = element("ttsStatus");
        if (output) output.textContent = message;
    }

    function storageGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function storageSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            return;
        }
    }

    function readableText() {
        const selection = window.getSelection();
        const selected = selection ? selection.toString().trim() : "";
        if (selected) return selected.slice(0, MAX_SPEAK_CHARS);

        const main = element("main-content");
        if (!main) return "";
        const clone = main.cloneNode(true);
        clone.querySelectorAll(
            "script, style, nav, form, button, input, textarea, select, " +
            "[data-tts-ignore], [aria-hidden='true']"
        ).forEach(function (node) {
            node.remove();
        });
        return (clone.textContent || "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, MAX_SPEAK_CHARS);
    }

    function splitText(text) {
        const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
        const output = [];
        sentences.forEach(function (sentence) {
            let remaining = sentence.trim();
            while (remaining.length > CHUNK_SIZE) {
                let cut = remaining.lastIndexOf(" ", CHUNK_SIZE);
                if (cut < Math.floor(CHUNK_SIZE / 2)) cut = CHUNK_SIZE;
                output.push(remaining.slice(0, cut).trim());
                remaining = remaining.slice(cut).trim();
            }
            if (remaining) output.push(remaining);
        });
        return output;
    }

    function selectedVoice() {
        const select = element("ttsVoiceSelect");
        const voices = window.speechSynthesis.getVoices();
        if (!select || !select.value) return null;
        return voices.find(function (voice) {
            return voice.voiceURI === select.value;
        }) || null;
    }

    function speakNext(run) {
        if (run !== speechRun) return;
        if (chunkIndex >= chunks.length) {
            activeUtterance = null;
            status("Finished reading.");
            return;
        }
        const utterance = new SpeechSynthesisUtterance(chunks[chunkIndex]);
        const voice = selectedVoice();
        const rate = element("ttsRateSelect");
        if (voice) utterance.voice = voice;
        utterance.rate = rate ? Number(rate.value) : 1;
        utterance.onend = function () {
            if (run !== speechRun) return;
            chunkIndex += 1;
            speakNext(run);
        };
        utterance.onerror = function () {
            if (run !== speechRun) return;
            activeUtterance = null;
            status("Reading stopped because the browser voice failed.");
        };
        activeUtterance = utterance;
        status(`Reading part ${chunkIndex + 1} of ${chunks.length}.`);
        window.speechSynthesis.speak(utterance);
    }

    function startReading() {
        if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
            status("Text-to-speech is not supported by this browser.");
            return;
        }
        const text = readableText();
        if (!text) {
            status("Select text or open a page with readable content first.");
            return;
        }
        speechRun += 1;
        const run = speechRun;
        window.speechSynthesis.cancel();
        chunks = splitText(text);
        chunkIndex = 0;
        speakNext(run);
    }

    function stopReading() {
        speechRun += 1;
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        chunks = [];
        chunkIndex = 0;
        activeUtterance = null;
        status("Reading stopped.");
        const pause = element("ttsPauseButton");
        if (pause) pause.textContent = "Pause";
    }

    function togglePause() {
        if (!("speechSynthesis" in window) || !activeUtterance) return;
        const button = element("ttsPauseButton");
        if (window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
            if (button) button.textContent = "Pause";
            status(`Reading part ${chunkIndex + 1} of ${chunks.length}.`);
        } else if (window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
            if (button) button.textContent = "Resume";
            status("Reading paused.");
        }
    }

    function populateVoices() {
        const select = element("ttsVoiceSelect");
        if (!select || !("speechSynthesis" in window)) return;
        const saved = storageGet("codelabx-tts-voice", "");
        const voices = window.speechSynthesis.getVoices()
            .slice()
            .sort(function (a, b) {
                return `${a.lang} ${a.name}`.localeCompare(`${b.lang} ${b.name}`);
            });
        select.replaceChildren();
        const automatic = document.createElement("option");
        automatic.value = "";
        automatic.textContent = "Browser default";
        select.appendChild(automatic);
        voices.forEach(function (voice) {
            const option = document.createElement("option");
            option.value = voice.voiceURI;
            option.textContent = `${voice.name} (${voice.lang})`;
            option.selected = voice.voiceURI === saved;
            select.appendChild(option);
        });
    }

    function setPanelOpen(open) {
        const panel = element("ttsPanel");
        const toggle = element("ttsToggleButton");
        if (!panel || !toggle) return;
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        if (open) {
            populateVoices();
            status(
                "Select text to read only that selection, or read the main page content."
            );
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const toggle = element("ttsToggleButton");
        const panel = element("ttsPanel");
        const close = element("ttsCloseButton");
        const play = element("ttsPlayButton");
        const pause = element("ttsPauseButton");
        const stop = element("ttsStopButton");
        const voice = element("ttsVoiceSelect");
        const rate = element("ttsRateSelect");
        if (!toggle || !panel || !close || !play || !pause || !stop) return;

        if (rate) rate.value = storageGet("codelabx-tts-rate", "1");
        populateVoices();
        if ("speechSynthesis" in window) {
            if (typeof window.speechSynthesis.addEventListener === "function") {
                window.speechSynthesis.addEventListener(
                    "voiceschanged",
                    populateVoices,
                );
            } else {
                window.speechSynthesis.onvoiceschanged = populateVoices;
            }
        }

        toggle.addEventListener("click", function () {
            setPanelOpen(panel.hidden);
        });
        close.addEventListener("click", function () { setPanelOpen(false); });
        play.addEventListener("click", startReading);
        pause.addEventListener("click", togglePause);
        stop.addEventListener("click", stopReading);
        if (voice) {
            voice.addEventListener("change", function () {
                storageSet("codelabx-tts-voice", voice.value);
            });
        }
        if (rate) {
            rate.addEventListener("change", function () {
                storageSet("codelabx-tts-rate", rate.value);
            });
        }
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !panel.hidden) setPanelOpen(false);
        });
        window.addEventListener("beforeunload", stopReading);
    });
}());
