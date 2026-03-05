// Service Worker - Baby-Foot Club
// Optimise mobile et connexions lentes (cache statique + runtime robuste).

const STATIC_CACHE = 'babyfoot-static-v47';
const RUNTIME_CACHE = 'babyfoot-runtime-v47';

const STATIC_ASSETS = [
  '/static/design-v3.css',
  '/static/icons.js',
  '/static/profile-utils.js',
  '/static/theme-manager.js',
  '/static/pwa.js',
  '/static/particles-bg.js',
  '/static/main.js',
  '/static/manifest.json',
  '/static/images/logo.svg',
  '/static/socket.io.min.js',
];

const PUBLIC_DYNAMIC_PATHS = [
  '/leaderboard',
  '/reservations',
  '/scores_all',
  '/api/public_stats',
];

const CACHEABLE_API_PREFIXES = [
  '/api/avatar/',
];

const SENSITIVE_PATH_PREFIXES = [
  '/api/',
  '/current_user',
];

const STATIC_CDN_HOSTS = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'cdnjs.cloudflare.com',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(STATIC_CACHE);
    await Promise.allSettled(STATIC_ASSETS.map((url) => cache.add(url)));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((k) => k.startsWith('babyfoot-') && k !== STATIC_CACHE && k !== RUNTIME_CACHE)
        .map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (!request || request.method !== 'GET') return;
  if (request.cache === 'only-if-cached' && request.mode !== 'same-origin') return;

  const url = new URL(request.url);

  // Extensions / schémas non HTTP(S)
  if (!url.protocol.startsWith('http')) return;

  // Temps reel Socket.IO: ne pas intercepter
  if (url.pathname.startsWith('/socket.io')) return;

  // Endpoints dynamiques publics: réseau d'abord + cache runtime
  if (PUBLIC_DYNAMIC_PATHS.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(networkFirst(request, {
      cacheName: RUNTIME_CACHE,
      timeoutMs: 6500,
      fallbackToOfflinePage: false,
    }));
    return;
  }

  // APIs media cacheables (ex: avatars)
  if (CACHEABLE_API_PREFIXES.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(staleWhileRevalidate(request, RUNTIME_CACHE));
    return;
  }

  // API sensible: réseau uniquement, pas de cache
  if (SENSITIVE_PATH_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(networkOnly(request, 6500));
    return;
  }

  // Navigation HTML: réseau d'abord, fallback cache puis page hors-ligne
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, {
      cacheName: RUNTIME_CACHE,
      timeoutMs: 6500,
      fallbackToOfflinePage: true,
    }));
    return;
  }

  const isSameOriginStatic = url.origin === self.location.origin && url.pathname.startsWith('/static/');
  const isStaticCdn = STATIC_CDN_HOSTS.some((host) => url.hostname.includes(host));

  // Statiques: stale-while-revalidate
  if (isSameOriginStatic || isStaticCdn) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }
});

async function fetchWithTimeout(request, timeoutMs) {
  if (typeof AbortController === 'undefined') {
    return fetch(request);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(request, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function shouldCacheResponse(response) {
  if (!response) return false;
  const cacheControl = String(response.headers.get('Cache-Control') || '').toLowerCase();
  if (cacheControl.includes('no-store')) return false;
  return response.ok || response.type === 'opaque';
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const networkPromise = fetch(request)
    .then((response) => {
      if (shouldCacheResponse(response)) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cached) return cached;

  const network = await networkPromise;
  if (network) return network;

  return new Response('Ressource indisponible hors ligne', { status: 503 });
}

async function networkOnly(request, timeoutMs) {
  try {
    return await fetchWithTimeout(request, timeoutMs || 6500);
  } catch {
    return new Response(JSON.stringify({
      success: false,
      offline: true,
      message: 'Connexion indisponible',
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

async function networkFirst(request, options) {
  const opts = options || {};
  const cacheName = opts.cacheName || RUNTIME_CACHE;
  const timeoutMs = opts.timeoutMs || 6500;
  const fallbackToOfflinePage = !!opts.fallbackToOfflinePage;

  try {
    const response = await fetchWithTimeout(request, timeoutMs);
    if (request.method === 'GET' && shouldCacheResponse(response)) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (fallbackToOfflinePage) return offlineHtmlResponse();
    return new Response('', { status: 503 });
  }
}

function offlineHtmlResponse() {
  return new Response(`<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hors ligne - Baby-Foot Club</title>
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f111a;color:#f5f5f5;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:1rem;text-align:center}
    .box{max-width:420px;padding:1.25rem;border-radius:14px;background:#171a24;border:1px solid rgba(205,127,50,.28)}
    h1{color:#cd7f32;font-size:1.35rem;margin:.35rem 0 .6rem}
    p{color:#9aa4b2;font-size:.92rem;line-height:1.5;margin:0 0 1rem}
    button{background:linear-gradient(135deg,#cd7f32,#b8732f);color:#fff;border:none;padding:.78rem 1.3rem;
           border-radius:10px;font-size:.96rem;font-weight:700;cursor:pointer}
  </style>
</head>
<body>
  <div class="box">
    <div style="font-size:2.1rem">📶</div>
    <h1>Connexion indisponible</h1>
    <p>Le serveur est temporairement inaccessible. Verifie ton reseau puis reessaie.</p>
    <button id="retryBtn">Reessayer</button>
  </div>
  <script>
    const retry = document.getElementById('retryBtn');
    if (retry) retry.addEventListener('click', () => location.reload());
  </script>
</body>
</html>`, { headers: { 'Content-Type': 'text/html; charset=UTF-8' } });
}
