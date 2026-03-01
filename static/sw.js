// ── Service Worker — Baby-Foot Club ──────────────────────────
// Met en cache les ressources statiques pour fonctionner
// même avec une connexion faible ou intermittente.

const CACHE_NAME = 'babyfoot-v30';

// Ressources mises en cache au premier chargement (shell de l'app)
const STATIC_ASSETS = [
  '/static/style.css',
  '/static/style-extended.css',
  '/static/responsive-mobile.css',
  '/static/dashboard-styles.css',
  '/static/lobby-styles.css',
  '/static/live-score-styles.css',
  '/static/global-animations.css',
  '/static/global-animations.js',
  '/static/animations.js',
  '/static/icons.js',
  '/static/confetti.js',
  '/static/images/logo.svg',
];

// ── Installation : mise en cache initiale ─────────────────────
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// ── Activation : nettoyage des vieux caches ───────────────────
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch : stratégie selon le type de ressource ─────────────
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Socket.IO : jamais intercepté (temps réel)
  if (url.pathname.startsWith('/socket.io')) return;

  // API dynamique : réseau d'abord, fallback cache si dispo
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/current_user') ||
    url.pathname.startsWith('/leaderboard') ||
    url.pathname.startsWith('/reservations') ||
    url.pathname.startsWith('/user_stats') ||
    url.pathname.startsWith('/scores_all')
  ) {
    e.respondWith(networkFirst(e.request));
    return;
  }

  // Pages HTML : réseau d'abord, fallback sur cache
  if (e.request.mode === 'navigate') {
    e.respondWith(networkFirst(e.request));
    return;
  }

  // Socket.IO CDN : jamais en cache, toujours réseau
  if (url.hostname.includes('cdn.socket.io')) return;

  // Ressources statiques (CSS, JS, images) : cache d'abord
  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('fonts.googleapis') ||
    url.hostname.includes('fonts.gstatic') ||
    url.hostname.includes('cdnjs.cloudflare')
  ) {
    e.respondWith(cacheFirst(e.request));
    return;
  }
});

// ── Stratégie : Cache d'abord (statique) ─────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Ressource non disponible hors ligne', { status: 503 });
  }
}

// ── Stratégie : Réseau d'abord (dynamique) ───────────────────
async function networkFirst(request) {
  try {
    const response = await fetch(request, { signal: AbortSignal.timeout(8000) });
    if (response.ok && request.method === 'GET') {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // Fallback offline pour les pages HTML
    if (request.mode === 'navigate') {
      return new Response(`
        <!DOCTYPE html><html lang="fr"><head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Hors ligne — Baby-Foot Club</title>
        <style>
          body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#f5f5f5;
               display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:1rem;text-align:center}
          h1{color:#cd7f32;font-size:1.5rem;margin-bottom:0.5rem}
          p{color:#888;font-size:0.9375rem;margin-bottom:1.5rem}
          button{background:#cd7f32;color:white;border:none;padding:0.875rem 2rem;
                 border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer;-webkit-appearance:none}
        </style></head><body>
        <div>
          <div style="font-size:3rem;margin-bottom:1rem">📡</div>
          <h1>Pas de connexion</h1>
          <p>Impossible de joindre le serveur.<br>Vérifie ta connexion Wi-Fi ou réseau.</p>
          <button onclick="location.reload()">Réessayer</button>
        </div>
        </body></html>
      `, { headers: { 'Content-Type': 'text/html' } });
    }
    return new Response('', { status: 503 });
  }
}
