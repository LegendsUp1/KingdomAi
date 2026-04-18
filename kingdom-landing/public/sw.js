// Kingdom AI — SOTA 2026 Service Worker
// Cache-first for static assets, network-first for API, offline fallback
const CACHE_VERSION = 'kingdom-ai-v2';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/offline.html',
    '/manifest.json',
    '/icon.png',
    '/privacy.html'
];

// ─── INSTALL: Pre-cache static assets ───
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION)
            .then((cache) => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// ─── ACTIVATE: Clean old caches ───
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_VERSION)
                    .map((name) => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

// ─── FETCH: Cache-first for static, network-first for API ───
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip cross-origin requests (CDNs, analytics, etc.)
    if (url.origin !== location.origin) return;

    // Skip the APK download — too large to cache (94MB)
    if (url.pathname.startsWith('/downloads/')) return;

    // Cache-first for static assets (HTML, CSS, JS, images)
    event.respondWith(
        caches.match(request).then((cached) => {
            if (cached) {
                // Return cached, but also update cache in background (stale-while-revalidate)
                const fetchPromise = fetch(request).then((response) => {
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
                    }
                    return response;
                }).catch(() => cached);

                return cached;
            }

            // Not in cache — fetch from network
            return fetch(request).then((response) => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
                }
                return response;
            }).catch(() => {
                // Network failed, no cache — show offline page
                if (request.destination === 'document') {
                    return caches.match('/offline.html');
                }
                return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
            });
        })
    );
});
