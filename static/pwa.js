(function () {
  'use strict';

  const ASSET_VERSION = String(window.__assetVersion || '');
  const SW_URL = '/sw.js' + (ASSET_VERSION ? ('?v=' + encodeURIComponent(ASSET_VERSION)) : '');
  let hasReloadedOnController = false;
  let deferredPrompt = null;

  function mediaMatches(query) {
    try {
      return !!(window.matchMedia && window.matchMedia(query).matches);
    } catch (e) {
      return false;
    }
  }

  function readConnectionProfile() {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const effectiveType = String((c && c.effectiveType) || '').toLowerCase();
    const saveData = !!(c && c.saveData);
    const slowByType = ['slow-2g', '2g', '3g'].includes(effectiveType);
    const offline = navigator.onLine === false;
    return {
      effectiveType,
      saveData,
      offline,
      slow: offline || saveData || slowByType,
      reducedMotion: mediaMatches('(prefers-reduced-motion: reduce)'),
      coarsePointer: mediaMatches('(pointer: coarse)'),
      smallScreen: mediaMatches('(max-width: 768px)'),
    };
  }

  function updateNetworkPill(profile) {
    const pill = document.getElementById('networkPill');
    const text = document.getElementById('networkPillText');
    if (!pill || !text) return;

    let message = '';
    if (profile.offline) {
      message = 'Hors ligne';
    } else if (profile.slow) {
      message = profile.saveData ? 'Mode economie de donnees' : 'Connexion lente';
    }

    if (!message) {
      pill.hidden = true;
      return;
    }

    text.textContent = message;
    pill.hidden = false;
  }

  function applyConnectionClass() {
    const profile = readConnectionProfile();
    window.__bfNetworkProfile = profile;
    const targets = [document.documentElement, document.body].filter(Boolean);
    targets.forEach((node) => {
      node.classList.toggle('network-saver', profile.slow);
      node.classList.toggle('offline', profile.offline);
      node.classList.toggle('reduced-motion', profile.reducedMotion);
      node.classList.toggle('touch-ui', profile.coarsePointer || profile.smallScreen);
    });
    updateNetworkPill(profile);
    try {
      window.dispatchEvent(new CustomEvent('bf:network-change', { detail: profile }));
    } catch (e) {}
    return profile;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyConnectionClass, { once: true });
  } else {
    applyConnectionClass();
  }

  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (connection && typeof connection.addEventListener === 'function') {
    connection.addEventListener('change', applyConnectionClass);
  }
  window.addEventListener('online', applyConnectionClass);
  window.addEventListener('offline', applyConnectionClass);

  const reducedMotionMq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  if (reducedMotionMq) {
    if (typeof reducedMotionMq.addEventListener === 'function') {
      reducedMotionMq.addEventListener('change', applyConnectionClass);
    } else if (typeof reducedMotionMq.addListener === 'function') {
      reducedMotionMq.addListener(applyConnectionClass);
    }
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (hasReloadedOnController) return;
      hasReloadedOnController = true;
      location.reload();
    });

    const registerServiceWorker = () => {
      navigator.serviceWorker.register(SW_URL, { scope: '/' })
        .then((reg) => {
          if (reg.waiting) showUpdateToast(reg.waiting);
          reg.addEventListener('updatefound', () => {
            const w = reg.installing;
            if (!w) return;
            w.addEventListener('statechange', () => {
              if (w.state === 'installed' && navigator.serviceWorker.controller) {
                showUpdateToast(w);
              }
            });
          });
        })
        .catch(() => {});
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', registerServiceWorker, { once: true });
    } else {
      registerServiceWorker();
    }
  }

  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone = window.navigator.standalone === true
    || window.matchMedia('(display-mode: standalone)').matches;

  if (!isStandalone) {
    function showInstallButton() {
      const btn = document.getElementById('pwa-install-trigger');
      if (btn) btn.style.display = 'block';
    }

    window.triggerPwaInstall = function () {
      if (isIos) {
        showIosModal();
      } else if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => { deferredPrompt = null; });
      } else {
        showIosModal();
      }
    };

    if (isIos) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', showInstallButton);
      } else {
        showInstallButton();
      }
    }

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      showInstallButton();

      const net = window.__bfNetworkProfile || readConnectionProfile();
      if (net.slow) return;

      let dismissed = null;
      try { dismissed = localStorage.getItem('pwa_dismissed'); } catch(e) {}
      if (!dismissed || Date.now() - parseInt(dismissed, 10) > 7 * 24 * 3600 * 1000) {
        setTimeout(showInstallBanner, 3000);
      }
    });

    function showIosModal() {
      if (document.getElementById('ios-pwa-modal')) return;

      const overlay = document.createElement('div');
      overlay.id = 'ios-pwa-modal';
      overlay.style.cssText = 'position:fixed;inset:0;z-index:999999;background:rgba(0,0,0,0.8);display:flex;align-items:flex-end;padding:1rem;box-sizing:border-box;';

      overlay.innerHTML = `
        <div style="background:#1c1c1e;border-radius:16px;width:100%;padding:1.5rem;box-sizing:border-box;border:1px solid rgba(205,127,50,0.35);">
          <div style="text-align:center;margin-bottom:1.25rem;">
            <div style="font-size:2.5rem;margin-bottom:0.4rem;">📲</div>
            <div style="font-size:1.05rem;font-weight:700;color:#f5f5f5;">Ajouter a l'ecran d'accueil</div>
            <div style="font-size:0.82rem;color:#888;margin-top:0.25rem;">Fonctionne uniquement dans Safari</div>
          </div>

          <div style="background:rgba(255,255,255,0.06);border-radius:12px;padding:1rem;display:flex;flex-direction:column;gap:0.85rem;margin-bottom:1.25rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;">
              <span style="font-size:1.4rem;flex-shrink:0;">1️⃣</span>
              <span style="color:#f5f5f5;font-size:0.9rem;">Appuie sur <strong style="color:#cd7f32;">Partager</strong> ⬆️ en bas de Safari</span>
            </div>
            <div style="display:flex;align-items:center;gap:0.75rem;">
              <span style="font-size:1.4rem;flex-shrink:0;">2️⃣</span>
              <span style="color:#f5f5f5;font-size:0.9rem;">Defile et appuie sur <strong style="color:#cd7f32;">Sur l'ecran d'accueil</strong></span>
            </div>
            <div style="display:flex;align-items:center;gap:0.75rem;">
              <span style="font-size:1.4rem;flex-shrink:0;">3️⃣</span>
              <span style="color:#f5f5f5;font-size:0.9rem;">Appuie sur <strong style="color:#cd7f32;">Ajouter</strong> en haut a droite</span>
            </div>
          </div>

          <button onclick="document.getElementById('ios-pwa-modal').remove()" style="-webkit-appearance:none;appearance:none;width:100%;padding:0.85rem;border-radius:12px;border:none;background:linear-gradient(135deg,#cd7f32,#b8732f);color:#fff;font-weight:700;font-size:1rem;cursor:pointer;">
            J'ai compris
          </button>
        </div>
      `;

      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
      document.body.appendChild(overlay);
    }

    function showInstallBanner() {
      if (!deferredPrompt || document.getElementById('pwa-banner')) return;

      const banner = document.createElement('div');
      banner.id = 'pwa-banner';
      banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;background:linear-gradient(135deg,#1a1a1a,#111);border-top:1px solid rgba(205,127,50,0.4);padding:1rem 1.25rem calc(1rem + env(safe-area-inset-bottom, 0px));display:flex;align-items:center;gap:1rem;box-shadow:0 -4px 24px rgba(0,0,0,0.5);';
      banner.innerHTML = `
        <img src="/static/images/logo.svg" style="width:36px;height:36px;flex-shrink:0" alt="">
        <div style="flex:1;min-width:0;">
          <div style="font-weight:700;color:#f5f5f5;font-size:0.9rem;">Installer l'app</div>
          <div style="color:#888;font-size:0.78rem;">Acces rapide depuis l'ecran d'accueil</div>
        </div>
        <button id="pwa-do-install" style="-webkit-appearance:none;background:linear-gradient(135deg,#cd7f32,#b8732f);color:#fff;border:none;padding:0.6rem 1rem;border-radius:8px;font-weight:700;font-size:0.875rem;cursor:pointer;flex-shrink:0;">Installer</button>
        <button id="pwa-do-dismiss" style="-webkit-appearance:none;background:transparent;border:none;color:#666;font-size:1.25rem;cursor:pointer;padding:0.25rem;flex-shrink:0;">✕</button>
      `;
      document.body.appendChild(banner);

      document.getElementById('pwa-do-install').addEventListener('click', () => {
        banner.remove();
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => { deferredPrompt = null; });
      });
      document.getElementById('pwa-do-dismiss').addEventListener('click', () => {
        banner.remove();
        try { localStorage.setItem('pwa_dismissed', Date.now().toString()); } catch(e) {}
      });
    }
  }

  function showUpdateToast(waitingWorker) {
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;top:calc(80px + env(safe-area-inset-top, 0px));left:50%;transform:translateX(-50%);z-index:99999;background:#1a1a1a;border:1px solid rgba(205,127,50,0.4);border-radius:10px;padding:0.75rem 1.25rem;display:flex;align-items:center;gap:0.75rem;box-shadow:0 4px 20px rgba(0,0,0,0.5);white-space:nowrap;';
    t.innerHTML = `<span style="font-size:0.875rem;color:#f5f5f5">Nouvelle version disponible</span><button id="pwa-refresh-now" style="-webkit-appearance:none;background:#cd7f32;color:#fff;border:none;padding:0.35rem 0.85rem;border-radius:6px;font-size:0.8125rem;font-weight:700;cursor:pointer;">Recharger</button>`;
    document.body.appendChild(t);

    const btn = t.querySelector('#pwa-refresh-now');
    if (btn) {
      btn.addEventListener('click', () => {
        if (waitingWorker && typeof waitingWorker.postMessage === 'function') {
          waitingWorker.postMessage({ type: 'SKIP_WAITING' });
        } else {
          location.reload();
        }
      });
    }

    setTimeout(() => t.remove(), 10000);
  }

  function ensureReconnectBanner() {
    let banner = document.getElementById('reconnect-banner');
    if (banner) return banner;

    banner = document.createElement('div');
    banner.id = 'reconnect-banner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:rgba(231,76,60,0.95);color:#fff;text-align:center;padding:0.7rem 1rem;font-size:0.8125rem;font-weight:700;letter-spacing:0.03em;transform:translateY(-115%);opacity:0;transition:transform 0.3s ease,opacity 0.3s ease;';
    banner.textContent = 'Connexion perdue - Reconnexion en cours...';
    document.body.appendChild(banner);
    return banner;
  }

  function setReconnectBannerState(banner, state) {
    if (!banner) return;
    if (state === 'hidden') {
      banner.style.transform = 'translateY(-115%)';
      banner.style.opacity = '0';
      return;
    }

    if (state === 'offline') {
      banner.textContent = 'Hors ligne - tentative de reconnexion automatique';
      banner.style.background = 'rgba(231,76,60,0.95)';
    } else if (state === 'restored') {
      banner.textContent = 'Connexion retablie';
      banner.style.background = 'rgba(39,174,96,0.95)';
    } else {
      banner.textContent = 'Connexion instable - Reconnexion en cours...';
      banner.style.background = 'rgba(205,127,50,0.96)';
    }

    banner.style.transform = 'translateY(0)';
    banner.style.opacity = '1';
  }

  function initReconnectIndicator(socket) {
    if (!socket || typeof socket.on !== 'function') return;
    if (socket.__bfReconnectIndicatorBound) return;
    socket.__bfReconnectIndicatorBound = true;

    const banner = ensureReconnectBanner();
    let hideTimer = null;
    const hideSoon = () => {
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => setReconnectBannerState(banner, 'hidden'), 1600);
    };

    socket.on('disconnect', () => {
      setReconnectBannerState(banner, navigator.onLine === false ? 'offline' : 'reconnecting');
    });
    socket.on('connect', () => {
      setReconnectBannerState(banner, 'restored');
      hideSoon();
    });
    socket.on('reconnect', () => {
      setReconnectBannerState(banner, 'restored');
      hideSoon();
    });

    window.addEventListener('offline', () => {
      setReconnectBannerState(banner, 'offline');
    });

    window.addEventListener('online', () => {
      if (socket.connected) {
        setReconnectBannerState(banner, 'restored');
        hideSoon();
      } else {
        setReconnectBannerState(banner, 'reconnecting');
      }
    });
  }

  window.applyConnectionClass = applyConnectionClass;
  window.initReconnectIndicator = initReconnectIndicator;
})();
