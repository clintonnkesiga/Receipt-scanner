/// <reference types="@sveltejs/kit" />
// App-shell service worker. SvelteKit auto-registers this in production builds.
// Strategy:
//   • precache the built JS/CSS + static files, serve them cache-first
//   • never cache /api or /uploads (auth'd data + images) — always the network
//   • navigations: network-first, falling back to cache so previously visited
//     pages still open offline (OCR/scan still needs connectivity).
import { build, files, version } from "$service-worker";

const CACHE = `receipt-scanner-${version}`;
const PRECACHE = [...build, ...files];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  // Always go to the network for the API and stored images.
  if (sameOrigin && (url.pathname.startsWith("/api") || url.pathname.startsWith("/uploads"))) {
    return;
  }

  // Immutable build assets + static files: cache-first.
  if (sameOrigin && PRECACHE.includes(url.pathname)) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(url.pathname).then((hit) => hit || fetch(request)),
      ),
    );
    return;
  }

  // Navigations (and other same-origin GETs): network-first, cache as we go,
  // fall back to the cache when offline.
  if (request.mode === "navigate" || sameOrigin) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok && sameOrigin) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          return cached || caches.match("/");
        }),
    );
  }
});
