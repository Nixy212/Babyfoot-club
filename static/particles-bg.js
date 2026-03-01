/**
 * particles-bg.js — Poussière dorée, version mobile
 * Purement CSS : zéro canvas, zéro requestAnimationFrame, zéro calcul JS
 * Chaque particule = un <span> animé par @keyframes CSS
 * Impact batterie/CPU : quasi nul
 */
(function () {

  const PARTICLES = [
    // [left%, animDuration(s), animDelay(s), size(px), opacity, color]
    [  5, 18, 0.0, 2.5, 0.25, '#e8a06a'],
    [ 12, 24, 2.1, 1.8, 0.18, '#e8b84a'],
    [ 18, 20, 5.3, 3.0, 0.22, '#d4884e'],
    [ 25, 31, 1.2, 1.5, 0.14, '#ffdc78'],
    [ 31, 17, 7.8, 2.0, 0.20, '#e8a06a'],
    [ 38, 26, 3.5, 2.8, 0.17, '#e8b84a'],
    [ 44, 22, 0.8, 1.6, 0.23, '#d4884e'],
    [ 50, 19, 9.1, 3.2, 0.19, '#ffdc78'],
    [ 57, 28, 4.4, 2.2, 0.15, '#e8a06a'],
    [ 63, 23, 6.7, 1.9, 0.21, '#e8b84a'],
    [ 70, 16, 2.9, 2.6, 0.16, '#d4884e'],
    [ 76, 29, 8.3, 1.4, 0.24, '#ffdc78'],
    [ 82, 21, 1.6, 3.1, 0.18, '#e8a06a'],
    [ 89, 25, 5.0, 2.1, 0.20, '#e8b84a'],
    [ 95, 18, 3.8, 1.7, 0.14, '#d4884e'],
    [  8, 27, 11.2,2.4, 0.16, '#ffdc78'],
    [ 22, 20, 7.0, 1.3, 0.19, '#e8a06a'],
    [ 35, 32, 0.3, 2.9, 0.13, '#e8b84a'],
    [ 48, 15, 9.6, 1.8, 0.22, '#d4884e'],
    [ 62, 23, 4.1, 2.5, 0.17, '#ffdc78'],
    [ 73, 19, 6.5, 1.6, 0.21, '#e8a06a'],
    [ 85, 26, 2.4, 3.3, 0.15, '#e8b84a'],
    [ 15, 21, 13.1,2.0, 0.18, '#d4884e'],
    [ 42, 17, 10.5,1.5, 0.20, '#ffdc78'],
    [ 68, 30, 1.9, 2.7, 0.14, '#e8a06a'],
    [  3, 22, 8.7, 1.9, 0.16, '#e8b84a'],
    [ 55, 18, 5.5, 2.3, 0.23, '#d4884e'],
    [ 78, 25, 12.0,1.7, 0.17, '#ffdc78'],
    [ 92, 20, 3.2, 2.8, 0.19, '#e8a06a'],
    [ 29, 28, 7.4, 1.4, 0.15, '#e8b84a'],
  ];

  // Injecter les @keyframes + le CSS de base une seule fois
  function injectCSS() {
    const style = document.createElement('style');
    style.textContent = `
      #dust-layer {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 1;
        overflow: hidden;
      }
      .dust {
        position: absolute;
        bottom: -6px;
        border-radius: 50%;
        will-change: transform, opacity;
        animation: dustFloat linear infinite;
      }
      @keyframes dustFloat {
        0%   { transform: translateY(0)   translateX(0)      scale(1);   opacity: 0;   }
        8%   { opacity: 1; }
        40%  { transform: translateY(-38vh) translateX(14px)  scale(1.1); }
        60%  { transform: translateY(-58vh) translateX(-10px) scale(0.95);}
        85%  { opacity: 0.6; }
        100% { transform: translateY(-105vh) translateX(6px)  scale(0.8); opacity: 0;  }
      }
    `;
    document.head.appendChild(style);
  }

  function build() {
    injectCSS();
    const layer = document.createElement('div');
    layer.id = 'dust-layer';

    PARTICLES.forEach(([left, dur, delay, size, opacity, color]) => {
      const span = document.createElement('span');
      span.className = 'dust';
      span.style.cssText = [
        `left:${left}%`,
        `width:${size}px`,
        `height:${size}px`,
        `background:${color}`,
        `opacity:${opacity}`,
        `animation-duration:${dur}s`,
        `animation-delay:-${delay}s`,   // démarrage immédiat décalé
        `box-shadow:0 0 ${size * 2}px ${size}px ${color}55`,
      ].join(';');
      layer.appendChild(span);
    });

    document.body.insertBefore(layer, document.body.firstChild);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }

})();
