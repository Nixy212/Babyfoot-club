/**
 * particles-bg.js — Poussière dorée en diagonale (bas-gauche → haut-droite)
 * Purement CSS, zéro canvas, zéro rAF. Impact batterie nul.
 */
(function () {

  // [bottom%, left%, durée(s), delay(s), taille(px), opacité, couleur]
  const P = [
    [ 0, 5,  19, 0.0, 2.5, .22, '#e8a06a'],
    [ 0,10,  25, 2.1, 1.8, .16, '#e8b84a'],
    [ 0,18,  21, 5.3, 3.0, .20, '#d4884e'],
    [ 0,24,  32, 1.2, 1.5, .13, '#ffdc78'],
    [ 0,31,  18, 7.8, 2.0, .19, '#e8a06a'],
    [ 0,38,  27, 3.5, 2.8, .15, '#e8b84a'],
    [ 0,44,  23, 0.8, 1.6, .21, '#d4884e'],
    [ 0,50,  20, 9.1, 3.2, .18, '#ffdc78'],
    [ 0,57,  29, 4.4, 2.2, .14, '#e8a06a'],
    [ 0,63,  24, 6.7, 1.9, .20, '#e8b84a'],
    [ 0,70,  17, 2.9, 2.6, .15, '#d4884e'],
    [ 0,76,  30, 8.3, 1.4, .23, '#ffdc78'],
    [ 0,82,  22, 1.6, 3.1, .17, '#e8a06a'],
    [ 0,89,  26, 5.0, 2.1, .19, '#e8b84a'],
    [ 0,95,  19, 3.8, 1.7, .13, '#d4884e'],
    [ 0, 8,  28,11.2, 2.4, .15, '#ffdc78'],
    [ 0,22,  21, 7.0, 1.3, .18, '#e8a06a'],
    [ 0,35,  33, 0.3, 2.9, .12, '#e8b84a'],
    [ 0,48,  16, 9.6, 1.8, .21, '#d4884e'],
    [ 0,62,  24, 4.1, 2.5, .16, '#ffdc78'],
    [ 0,73,  20, 6.5, 1.6, .20, '#e8a06a'],
    [ 0,85,  27, 2.4, 3.3, .14, '#e8b84a'],
    [ 0,15,  22,13.1, 2.0, .17, '#d4884e'],
    [ 0,42,  18,10.5, 1.5, .19, '#ffdc78'],
    [ 0,68,  31, 1.9, 2.7, .13, '#e8a06a'],
    [ 0, 3,  23, 8.7, 1.9, .15, '#e8b84a'],
    [ 0,55,  19, 5.5, 2.3, .22, '#d4884e'],
    [ 0,78,  26,12.0, 1.7, .16, '#ffdc78'],
    [ 0,92,  21, 3.2, 2.8, .18, '#e8a06a'],
    [ 0,29,  29, 7.4, 1.4, .14, '#e8b84a'],
  ];

  function injectCSS() {
    const s = document.createElement('style');
    // translateX positif = drift vers la droite (diagonale bas-gauche → haut-droite)
    s.textContent = `
      #dust-layer{
        position:fixed;inset:0;pointer-events:none;z-index:1;overflow:hidden;
      }
      .dust{
        position:absolute;border-radius:50%;
        animation:dustDiag linear infinite;
        will-change:transform,opacity;
      }
      @keyframes dustDiag{
        0%  { transform:translateY(0) translateX(0) scale(1); opacity:0; }
        6%  { opacity:1; }
        40% { transform:translateY(-40vh) translateX(22vw) scale(1.08); }
        70% { transform:translateY(-70vh) translateX(38vw) scale(0.94); opacity:.7;}
        100%{ transform:translateY(-110vh) translateX(52vw) scale(0.78); opacity:0; }
      }
    `;
    document.head.appendChild(s);
  }

  function build() {
    injectCSS();
    const layer = document.createElement('div');
    layer.id = 'dust-layer';
    P.forEach(([bot, left, dur, delay, size, opacity, color]) => {
      const el = document.createElement('span');
      el.className = 'dust';
      el.style.cssText = [
        `bottom:${bot}%`,
        `left:${left}%`,
        `width:${size}px`,
        `height:${size}px`,
        `background:${color}`,
        `opacity:${opacity}`,
        `animation-duration:${dur}s`,
        `animation-delay:-${delay}s`,
        `box-shadow:0 0 ${size*2.2}px ${size*0.9}px ${color}50`,
      ].join(';');
      layer.appendChild(el);
    });
    document.body.insertBefore(layer, document.body.firstChild);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();
