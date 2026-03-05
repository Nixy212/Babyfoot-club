/**
 * profile-utils.js - Shared helpers for profile display (avatar/nickname/theme/frame)
 */

window.ProfileUtils = (() => {
  const _cache = {};
  const CACHE_TTL_MS = 15000;
  let _lastFetchAt = 0;
  let _inflightProfilesReq = null;

  function _cacheFresh() {
    return Object.keys(_cache).length > 0 && (Date.now() - _lastFetchAt) < CACHE_TTL_MS;
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
          if (u && u.username) _cache[u.username] = u;
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

  function avatarHTML(user, size) {
    const s = size || 36;
    if (!user) return '<span>?</span>';
    if ((user.has_avatar || user.avatar_url) && user.username) {
      const src = '/api/avatar/' + encodeURIComponent(user.username);
      const ox = Number.isFinite(Number(user.avatar_crop_x)) ? Number(user.avatar_crop_x) : 50;
      const oy = Number.isFinite(Number(user.avatar_crop_y)) ? Number(user.avatar_crop_y) : 50;
      return `<img src="${src}" style="width:${s}px;height:${s}px;border-radius:50%;object-fit:cover;object-position:${ox}% ${oy}%;" alt="" onerror="this.style.display='none'">`;
    }
    if (user.avatar_preset) {
      return `<span style="font-size:${Math.round(s * 0.55)}px;line-height:1">${user.avatar_preset}</span>`;
    }
    const initial = (user.username || '?')[0].toUpperCase();
    return `<span style="font-size:${Math.round(s * 0.45)}px;font-weight:700">${initial}</span>`;
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
      const imgSize = Math.max(size, Math.round(size * cs));
      inner = `<img src="${b.image_url}" alt="${name}" style="width:${imgSize}px;height:${imgSize}px;display:block;flex-shrink:0;object-fit:cover;object-position:${cx}% ${cy}%">`;
    } else if (b.icon) {
      inner = `<span style="font-size:${Math.max(10, Math.round(size * 0.56))}px;line-height:1;user-select:none">${escapeHtml(b.icon)}</span>`;
    } else {
      inner = `<span style="font-size:${Math.max(10, Math.round(size * 0.5))}px;font-weight:800;line-height:1;color:${color}">${escapeHtml((b.name || '?')[0].toUpperCase())}</span>`;
    }

    const ring = showRing
      ? `box-shadow:inset 0 0 0 ${borderWidth}px ${color}66,inset 0 0 0 ${Math.max(1, borderWidth - 0.4)}px rgba(255,255,255,.1)${withHalo ? `,0 0 10px ${color}3f` : ''};`
      : `border:1px solid rgba(255,255,255,.14);`;
    return `<span title="${name}" style="display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;background:radial-gradient(circle at 28% 22%,${color}2e 0%,${color}14 52%,rgba(10,12,18,.82) 100%);${ring}overflow:hidden;flex-shrink:0;transform:translateZ(0)"><span style="display:inline-flex;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%;overflow:hidden;background:rgba(0,0,0,.1)">${inner}</span></span>`;
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

    if ((user.has_avatar || user.avatar_url) && user.username) {
      const src = '/api/avatar/' + encodeURIComponent(user.username) + '?t=' + Date.now();
      navAv.innerHTML = '';
      const img = document.createElement('img');
      img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;border-radius:50%;';
      img.alt = '';
      img.src = src;
      img.onerror = function () {
        navAv.innerHTML = '';
        navAv.textContent = user.avatar_preset || (user.username || '?')[0].toUpperCase();
      };
      navAv.appendChild(img);
    } else if (user.avatar_preset) {
      navAv.innerHTML = '';
      navAv.textContent = user.avatar_preset;
    } else {
      navAv.innerHTML = '';
      navAv.textContent = (user.username || '?')[0].toUpperCase();
    }
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
    _cache[username] = data;
    _lastFetchAt = Date.now();
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
    _getAllCache,
    logout,
  };
})();
