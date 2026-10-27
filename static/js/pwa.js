"use strict";

(function () {
    let deferredInstallPrompt = null;

    function installButton() {
        return document.getElementById("pwaInstallButton");
    }

    function setInstallAvailable(available) {
        const button = installButton();
        if (!button) return;
        button.hidden = !available;
        button.setAttribute("aria-hidden", String(!available));
    }

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredInstallPrompt = event;
        setInstallAvailable(true);
    });

    window.addEventListener("appinstalled", function () {
        deferredInstallPrompt = null;
        setInstallAvailable(false);
    });

    document.addEventListener("DOMContentLoaded", function () {
        const button = installButton();
        if (button) {
            button.addEventListener("click", async function () {
                if (!deferredInstallPrompt) return;
                button.disabled = true;
                try {
                    await deferredInstallPrompt.prompt();
                    await deferredInstallPrompt.userChoice;
                } finally {
                    deferredInstallPrompt = null;
                    button.disabled = false;
                    setInstallAvailable(false);
                }
            });
        }

        if (!("serviceWorker" in navigator)) return;
        navigator.serviceWorker.register("/service-worker.js", {scope: "/"})
            .catch(function () {
                setInstallAvailable(false);
            });
    });
}());
