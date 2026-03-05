/**
 * profile-utils.js - Shared helpers for profile display (avatar/nickname/theme/frame)
 */

window.ProfileUtils = (() => {
  const _cache = {};
  const CACHE_TTL_MS = 15000;
  let _lastFetchAt = 0;
  let _inflightProfilesReq = null;
  const _avatarMissing = new Set();

  function _cacheFresh() {
    return Object.keys(_cache).length > 0 && (Date.now() - _lastFetchAt) < CACHE_TTL_MS;
  }

  function mergeUserData(prev, next) {
    if (!next || !next.username) return prev || next || {};
    return { ...(prev || {}), ...next, username: next.username };
  }

  function normalizeThemeKey(raw) {
    const v = String(raw || '').trim().toLowerCase();
    if (!v || v === 'default') return 'default';
    if (v.startsWith('theme_')) return v;
    if (['fire', 'night', 'gold', 'royal', 'master'].includes(v)) return 'theme_' + v;
    return 'default';
  }

  function normalizeFrameKey(raw) {
    const v = String(raw || '').trim().toLowerCase();
    if (!v || v === 'none') return 'none';
    if (v.startsWith('frame_')) return v;
    if (['bronze', 'flame', 'phoenix'].includes(v)) return 'frame_' + v;
    return 'none';
  }

  function frameClassFromKey(key) {
    const k = normalizeFrameKey(key);
    if (k === 'none') return 'avatar-frame-none';
    return 'avatar-' + k.replace('_', '-');
  }

  function themeClassFromKey(key) {
    const k = normalizeThemeKey(key);
    if (k === 'default') return 'avatar-theme-default';
    return 'avatar-theme-' + k.replace('theme_', '');
  }

  function clearAvatarCosmeticClasses(el) {
    if (!el || !el.classList) return;
    Array.from(el.classList).forEach((cls) => {
      if (cls.startsWith('avatar-frame-') || cls.startsWith('avatar-theme-') || cls.startsWith('avatar-frame_')) {
        el.classList.remove(cls);
      }
    });
  }

  async function _refreshProfiles(force) {
    if (!force && _cacheFresh()) return _cache;
    if (_inflightProfilesReq) return _inflightProfilesReq;
    _inflightProfilesReq = (async () => {
      try {
        const res = await fetch('/users_list');
        if (!res.ok) return _cache;
        const list = await res.json();
        (Array.isArray(list) ? list : []).forEach((u) => {
          if (u && u.username) _cache[u.username] = mergeUserData(_cache[u.username], u);
        });
        if (Object.keys(_cache).length > 0) _lastFetchAt = Date.now();
      } catch (e) {}
      return _cache;
    })();
    try {
      return await _inflightProfilesReq;
    } finally {
      _inflightProfilesReq = null;
    }
  }

  function displayName(user) {
    if (!user) return '?';
    return user.nickname && user.nickname.trim() ? user.nickname.trim() : (user.username || '?');
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function avatarFallbackHTML(user, size) {
    const s = size || 36;
    if (!user) return '<span>?</span>';
    if (user.avatar_preset) {
      return `<span style="font-size:${Math.round(s * 0.55)}px;line-height:1">${escapeHtml(user.avatar_preset)}</span>`;
    }
    const initial = (user.username || '?')[0].toUpperCase();
    return `<span style="font-size:${Math.round(s * 0.45)}px;font-weight:700">${escapeHtml(initial)}</span>`;
  }

  function avatarHTML(user, size) {
    const s = size || 36;
    if (!user) return '<span>?</span>';

    const username = String(user.username || '');
    if (!username) return avatarFallbackHTML(user, s);

    // Evite les requetes 404 repetitives tout en restant tolerant si un avatar apparait ensuite.
    if (_avatarMissing.has(username) && !user.avatar_url && user.has_avatar !== true) {
      return avatarFallbackHTML(user, s);
    }
    if (user.has_avatar === true || user.avatar_url) _avatarMissing.delete(username);

    const src = '/api/avatar/' + encodeURIComponent(username);
    const ox = Number.isFinite(Number(user.avatar_crop_x)) ? Number(user.avatar_crop_x) : 50;
    const oy = Number.isFinite(Number(user.avatar_crop_y)) ? Number(user.avatar_crop_y) : 50;
    const fallback = avatarFallbackHTML(user, s);
    const usernameEncoded = encodeURIComponent(username);

    return `<span style="position:relative;width:${s}px;height:${s}px;display:inline-flex;align-items:center;justify-content:center;overflow:hidden;border-radius:50%">${fallback}<img src="${src}" style="position:absolute;inset:0;width:${s}px;height:${s}px;border-radius:50%;object-fit:cover;object-position:${ox}% ${oy}%;" alt="" loading="lazy" decoding="async" onload="if(window.ProfileUtils&&ProfileUtils._markAvatarPresent)ProfileUtils._markAvatarPresent(decodeURIComponent('${usernameEncoded}'));if(this.previousElementSibling)this.previousElementSibling.style.display='none'" onerror="if(window.ProfileUtils&&ProfileUtils._markAvatarMissing)ProfileUtils._markAvatarMissing(decodeURIComponent('${usernameEncoded}'));this.remove()"></span>`;
  }

  function avatarWithCosmeticsHTML(user, size, opts) {
    const s = size || 36;
    const options = opts || {};
    const classes = ['avatar-shell', 'avatar-shell-circle', themeClassFromKey(user && user.active_theme)];
    const frameClass = frameClassFromKey(user && user.active_frame);
    if (frameClass !== 'avatar-frame-none') classes.push(frameClass);
    if (options.extraClass) classes.push(options.extraClass);
    return `<span class="${classes.join(' ')}" style="width:${s}px;height:${s}px;display:inline-flex;align-items:center;justify-content:center;overflow:hidden">${avatarHTML(user, s)}</span>`;
  }

  // badgesOnlyHTML — affiche uniquement les images des badges (sans nom), taille configurable
  // Gère crop_x / crop_y / crop_scale si stockés dans le badge
  function badgeHTML(badge, opts) {
    const b = badge || {};
    const options = opts || {};
    const size = options.size || 22;
    const showRing = options.showRing !== false;
    const withHalo = options.halo === true;
    const borderWidth = Number.isFinite(Number(options.borderWidth))
      ? Math.max(1, Number(options.borderWidth))
      : Math.max(1, Math.round(size * 0.07));
    const color = b.color || '#888';
    const name = escapeHtml(b.name || '');

    let inner = '';
    if (b.image_url) {
      const cx = Number.isFinite(Number(b.crop_x)) ? Number(b.crop_x) : 50;
      const cy = Number.isFinite(Number(b.crop_y)) ? Number(b.crop_y) : 50;
      const cs = Number.isFinite(Number(b.crop_scale)) ? Math.max(1, Number(b.crop_scale)) : 1;
      inner = `<img src="${b.image_url}" alt="${name}" style="width:100%;height:100%;display:block;flex-shrink:0;object-fit:cover;object-position:${cx}% ${cy}%;transform:scale(${cs});transform-origin:${cx}% ${cy}%">`;
    } else if (b.icon) {
      inner = `<span style="font-size:${Math.max(10, Math.round(size * 0.56))}px;line-height:1;user-select:none">${escapeHtml(b.icon)}</span>`;
    } else {
      inner = `<span style="font-size:${Math.max(10, Math.round(size * 0.5))}px;font-weight:800;line-height:1;color:${color}">${escapeHtml((b.name || '?')[0].toUpperCase())}</span>`;
    }

    const ring = showRing
      ? `box-shadow:0 0 0 ${Math.max(1, Math.round(borderWidth * 0.65))}px ${color}3d${withHalo ? `,0 0 ${Math.max(6, Math.round(size * 0.4))}px ${color}2a` : ''};`
      : `border:1px solid rgba(255,255,255,.14);`;
    return `<span title="${name}" style="display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;background:rgba(10,12,18,.9);${ring}overflow:hidden;flex-shrink:0;transform:translateZ(0)"><span style="display:inline-flex;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%;overflow:hidden">${inner}</span></span>`;
  }

  function badgesOnlyHTML(user, imgSize) {
    const s = imgSize || 22;
    const badges = (user && user.badges) || [];
    if (!badges.length) return '';
    return badges.slice(0, 5).map((b) => badgeHTML(b, {
      size: s,
      showRing: true,
      borderWidth: Math.max(1, Math.round(s * 0.07)),
    })).join('');
  }

  function playerCardHTML(user, opts) {
    const options = opts || {};
    const size = options.size || 36;
    const showUsername = options.showUsername !== false;
    const compact = !!options.compact;
    const name = displayName(user);
    const isNicknamed = user && user.nickname && user.nickname.trim();
    const av = avatarWithCosmeticsHTML(user, size);
    const sub = (showUsername && isNicknamed)
      ? `<span style="font-size:0.68rem;color:var(--text-muted);display:block;line-height:1.1">${user.username}</span>`
      : '';
    const bdg = badgesOnlyHTML(user, options.badgeSize || 18);
    const bdgRow = bdg ? `<div style="display:flex;gap:3px;flex-wrap:wrap;margin-top:3px;align-items:center">${bdg}</div>` : '';
    if (compact) {
      return `<span style="display:inline-flex;align-items:center;gap:6px">${av}<span><span style="font-weight:600;font-size:0.875rem">${name}</span>${sub}${bdgRow}</span></span>`;
    }
    return `<div style="display:flex;align-items:center;gap:10px">${av}<div><div style="font-weight:600;font-size:0.9rem;line-height:1.2">${name}</div>${sub}${bdgRow}</div></div>`;
  }

  function applyAvatarCosmetics(el, user) {
    if (!el || !user) return;
    clearAvatarCosmeticClasses(el);
    el.classList.add(themeClassFromKey(user.active_theme));
    const frameClass = frameClassFromKey(user.active_frame);
    if (frameClass !== 'avatar-frame-none') el.classList.add(frameClass);
    el.dataset.avatarTheme = normalizeThemeKey(user.active_theme);
    el.dataset.avatarFrame = normalizeFrameKey(user.active_frame);
  }

  function updateNav(user) {
    const navAv = document.getElementById('navAv');
    const navUsername = document.getElementById('navUsername');
    if (!navAv || !user) return;

    if (navUsername) navUsername.textContent = displayName(user);
    navAv.style.opacity = '1';
    navAv.classList.add('avatar-shell', 'avatar-shell-circle', 'avatar-shell-nav');
    applyAvatarCosmetics(navAv, user);

    const fallback = user.avatar_preset || (user.username || '?')[0].toUpperCase();
    navAv.innerHTML = '';
    navAv.textContent = fallback;

    const knowsNoAvatar = user.has_avatar === false && !user.avatar_url;
    if (!user.username || knowsNoAvatar) return;

    const src = '/api/avatar/' + encodeURIComponent(user.username);
    const img = document.createElement('img');
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;border-radius:50%;';
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = src;
    img.onload = function () {
      if (user.username) _avatarMissing.delete(user.username);
      navAv.innerHTML = '';
      navAv.appendChild(img);
    };
    img.onerror = function () {
      if (user.username) _avatarMissing.add(user.username);
      // Keep fallback text.
      img.remove();
    };
  }

  async function fetchUserProfile(username) {
    if (!username) return { username: '' };
    if (_cache[username] && _cacheFresh()) return _cache[username];
    await _refreshProfiles(false);
    return _cache[username] || { username: username };
  }

  async function fetchAllProfiles(force) {
    await _refreshProfiles(!!force);
    return _cache;
  }

  function _cache_set(username, data) {
    _cache[username] = mergeUserData(_cache[username], data);
    _lastFetchAt = Date.now();
  }

  function _markAvatarMissing(username) {
    const u = String(username || '').trim();
    if (u) _avatarMissing.add(u);
  }

  function _markAvatarPresent(username) {
    const u = String(username || '').trim();
    if (u) _avatarMissing.delete(u);
  }

  function logout() {
    fetch('/api/logout', { method: 'POST' }).then(() => { location.href = '/'; });
  }

  window.logout = logout;

  function _getAllCache() { return _cache; }

  return {
    displayName,
    normalizeThemeKey,
    normalizeFrameKey,
    avatarHTML,
    avatarWithCosmeticsHTML,
    badgeHTML,
    badgesOnlyHTML,
    playerCardHTML,
    applyAvatarCosmetics,
    updateNav,
    fetchUserProfile,
    fetchAllProfiles,
    _cache_set,
    _markAvatarMissing,
    _markAvatarPresent,
    _getAllCache,
    logout,
  };
})();
