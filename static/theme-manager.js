/**
 * theme-manager.js — Applique le thème cosmétique actif sur toutes les pages.
 * Expose window.ThemeManager.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'bf_active_theme';
  const THEMES = {
    default: {
      bodyClass: '',
      emoji: '⚽', bg:'#0f101a', accentRgb:'212,136,78', gridColor:'rgba(212,136,78,.025)',
      vars: { '--c-bg':'#0f111a','--c-s1':'#151820','--c-s2':'#1c2030','--c-s3':'#232840','--c-s4':'#2a3050',
              '--c-accent':'#d4884e','--c-accent-h':'#e8a06a','--c-gold':'#e8b84a','--c-bronze':'#b06030',
              '--c-a08':'rgba(212,136,78,.08)','--c-a10':'rgba(212,136,78,.10)','--c-a15':'rgba(212,136,78,.15)',
              '--c-a25':'rgba(212,136,78,.25)','--c-a40':'rgba(212,136,78,.40)','--c-ba':'rgba(212,136,78,.28)' }
    },
    theme_fire: {
      bodyClass: 'theme-fire',
      emoji: '🔥', bg:'#130704', accentRgb:'255,107,44', gridColor:'rgba(255,107,44,.04)',
      vars: { '--c-bg':'#130704','--c-s1':'#1d0b08','--c-s2':'#27110d','--c-s3':'#321713','--c-s4':'#421f19',
              '--c-accent':'#ff6b2c','--c-accent-h':'#ff9556','--c-gold':'#ffc56a','--c-bronze':'#c8582d',
              '--c-a08':'rgba(255,107,44,.08)','--c-a10':'rgba(255,107,44,.10)','--c-a15':'rgba(255,107,44,.15)',
              '--c-a25':'rgba(255,107,44,.25)','--c-a40':'rgba(255,107,44,.40)','--c-ba':'rgba(255,107,44,.30)' }
    },
    theme_night: {
      bodyClass: 'theme-night',
      emoji: '🌌', bg:'#090812', accentRgb:'142,125,255', gridColor:'rgba(142,125,255,.04)',
      vars: { '--c-bg':'#090812','--c-s1':'#111022','--c-s2':'#171635','--c-s3':'#211f4a','--c-s4':'#2c2a64',
              '--c-accent':'#8e7dff','--c-accent-h':'#b2a4ff','--c-gold':'#cfbbff','--c-bronze':'#7b66d4',
              '--c-a08':'rgba(142,125,255,.08)','--c-a10':'rgba(142,125,255,.10)','--c-a15':'rgba(142,125,255,.15)',
              '--c-a25':'rgba(142,125,255,.25)','--c-a40':'rgba(142,125,255,.40)','--c-ba':'rgba(142,125,255,.32)' }
    },
    theme_gold: {
      bodyClass: 'theme-gold',
      emoji: '✨', bg:'#111003', accentRgb:'227,179,59', gridColor:'rgba(227,179,59,.04)',
      vars: { '--c-bg':'#111003','--c-s1':'#191706','--c-s2':'#25210a','--c-s3':'#322c10','--c-s4':'#433a16',
              '--c-accent':'#e3b33b','--c-accent-h':'#f4cd66','--c-gold':'#ffe285','--c-bronze':'#bf8e2a',
              '--c-a08':'rgba(227,179,59,.08)','--c-a10':'rgba(227,179,59,.10)','--c-a15':'rgba(227,179,59,.15)',
              '--c-a25':'rgba(227,179,59,.25)','--c-a40':'rgba(227,179,59,.40)','--c-ba':'rgba(227,179,59,.32)' }
    },
    theme_royal: {
      bodyClass: 'theme-royal',
      emoji: '💠', bg:'#071021', accentRgb:'74,147,235', gridColor:'rgba(74,147,235,.04)',
      vars: { '--c-bg':'#071021','--c-s1':'#0d182d','--c-s2':'#12213b','--c-s3':'#1a2d50','--c-s4':'#223b68',
              '--c-accent':'#4a93eb','--c-accent-h':'#6fb5ff','--c-gold':'#8fd1ff','--c-bronze':'#3173bb',
              '--c-a08':'rgba(74,147,235,.08)','--c-a10':'rgba(74,147,235,.10)','--c-a15':'rgba(74,147,235,.15)',
              '--c-a25':'rgba(74,147,235,.25)','--c-a40':'rgba(74,147,235,.40)','--c-ba':'rgba(74,147,235,.30)' }
    },
    theme_master: {
      bodyClass: 'theme-master',
      emoji: '🏆', bg:'#0f0e0a', accentRgb:'215,164,58', gridColor:'rgba(215,164,58,.04)',
      vars: { '--c-bg':'#0f0e0a','--c-s1':'#181611','--c-s2':'#221f16','--c-s3':'#302b1d','--c-s4':'#403826',
              '--c-accent':'#d7a43a','--c-accent-h':'#f0cd75','--c-gold':'#ffe1a0','--c-bronze':'#b88224',
              '--c-a08':'rgba(215,164,58,.08)','--c-a10':'rgba(215,164,58,.10)','--c-a15':'rgba(215,164,58,.15)',
              '--c-a25':'rgba(215,164,58,.25)','--c-a40':'rgba(215,164,58,.40)','--c-ba':'rgba(215,164,58,.34)' }
    },
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

    const html = document.documentElement;
    if (document.body) setBodyThemeClass(cfg.bodyClass);
    html.setAttribute('data-active-theme', key);
    html.style.setProperty('--theme-emoji', '"' + cfg.emoji + '"');

    // MOBILE FIX COMPLET — iOS Safari / Chrome Android n'hérite pas des CSS vars
    // définies sur body.theme-X. On les force TOUTES sur <html> pour garantir
    // l'application dès le premier paint, sur toutes les pages.
    if (cfg.vars) {
      Object.entries(cfg.vars).forEach(([k, v]) => html.style.setProperty(k, v));
      // Alias sémantiques (--bg-primary, etc.) aussi forcés sur html
      const v = cfg.vars;
      html.style.setProperty('--bg-primary',    v['--c-bg']      || '');
      html.style.setProperty('--bg-secondary',  v['--c-s1']      || '');
      html.style.setProperty('--bg-elevated',   v['--c-s2']      || '');
      html.style.setProperty('--bg-tertiary',   v['--c-s3']      || '');
      html.style.setProperty('--bg-hover',      v['--c-s4']      || '');
      html.style.setProperty('--accent-primary',v['--c-accent']  || '');
      html.style.setProperty('--accent-hover',  v['--c-accent-h']|| '');
      html.style.setProperty('--border-accent', v['--c-ba']      || '');
    }
    if (cfg.accentRgb) html.style.setProperty('--theme-accent-rgb', cfg.accentRgb);
    if (cfg.gridColor)  html.style.setProperty('--grid-color', cfg.gridColor);
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
