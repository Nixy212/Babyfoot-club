/**
 * particles-bg.js - Theme emoji outline particles drifting diagonally.
 */
(function () {
  'use strict';

  const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) return;

  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const effectiveType = String((conn && conn.effectiveType) || '').toLowerCase();
  const saveData = !!(conn && conn.saveData);
  const slowNetwork = saveData || ['slow-2g', '2g', '3g'].includes(effectiveType);
  if (slowNetwork || (window.__bfNetworkProfile && window.__bfNetworkProfile.slow)) return;

  const isMobile = window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
  const PARTICLE_COUNT = isMobile ? 10 : 24;

  const STROKE_BY_THEME = {
    default: 'rgba(212,136,78,0.42)',
    theme_fire: 'rgba(255,107,44,0.5)',
    theme_night: 'rgba(142,125,255,0.5)',
    theme_gold: 'rgba(227,179,59,0.5)',
    theme_royal: 'rgba(74,147,235,0.5)',
    theme_master: 'rgba(215,164,58,0.52)',
  };

  function activeThemeKey() {
    const fromManager = window.ThemeManager && window.ThemeManager.getActiveTheme
      ? window.ThemeManager.getActiveTheme()
      : null;
    const fromAttr = document.documentElement.getAttribute('data-active-theme');
    return fromManager || fromAttr || 'default';
  }

  function activeThemeEmoji() {
    if (window.ThemeManager && window.ThemeManager.getThemeEmoji) {
      return window.ThemeManager.getThemeEmoji();
    }
    const cssEmoji = getComputedStyle(document.documentElement).getPropertyValue('--theme-emoji').trim();
    const cleaned = cssEmoji.replace(/^['"]|['"]$/g, '');
    return cleaned || '⚽';
  }

  function strokeColorForTheme(key) {
    return STROKE_BY_THEME[key] || STROKE_BY_THEME.default;
  }

  function injectCSS() {
    if (document.getElementById('emoji-dust-style')) return;
    const s = document.createElement('style');
    s.id = 'emoji-dust-style';
    s.textContent = `
      #dust-layer{
        position:fixed;inset:0;pointer-events:none;z-index:1;overflow:hidden;
      }
      .dust-emoji{
        position:absolute;
        color:transparent;
        -webkit-text-stroke:1px var(--dust-stroke, rgba(212,136,78,.42));
        text-shadow:0 0 8px var(--dust-stroke, rgba(212,136,78,.42));
        will-change:transform,opacity;
        animation:dustEmojiDiag linear infinite;
        user-select:none;
      }
      @keyframes dustEmojiDiag{
        0%   { transform:translateY(0) translateX(0) rotate(-8deg) scale(1); opacity:0; }
        8%   { opacity:1; }
        55%  { transform:translateY(-56vh) translateX(26vw) rotate(7deg) scale(1.06); opacity:.75; }
        100% { transform:translateY(-116vh) translateX(56vw) rotate(16deg) scale(.85); opacity:0; }
      }
    `;
    document.head.appendChild(s);
  }

  function build() {
    injectCSS();
    let layer = document.getElementById('dust-layer');
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'dust-layer';
      document.body.insertBefore(layer, document.body.firstChild);
    }
    layer.innerHTML = '';

    const themeKey = activeThemeKey();
    const emoji = activeThemeEmoji();
    const stroke = strokeColorForTheme(themeKey);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const size = (isMobile ? 11 : 13) + Math.random() * (isMobile ? 4 : 8);
      const left = Math.random() * 96;
      const bottom = -8 + Math.random() * 12;
      const duration = (isMobile ? 18 : 20) + Math.random() * (isMobile ? 16 : 18);
      const delay = Math.random() * 18;
      const opacity = (isMobile ? 0.2 : 0.28) + Math.random() * 0.28;
      const drift = (Math.random() * 0.8 + 0.6).toFixed(2);

      const el = document.createElement('span');
      el.className = 'dust-emoji';
      el.textContent = emoji;
      el.style.cssText = [
        `left:${left.toFixed(2)}%`,
        `bottom:${bottom.toFixed(2)}%`,
        `font-size:${size.toFixed(1)}px`,
        `opacity:${opacity.toFixed(2)}`,
        `animation-duration:${duration.toFixed(1)}s`,
        `animation-delay:-${delay.toFixed(2)}s`,
        `--dust-stroke:${stroke}`,
        `filter:drop-shadow(0 0 ${Math.max(5, size * 0.9).toFixed(1)}px var(--dust-stroke))`,
        `transform-origin:center`,
        `--drift:${drift}`,
      ].join(';');
      layer.appendChild(el);
    }
  }

  function refreshThemeOnParticles() {
    const layer = document.getElementById('dust-layer');
    if (!layer) return;
    const themeKey = activeThemeKey();
    const emoji = activeThemeEmoji();
    const stroke = strokeColorForTheme(themeKey);
    layer.querySelectorAll('.dust-emoji').forEach((el) => {
      el.textContent = emoji;
      el.style.setProperty('--dust-stroke', stroke);
      el.style.filter = `drop-shadow(0 0 10px ${stroke})`;
    });
  }

  function init() {
    build();
    window.addEventListener('bf:theme-changed', refreshThemeOnParticles);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
