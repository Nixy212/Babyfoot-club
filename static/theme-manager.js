/**
 * theme-manager.js — Applique le thème cosmétique actif sur toutes les pages.
 * Expose window.ThemeManager.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'bf_active_theme';
  const THEMES = {
    default: { bodyClass: '', emoji: '⚽', bg:'#0f101a', accentRgb:'212,136,78', gridColor:'rgba(212,136,78,.025)' },
    theme_fire:   { bodyClass: 'theme-fire',   emoji: '🔥', bg:'#130704', accentRgb:'255,107,44', gridColor:'rgba(255,107,44,.04)' },
    theme_night:  { bodyClass: 'theme-night',  emoji: '🌌', bg:'#090812', accentRgb:'142,125,255', gridColor:'rgba(142,125,255,.04)' },
    theme_gold:   { bodyClass: 'theme-gold',   emoji: '✨', bg:'#111003', accentRgb:'227,179,59',  gridColor:'rgba(227,179,59,.04)' },
    theme_royal:  { bodyClass: 'theme-royal',  emoji: '💠', bg:'#071021', accentRgb:'74,147,235',  gridColor:'rgba(74,147,235,.04)' },
    theme_master: { bodyClass: 'theme-master', emoji: '🏆', bg:'#0f0e0a', accentRgb:'215,164,58',  gridColor:'rgba(215,164,58,.04)' },
  };
  const BODY_THEME_CLASSES = Object.values(THEMES).map((t) => t.bodyClass).filter(Boolean);

  function normalizeThemeKey(raw) {
    const v = String(raw || '').trim().toLowerCase();
    if (!v || v === 'default') return 'default';
    if (THEMES[v]) return v;
    if (v.startsWith('theme_') && THEMES[v]) return v;
    if (THEMES['theme_' + v]) return 'theme_' + v;
    return 'default';
  }

  function getThemeConfig(key) {
    return THEMES[normalizeThemeKey(key)] || THEMES.default;
  }

  function setBodyThemeClass(className) {
    const body = document.body;
    if (!body) return;
    BODY_THEME_CLASSES.forEach((cls) => body.classList.remove(cls));
    if (className) body.classList.add(className);
  }

  function applyTheme(themeKey, opts) {
    const options = opts || {};
    const key = normalizeThemeKey(themeKey);
    const cfg = getThemeConfig(key);

    if (document.body) setBodyThemeClass(cfg.bodyClass);
    document.documentElement.setAttribute('data-active-theme', key);
    document.documentElement.style.setProperty('--theme-emoji', '"' + cfg.emoji + '"');

    // Fix mobile (iOS Safari / Chrome Android) : forcer les vars CSS sur <html>
    // garantit l'héritage même si body.theme-X est appliqué après le premier paint
    if (cfg.accentRgb) document.documentElement.style.setProperty('--theme-accent-rgb', cfg.accentRgb);
    if (cfg.gridColor)  document.documentElement.style.setProperty('--grid-color', cfg.gridColor);
    if (cfg.bg && document.body) document.body.style.backgroundColor = cfg.bg;

    window.__activeThemeKey = key;
    window.__activeThemeEmoji = cfg.emoji;

    if (options.persist !== false) {
      try { localStorage.setItem(STORAGE_KEY, key); } catch (e) {}
    }

    window.dispatchEvent(new CustomEvent('bf:theme-changed', {
      detail: { theme: key, emoji: cfg.emoji },
    }));

    return key;
  }

  function applyFromStorage() {
    try {
      const cached = localStorage.getItem(STORAGE_KEY);
      if (cached) applyTheme(cached, { persist: false });
    } catch (e) {}
  }

  function setUserData(user) {
    if (!user || !user.username) return;
    const theme = user.active_theme || 'default';
    applyTheme(theme, { persist: true });
    window.__activeFrameKey = user.active_frame || 'none';
  }

  async function refreshFromServer() {
    try {
      const res = await fetch('/current_user');
      if (!res.ok) return null;
      const user = await res.json();
      if (user) setUserData(user);
      return user;
    } catch (e) {
      return null;
    }
  }

  function init() {
    applyFromStorage();
    if (document.body) setBodyThemeClass(getThemeConfig(window.__activeThemeKey || 'default').bodyClass);
  }

  window.ThemeManager = {
    applyTheme,
    normalizeThemeKey,
    setUserData,
    refreshFromServer,
    getActiveTheme: function () { return window.__activeThemeKey || 'default'; },
    getThemeEmoji: function () { return window.__activeThemeEmoji || '⚽'; },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
