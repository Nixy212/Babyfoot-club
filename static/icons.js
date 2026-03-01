/**
 * Baby-Foot Club — Icônes SVG illustrées custom
 * Style : trait épuré, illustration artisanale, palette bronze/or
 */

const BFIcons = {

  // 🏠 → Maison illustrée
  home: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M3 10.5L12 3L21 10.5V20C21 20.55 20.55 21 20 21H15V15H9V21H4C3.45 21 3 20.55 3 20V10.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" fill="none"/>
    <path d="M9 21V16C9 15.45 9.45 15 10 15H14C14.55 15 15 15.45 15 16V21" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="12" cy="10" r="1.5" fill="currentColor" opacity="0.5"/>
  </svg>`,

  // 📅 → Calendrier avec croix de baby-foot
  calendar: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="3" y="5" width="18" height="16" rx="2.5" stroke="currentColor" stroke-width="1.6" fill="none"/>
    <path d="M3 10H21" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <line x1="8" y1="3" x2="8" y2="7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <line x1="16" y1="3" x2="16" y2="7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="9" cy="15" r="1.3" fill="currentColor"/>
    <circle cx="15" cy="15" r="1.3" fill="currentColor"/>
    <circle cx="12" cy="15" r="1" fill="currentColor" opacity="0.4"/>
  </svg>`,

  // 🎮 → Manette de jeu stylisée
  gamepad: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M6 11C4 11 2 13 2 16C2 18.5 3.5 21 5.5 21C6.5 21 7.3 20.4 8.2 19.4L9.5 18H14.5L15.8 19.4C16.7 20.4 17.5 21 18.5 21C20.5 21 22 18.5 22 16C22 13 20 11 18 11H6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>
    <line x1="8" y1="13.5" x2="8" y2="16.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <line x1="6.5" y1="15" x2="9.5" y2="15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="16" cy="14" r="1.1" fill="currentColor"/>
    <circle cx="18" cy="16" r="1.1" fill="currentColor"/>
    <path d="M6 11L7 7C7.4 5.8 8.5 5 9.8 5H14.2C15.5 5 16.6 5.8 17 7L18 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
  </svg>`,

  // 📊 → Graphique de statistiques
  stats: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M3 20H21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <rect x="5" y="12" width="3.5" height="8" rx="1" fill="currentColor" opacity="0.3" stroke="currentColor" stroke-width="1.4"/>
    <rect x="10.25" y="7" width="3.5" height="13" rx="1" fill="currentColor" opacity="0.5" stroke="currentColor" stroke-width="1.4"/>
    <rect x="15.5" y="4" width="3.5" height="16" rx="1" fill="currentColor" opacity="0.7" stroke="currentColor" stroke-width="1.4"/>
    <path d="M6.75 12L12 7L17.25 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2 2"/>
  </svg>`,

  // 🏆 → Trophée illustré
  trophy: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M7 3H17V11C17 13.76 14.76 16 12 16C9.24 16 7 13.76 7 11V3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" fill="none"/>
    <path d="M7 5H4C4 5 3 5 3 7C3 9.5 5 11 7 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <path d="M17 5H20C20 5 21 5 21 7C21 9.5 19 11 17 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <line x1="12" y1="16" x2="12" y2="20" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <path d="M8 20H16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
    <path d="M9.5 9.5L11 11L14.5 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`,

  // ⚽ → Ballon de foot illustré
  ball: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" fill="none"/>
    <path d="M12 3L10.5 7.5L12 9L13.5 7.5L12 3Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.2"/>
    <path d="M12 9L9 10.5L8.5 14L12 15.5L15.5 14L15 10.5L12 9Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.2"/>
    <path d="M8.5 14L5 14.5L4 18L7 20L10 18.5L8.5 14Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.1"/>
    <path d="M15.5 14L19 14.5L20 18L17 20L14 18.5L15.5 14Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.1"/>
    <path d="M10.5 7.5L6.5 8L5 14.5L8.5 14L9 10.5L10.5 7.5Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.1"/>
    <path d="M13.5 7.5L17.5 8L19 14.5L15.5 14L15 10.5L13.5 7.5Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" fill="currentColor" fill-opacity="0.1"/>
  </svg>`,

  // 🔓 → Cadenas ouvert illustré (servo/déverrouillage)
  unlock: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="5" y="11" width="14" height="10" rx="2.5" stroke="currentColor" stroke-width="1.6" fill="none"/>
    <path d="M8 11V7.5C8 5.57 9.57 4 11.5 4H12.5C14.43 4 16 5.57 16 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/>
    <circle cx="12" cy="16" r="1.8" fill="currentColor" opacity="0.6"/>
    <line x1="12" y1="17.8" x2="12" y2="19.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <path d="M16 7.5C16 6.5 16.8 5.5 17.5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity="0.5"/>
  </svg>`,

  // 🚪 → Porte de sortie
  logout: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 21H5C4.45 21 4 20.55 4 20V4C4 3.45 4.45 3 5 3H10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <path d="M16 17L21 12L16 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="7" cy="12" r="1.2" fill="currentColor" opacity="0.4"/>
  </svg>`,

  // 🔄 → Rejouer / replay
  replay: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 5C7.58 5 4 8.58 4 13C4 17.42 7.58 21 12 21C16.42 21 20 17.42 20 13C20 10.83 19.12 8.87 17.68 7.44" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/>
    <path d="M12 5L15.5 2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <path d="M12 5L9.5 2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    <path d="M10.5 13L12 11V16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M10 16H14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  </svg>`,

  // 🎉 → Trophée victoire grand format (popup winner)
  winner: `<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- Corps trophée -->
    <path d="M35 18H85V54C85 68.36 73.36 80 59 80L61 80C46.64 80 35 68.36 35 54V18Z" stroke="currentColor" stroke-width="3" stroke-linejoin="round" fill="none"/>
    <!-- Anses -->
    <path d="M35 24H22C22 24 16 24 16 34C16 46 24 54 35 56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <path d="M85 24H98C98 24 104 24 104 34C104 46 96 54 85 56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <!-- Pied -->
    <line x1="60" y1="80" x2="60" y2="96" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
    <path d="M44 96H76" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
    <!-- Socle -->
    <rect x="38" y="96" width="44" height="8" rx="3" fill="currentColor" opacity="0.15" stroke="currentColor" stroke-width="2"/>
    <!-- Étoile intérieure -->
    <path d="M60 32L62.8 39.5H71L64.5 44L67.3 51.5L60 47L52.7 51.5L55.5 44L49 39.5H57.2L60 32Z" fill="currentColor" opacity="0.25" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
    <!-- Brillance -->
    <path d="M42 28C44 26 48 25 52 27" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity="0.4"/>
    <path d="M44 34C45 32.5 47 32 49 32.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity="0.3"/>
  </svg>`,

  // 🥇 Médaille or
  medal_gold: `<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="16" cy="20" r="10" stroke="#f0c040" stroke-width="2" fill="none"/>
    <circle cx="16" cy="20" r="7" fill="#f0c040" opacity="0.15" stroke="#f0c040" stroke-width="1"/>
    <path d="M10 4L13 14" stroke="#f0c040" stroke-width="2" stroke-linecap="round"/>
    <path d="M22 4L19 14" stroke="#f0c040" stroke-width="2" stroke-linecap="round"/>
    <path d="M10 4H22" stroke="#f0c040" stroke-width="2" stroke-linecap="round"/>
    <text x="16" y="24.5" text-anchor="middle" fill="#f0c040" font-size="9" font-weight="bold" font-family="Arial">1</text>
  </svg>`,

  // 🥈 Médaille argent
  medal_silver: `<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="16" cy="20" r="10" stroke="#c0c8d0" stroke-width="2" fill="none"/>
    <circle cx="16" cy="20" r="7" fill="#c0c8d0" opacity="0.15" stroke="#c0c8d0" stroke-width="1"/>
    <path d="M10 4L13 14" stroke="#c0c8d0" stroke-width="2" stroke-linecap="round"/>
    <path d="M22 4L19 14" stroke="#c0c8d0" stroke-width="2" stroke-linecap="round"/>
    <path d="M10 4H22" stroke="#c0c8d0" stroke-width="2" stroke-linecap="round"/>
    <text x="16" y="24.5" text-anchor="middle" fill="#c0c8d0" font-size="9" font-weight="bold" font-family="Arial">2</text>
  </svg>`,

  // 🥉 Médaille bronze
  medal_bronze: `<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="16" cy="20" r="10" stroke="#cd7f32" stroke-width="2" fill="none"/>
    <circle cx="16" cy="20" r="7" fill="#cd7f32" opacity="0.15" stroke="#cd7f32" stroke-width="1"/>
    <path d="M10 4L13 14" stroke="#cd7f32" stroke-width="2" stroke-linecap="round"/>
    <path d="M22 4L19 14" stroke="#cd7f32" stroke-width="2" stroke-linecap="round"/>
    <path d="M10 4H22" stroke="#cd7f32" stroke-width="2" stroke-linecap="round"/>
    <text x="16" y="24.5" text-anchor="middle" fill="#cd7f32" font-size="9" font-weight="bold" font-family="Arial">3</text>
  </svg>`,

  // Table baby-foot (feature icon accueil)
  foosball: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- Table -->
    <rect x="4" y="14" width="40" height="20" rx="3" stroke="currentColor" stroke-width="2" fill="none"/>
    <!-- Terrain vert -->
    <rect x="6" y="16" width="36" height="16" rx="2" fill="currentColor" opacity="0.08"/>
    <!-- Ligne centrale -->
    <line x1="24" y1="16" x2="24" y2="32" stroke="currentColor" stroke-width="1" opacity="0.4"/>
    <circle cx="24" cy="24" r="3" stroke="currentColor" stroke-width="1" opacity="0.4" fill="none"/>
    <!-- Barres -->
    <line x1="12" y1="10" x2="12" y2="38" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="20" y1="10" x2="20" y2="38" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="28" y1="10" x2="28" y2="38" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="36" y1="10" x2="36" y2="38" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <!-- Joueurs rouges -->
    <circle cx="12" cy="21" r="3.5" fill="#e74c3c" stroke="currentColor" stroke-width="1"/>
    <circle cx="12" cy="27" r="3.5" fill="#e74c3c" stroke="currentColor" stroke-width="1"/>
    <circle cx="20" cy="24" r="3.5" fill="#e74c3c" stroke="currentColor" stroke-width="1"/>
    <!-- Joueurs bleus -->
    <circle cx="28" cy="24" r="3.5" fill="#3498db" stroke="currentColor" stroke-width="1"/>
    <circle cx="36" cy="21" r="3.5" fill="#3498db" stroke="currentColor" stroke-width="1"/>
    <circle cx="36" cy="27" r="3.5" fill="#3498db" stroke="currentColor" stroke-width="1"/>
    <!-- Balle -->
    <circle cx="24" cy="24" r="2.5" fill="white" stroke="currentColor" stroke-width="1"/>
    <!-- Poignées -->
    <rect x="1" y="20" width="4" height="8" rx="2" fill="currentColor" opacity="0.4"/>
    <rect x="43" y="20" width="4" height="8" rx="2" fill="currentColor" opacity="0.4"/>
  </svg>`,

  // Chrono / réservation 25min
  timer: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="26" r="16" stroke="currentColor" stroke-width="2.5" fill="none"/>
    <path d="M18 8H30" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="24" y1="8" x2="24" y2="12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M24 18V27L30 33" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="24" cy="26" r="2" fill="currentColor" opacity="0.5"/>
    <!-- Ticks -->
    <line x1="24" y1="12" x2="24" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
    <line x1="38" y1="26" x2="36" y2="26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
    <line x1="10" y1="26" x2="12" y2="26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
    <line x1="24" y1="40" x2="24" y2="38" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
  </svg>`,

  // Signal wifi / temps réel
  live: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="36" r="3" fill="currentColor"/>
    <path d="M16 28C18.12 25.88 21 24.5 24 24.5C27 24.5 29.88 25.88 32 28" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none"/>
    <path d="M10 22C13.78 18.22 18.62 16 24 16C29.38 16 34.22 18.22 38 22" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none"/>
    <path d="M4 16C9.44 10.56 16.34 7.5 24 7.5C31.66 7.5 38.56 10.56 44 16" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none"/>
    <!-- Point live clignotant -->
    <circle cx="38" cy="10" r="4" fill="#e74c3c" opacity="0.9"/>
    <circle cx="38" cy="10" r="2" fill="white"/>
  </svg>`,

  // Classement / podium
  podium: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- Marches podium -->
    <rect x="4" y="28" width="12" height="14" rx="2" fill="currentColor" opacity="0.15" stroke="currentColor" stroke-width="2"/>
    <rect x="18" y="20" width="12" height="22" rx="2" fill="currentColor" opacity="0.25" stroke="currentColor" stroke-width="2"/>
    <rect x="32" y="32" width="12" height="10" rx="2" fill="currentColor" opacity="0.1" stroke="currentColor" stroke-width="2"/>
    <!-- Chiffres -->
    <text x="10" y="38" text-anchor="middle" fill="currentColor" font-size="7" font-weight="bold" font-family="Arial" opacity="0.6">2</text>
    <text x="24" y="38" text-anchor="middle" fill="currentColor" font-size="7" font-weight="bold" font-family="Arial" opacity="0.8">1</text>
    <text x="38" y="38" text-anchor="middle" fill="currentColor" font-size="7" font-weight="bold" font-family="Arial" opacity="0.5">3</text>
    <!-- Personnages -->
    <circle cx="10" cy="22" r="4" stroke="currentColor" stroke-width="1.8" fill="none"/>
    <path d="M6 26.5C7 25 8.5 24.5 10 24.5C11.5 24.5 13 25 14 26.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
    <circle cx="24" cy="14" r="4" stroke="currentColor" stroke-width="1.8" fill="none"/>
    <path d="M20 18.5C21 17 22.5 16.5 24 16.5C25.5 16.5 27 17 28 18.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
    <circle cx="38" cy="26" r="4" stroke="currentColor" stroke-width="1.8" fill="none"/>
    <path d="M34 30.5C35 29 36.5 28.5 38 28.5C39.5 28.5 41 29 42 30.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
    <!-- Couronne sur le 1er -->
    <path d="M20 11L22 8L24 10.5L26 8L28 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`,

  // Multi-joueurs
  multiplayer: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="16" cy="16" r="6" stroke="currentColor" stroke-width="2" fill="none"/>
    <path d="M6 36C7.5 30 11 27 16 27C21 27 24.5 30 26 36" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
    <circle cx="33" cy="16" r="6" stroke="currentColor" stroke-width="2" fill="none"/>
    <path d="M23 36C24.5 30 28 27 33 27C38 27 41.5 30 43 36" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>
    <path d="M24 22L24 26" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
    <path d="M22 24L26 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
  </svg>`,
};

// Helper pour créer un élément SVG inline
function bfIcon(name, size = 24, className = '') {
  const svg = BFIcons[name];
  if (!svg) return '';
  const wrapper = document.createElement('span');
  wrapper.className = 'bf-icon ' + className;
  wrapper.style.cssText = `display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;flex-shrink:0`;
  wrapper.innerHTML = svg;
  const svgEl = wrapper.querySelector('svg');
  if (svgEl) {
    svgEl.setAttribute('width', size);
    svgEl.setAttribute('height', size);
    svgEl.style.width = size + 'px';
    svgEl.style.height = size + 'px';
  }
  return wrapper.outerHTML;
}

// Fonction d'init exposée globalement (réutilisable après injection dynamique)
function initBFIcons(root = document) {
  root.querySelectorAll('[data-bficon]').forEach(el => {
    if (el.querySelector('svg')) return; // déjà initialisé
    const name = el.getAttribute('data-bficon');
    const size = parseInt(el.getAttribute('data-size') || '24');
    const svg = BFIcons[name];
    if (!svg) return;
    el.innerHTML = svg;
    const svgEl = el.querySelector('svg');
    if (svgEl) {
      svgEl.setAttribute('width', size);
      svgEl.setAttribute('height', size);
      svgEl.style.width = size + 'px';
      svgEl.style.height = size + 'px';
    }
  });
}

// Injection automatique au chargement
document.addEventListener('DOMContentLoaded', () => initBFIcons());

// MutationObserver pour les éléments injectés dynamiquement (ex: leaderboard)
const _bfObserver = new MutationObserver(mutations => {
  mutations.forEach(m => m.addedNodes.forEach(n => {
    if (n.nodeType === 1) {
      if (n.hasAttribute('data-bficon')) initBFIcons(n.parentElement || document);
      else if (n.querySelectorAll) initBFIcons(n);
    }
  }));
});
_bfObserver.observe(document.body, { childList: true, subtree: true });
