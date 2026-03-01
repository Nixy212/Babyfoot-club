(function() {
  'use strict';

  // ── Animations flottantes ──────────────────────────────────────────────────
  function createFloatingShapes() {
    if (document.querySelector('.floating-shapes-global')) return;
    const container = document.createElement('div');
    container.className = 'floating-shapes-global';
    for (let i = 1; i <= 5; i++) {
      const shape = document.createElement('div');
      shape.className = `floating-shape-global shape-global-${i}`;
      container.appendChild(shape);
    }
    document.body.insertBefore(container, document.body.firstChild);
  }

  function createGlowPulse() {
    if (document.querySelector('.glow-pulse-global')) return;
    const glow = document.createElement('div');
    glow.className = 'glow-pulse-global';
    document.body.insertBefore(glow, document.body.firstChild);
  }

  // ── Styles notifications globales ─────────────────────────────────────────
  function injectNotifStyles() {
    if (document.getElementById('global-notif-styles')) return;
    const style = document.createElement('style');
    style.id = 'global-notif-styles';
    style.textContent = `
      #global-notif-bar {
        position: fixed;
        top: 70px;
        right: 20px;
        max-width: 420px;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        pointer-events: none;
      }
      .g-notif {
        background: #1a1a1a;
        border: 1px solid rgba(205,127,50,0.4);
        border-left: 3px solid #cd7f32;
        padding: 1rem 1.25rem;
        border-radius: 10px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        gap: 0.875rem;
        pointer-events: all;
        animation: gnotif-in 0.35s cubic-bezier(0.34,1.56,0.64,1);
        color: #e8e8e8;
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.9rem;
      }
      .g-notif.g-notif-out {
        animation: gnotif-out 0.25s ease forwards;
      }
      .g-notif.g-join-req {
        border-left-color: #3498db;
        border-color: rgba(52,152,219,0.4);
      }
      @keyframes gnotif-in {
        from { transform: translateX(440px); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
      @keyframes gnotif-out {
        from { transform: translateX(0);    opacity: 1; max-height: 120px; }
        to   { transform: translateX(440px); opacity: 0; max-height: 0; }
      }
      .g-notif-text { flex: 1; line-height: 1.4; }
      .g-notif-text strong { color: #cd7f32; }
      .g-notif-btns { display: flex; gap: 0.4rem; flex-shrink: 0; }
      .g-btn-accept {
        padding: 0.45rem 1rem;
        border: none;
        border-radius: 6px;
        background: linear-gradient(135deg, #cd7f32, #ffd700);
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
        cursor: pointer;
        transition: transform 0.15s, box-shadow 0.15s;
      }
      .g-btn-accept:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(205,127,50,0.5); }
      .g-btn-decline {
        padding: 0.45rem 1rem;
        border: none;
        border-radius: 6px;
        background: rgba(231,76,60,0.15);
        border: 1px solid rgba(231,76,60,0.4);
        color: #e74c3c;
        font-weight: 700;
        font-size: 0.85rem;
        cursor: pointer;
        transition: transform 0.15s;
      }
      .g-btn-decline:hover { transform: translateY(-2px); background: rgba(231,76,60,0.3); }
    `;
    document.head.appendChild(style);
  }

  // ── Barre de notifications globale ────────────────────────────────────────
  function getNotifBar() {
    let bar = document.getElementById('global-notif-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'global-notif-bar';
      document.body.appendChild(bar);
    }
    return bar;
  }

  function dismissNotif(el) {
    el.classList.add('g-notif-out');
    setTimeout(() => el.remove(), 280);
  }

  function autoClose(el, delay) {
    return setTimeout(() => dismissNotif(el), delay);
  }

  // ── Invitation reçue ──────────────────────────────────────────────────────
  window._globalShowLobbyInvite = function(data, socket) {
    const bar = getNotifBar();
    const notif = document.createElement('div');
    notif.className = 'g-notif';
    notif.innerHTML = `
      <div class="g-notif-text">
        <strong>${data.from}</strong> vous invite à jouer
        <div style="font-size:0.78rem;color:#888;margin-top:2px">Invitation au lobby</div>
      </div>
      <div class="g-notif-btns">
        <button class="g-btn-accept">✓ Rejoindre</button>
        <button class="g-btn-decline">✕</button>
      </div>
    `;
    const timer = autoClose(notif, 15000);
    notif.querySelector('.g-btn-accept').onclick = () => {
      clearTimeout(timer);
      socket.emit('accept_lobby');
      dismissNotif(notif);
      setTimeout(() => location.href = '/lobby', 400);
    };
    notif.querySelector('.g-btn-decline').onclick = () => {
      clearTimeout(timer);
      socket.emit('decline_lobby');
      dismissNotif(notif);
    };
    bar.appendChild(notif);
  };

  // ── Demande rejoindre lobby ───────────────────────────────────────────────
  window._globalShowJoinRequest = function(data, socket) {
    const bar = getNotifBar();
    const notif = document.createElement('div');
    notif.className = 'g-notif g-join-req';
    notif.innerHTML = `
      <div class="g-notif-text">
        <strong style="color:#3498db">${data.from}</strong> veut rejoindre votre lobby
        <div style="font-size:0.78rem;color:#888;margin-top:2px">Demande d'accès</div>
      </div>
      <div class="g-notif-btns">
        <button class="g-btn-accept" style="background:linear-gradient(135deg,#2980b9,#3498db)">✓ Accepter</button>
        <button class="g-btn-decline">✕ Refuser</button>
      </div>
    `;
    const timer = autoClose(notif, 20000);
    notif.querySelector('.g-btn-accept').onclick = () => {
      clearTimeout(timer);
      socket.emit('accept_join_request', { from: data.from, request_id: data.request_id });
      dismissNotif(notif);
    };
    notif.querySelector('.g-btn-decline').onclick = () => {
      clearTimeout(timer);
      socket.emit('decline_join_request', { from: data.from, request_id: data.request_id });
      dismissNotif(notif);
    };
    bar.appendChild(notif);
  };

  // ── Résultat demande ──────────────────────────────────────────────────────
  window._globalShowJoinResult = function(accepted, hostName) {
    const bar = getNotifBar();
    const notif = document.createElement('div');
    notif.className = 'g-notif';
    notif.style.borderLeftColor = accepted ? '#27ae60' : '#e74c3c';
    notif.style.borderColor = accepted ? 'rgba(39,174,96,0.4)' : 'rgba(231,76,60,0.4)';
    notif.innerHTML = `
      <div class="g-notif-text">
        ${accepted
          ? `<strong style="color:#27ae60">✓ Demande acceptée</strong> par <strong>${hostName}</strong><div style="font-size:0.78rem;color:#888;margin-top:2px">Redirection vers le lobby…</div>`
          : `<strong style="color:#e74c3c">✕ Demande refusée</strong> par <strong>${hostName}</strong><div style="font-size:0.78rem;color:#888;margin-top:2px">L'hôte a refusé votre demande</div>`
        }
      </div>
    `;
    autoClose(notif, 5000);
    bar.appendChild(notif);
    if (accepted) {
      setTimeout(() => location.href = '/lobby', 1200);
    }
  };

  // ── Socket global (pages sans socket propre) ──────────────────────────────
  window._hookGlobalSocketEvents = function(socket) {
    if (!socket || socket.__globalHooked) return;
    socket.__globalHooked = true;

    socket.on('lobby_invitation', async (data) => {
      let me = window._currentUsername;
      if (!me) {
        try { const r = await fetch('/current_user'); const u = await r.json(); me = u && u.username; window._currentUsername = me; } catch(e) {}
      }
      if (me && data.to === me) {
        // Dashboard gère ses propres notifs → skip
        if (location.pathname === '/dashboard') return;
        window._globalShowLobbyInvite(data, socket);
      }
    });

    socket.on('join_request', async (data) => {
      let me = window._currentUsername;
      if (!me) {
        try { const r = await fetch('/current_user'); const u = await r.json(); me = u && u.username; window._currentUsername = me; } catch(e) {}
      }
      if (me && data.host === me) {
        if (location.pathname === '/dashboard' || location.pathname === '/lobby') return;
        window._globalShowJoinRequest(data, socket);
      }
    });

    socket.on('join_request_result', (data) => {
      window._globalShowJoinResult(data.accepted, data.host);
    });
  };

  function initGlobalSocketForPage() {
    const pagesWithSocket = ['/dashboard', '/lobby', '/live-score'];
    const needsOwn = !pagesWithSocket.some(p => location.pathname.startsWith(p));

    if (needsOwn) {
      if (typeof io === 'undefined') return;
      try {
        const sock = io({
          reconnection: true, reconnectionDelay: 1000, reconnectionDelayMax: 10000,
          reconnectionAttempts: Infinity, timeout: 20000,
          transports: ['websocket','polling'],
        });
        window._hookGlobalSocketEvents(sock);
        window._globalSocket = sock;
      } catch(e) {}
    }
  }

  // ── Indicateur reconnexion ────────────────────────────────────────────────
  window.initReconnectIndicator = function(socket) {
    if (!socket) return;
    let bar = document.getElementById('reconnect-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'reconnect-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:100000;background:rgba(231,152,0,0.95);color:white;text-align:center;padding:0.4rem;font-size:0.85rem;font-weight:700;display:none;font-family:Inter,sans-serif;';
      bar.textContent = '⚡ Reconnexion en cours…';
      document.body.appendChild(bar);
    }
    socket.on('disconnect', () => { bar.style.display = 'block'; });
    socket.on('connect', () => { bar.style.display = 'none'; });
    // Hooker les événements globaux sur ce socket de page
    window._hookGlobalSocketEvents(socket);
  };

  // ── Boot ──────────────────────────────────────────────────────────────────
  function init() {
    createFloatingShapes();
    createGlowPulse();
    injectNotifStyles();
    // Attendre que socket.io soit prêt pour les pages sans socket propre
    if (typeof io !== 'undefined') {
      initGlobalSocketForPage();
    } else {
      document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initGlobalSocketForPage, 500);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
