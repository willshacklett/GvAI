const CACHE_NAME = "gvai-pwa-v6";
const ASSETS = [
  "./",
  "./index.html",
  "./fetch.js",
  "./gv-carl-logo.svg",
  "./style.css",
  "./dashboard.js?v=voice2",
  "./manifest.json"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const req = event.request;

  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(req).catch(() =>
      caches.match(req).then(cached => cached || caches.match("./index.html"))
    )
  );
});
