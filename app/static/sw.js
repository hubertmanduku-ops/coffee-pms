// CPMS service worker
// Strategy:
//  - Pages (navigation requests): network-first, so operational data is always fresh when
//    online; falls back to a cached "offline" page only when there is no connectivity at all.
//  - Static assets under /static/: cache-first, since CSS/icons/manifest rarely change.
//  - Everything else (form POSTs, third-party CDN requests): left untouched, normal browser fetch.
//
// Bump CACHE_VERSION whenever static assets change, so old caches get cleared out on the
// next visit.
const CACHE_VERSION = "cpms-v1";
const APP_SHELL = [
  "/static/css/style.css",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.mode === "navigate") {
    // Page load — always prefer the live server response so nobody sees stale
    // operational data. Only touch the cache when the network is unreachable.
    event.respondWith(
      fetch(request).catch(() => caches.match("/static/offline.html"))
    );
    return;
  }

  if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    // Static assets — cache-first, refresh the cache in the background.
    event.respondWith(
      caches.match(request).then((cached) => {
        const networkFetch = fetch(request)
          .then((response) => {
            if (response && response.ok) {
              caches.open(CACHE_VERSION).then((cache) => cache.put(request, response.clone()));
            }
            return response;
          })
          .catch(() => cached);
        return cached || networkFetch;
      })
    );
  }
  // All other requests (form submissions, CDN assets, etc.) are left to the browser's
  // default handling.
});
