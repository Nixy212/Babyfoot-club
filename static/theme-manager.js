/**
 * theme-manager.js — Applique le thème cosmétique actif sur toutes les pages.
 * Expose window.ThemeManager.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'bf_active_theme';
  const THEMES = {
    default: { bodyClass: '', emoji: '⚽' },
    theme_fire: { bodyClass: 'theme-fire', emoji: '🔥' },
    theme_night: { bodyClass: 'theme-night', emoji: '🌌' },
    theme_gold: { bodyClass: 'theme-gold', emoji: '✨' },
    theme_royal: { bodyClass: 'theme-royal', emoji: '💠' },
    theme_master: { bodyClass: 'theme-master', emoji: '🏆' },
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
