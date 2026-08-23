"use strict";

const SHELL_CACHE = "codelabx-public-shell-v1";
const STATIC_CACHE = "codelabx-static-v1";
const PUBLIC_SHELL = [
    "/offline/",
    "/static/manifest.webmanifest",
    "/static/icons/pwa-180.png",
    "/static/icons/pwa-192.png",
    "/static/icons/pwa-512.png",
    "/static/vendor/bootstrap/bootstrap.min.css",
    "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
    "/static/css/style.css",
    "/static/css/base.css",
    "/static/css/pwa-accessibility.css",
    "/static/js/main.js",
    "/static/js/base.js",
    "/static/js/pwa.js",
    "/static/js/tts.js",
    "/static/js/offline.js"
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(SHELL_CACHE).then(function (cache) {
            return cache.addAll(PUBLIC_SHELL);
        }).then(function () {
            return self.skipWaiting();
        })
    );
});

self.addEventListener("activate", function (event) {
    const allowed = new Set([SHELL_CACHE, STATIC_CACHE]);
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (key) {
                    return key.startsWith("codelabx-") && !allowed.has(key);
                }).map(function (key) {
                    return caches.delete(key);
                })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

self.addEventListener("message", function (event) {
    if (event.data === "SKIP_WAITING") {
        self.skipWaiting();
    }
});

self.addEventListener("fetch", function (event) {
    const request = event.request;
    if (request.method !== "GET") return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request, {cache: "no-store"}).catch(function () {
                return caches.match("/offline/");
            })
        );
        return;
    }

    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then(function (cached) {
                if (cached) return cached;
                return fetch(request).then(function (response) {
                    if (!response || !response.ok || response.type !== "basic") {
                        return response;
                    }
                    const copy = response.clone();
                    caches.open(STATIC_CACHE).then(function (cache) {
                        cache.put(request, copy);
                    });
                    return response;
                });
            })
        );
    }
});
