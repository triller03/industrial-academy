// ASAPA — Industrial Automation Training Platform — service worker
// Caches the app shell so the UI loads with no network. API calls are never cached;
// content for offline study comes from IndexedDB bundles instead.
const CACHE = "academy-shell-v7";
const SHELL = [
  "/",
  "/index.html",
  "/css/styles.css",
  "/js/offline.js",
  "/js/app.js",
  "/logo.png",
  "/favicon.ico",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // Never cache or intercept the API — offline work is queued client-side.
  if (url.pathname.startsWith("/api")) return;

  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || caches.match("/index.html"))
      )
  );
});
