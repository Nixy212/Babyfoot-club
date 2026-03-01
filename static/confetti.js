/* =========================================
   CONFETTI & VICTORY ANIMATIONS
   Baby-Foot Club - Célébrations de victoire
   ========================================= */

/**
 * Crée et lance les confettis de victoire
 * @param {number} duration - Durée de l'animation en ms (défaut: 4000)
 * @param {number} count - Nombre de confettis (défaut: 150)
 */
function launchConfetti(duration = 4000, count = 150) {
  // Créer le container de confettis s'il n'existe pas
  let container = document.getElementById('confetti-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'confetti-container';
    container.className = 'confetti-container';
    document.body.appendChild(container);
  }

  // Nettoyer les anciens confettis
  container.innerHTML = '';

  const colors = ['color-1', 'color-2', 'color-3', 'color-4', 'color-5', 'color-6'];
  const shapes = ['square', 'circle', 'triangle'];
  const origins = ['from-left', 'from-right', 'from-top'];

  // Créer les confettis
  for (let i = 0; i < count; i++) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';
    
    // Forme aléatoire
    const shape = shapes[Math.floor(Math.random() * shapes.length)];
    confetti.classList.add(shape);
    
    // Couleur aléatoire
    const color = colors[Math.floor(Math.random() * colors.length)];
    confetti.classList.add(color);
    
    // Origine aléatoire
    const origin = origins[Math.floor(Math.random() * origins.length)];
    confetti.classList.add(origin);
    
    // Position et délai aléatoires
    if (origin === 'from-top') {
      confetti.style.setProperty('--confetti-start', `${Math.random() * 100}%`);
      confetti.style.setProperty('--confetti-drift', Math.random() * 4 - 2);
    }
    
    confetti.style.animationDelay = `${Math.random() * 1000}ms`;
    confetti.style.animationDuration = `${2000 + Math.random() * 2000}ms`;
    
    // Taille aléatoire
    const size = 8 + Math.random() * 8;
    confetti.style.width = `${size}px`;
    confetti.style.height = `${size}px`;
    
    container.appendChild(confetti);
  }

  // Nettoyer après l'animation
  setTimeout(() => {
    container.remove();
  }, duration);
}

/**
 * Affiche le popup de victoire avec confettis
 * @param {string} winnerTeam - 'team1' ou 'team2'
 * @param {Array} winners - Liste des noms des gagnants
 * @param {string} finalScore - Score final (ex: "10 - 5")
 */
function showVictoryPopup(winnerTeam, winners, finalScore) {
  // Créer l'overlay
  const overlay = document.createElement('div');
  overlay.className = 'victory-overlay';
  overlay.id = 'victory-overlay';
  
  // Créer le popup
  const popup = document.createElement('div');
  popup.className = 'victory-popup';
  
  // Déterminer l'équipe gagnante
  const teamColor = winnerTeam === 'team1' ? 'bronze' : 'gold';
  const teamEmoji = winnerTeam === 'team1' ? '🔴' : '🔵';
  
  // Contenu du popup
  popup.innerHTML = `
    <div class="victory-trophy">🏆</div>
    <h1 class="victory-title">VICTOIRE !</h1>
    <div class="victory-winners">
      ${teamEmoji} ${winners.join(' & ')}
    </div>
    <div class="victory-score">${finalScore}</div>
    <div class="victory-actions">
      <button class="btn btn-primary btn-lg" onclick="closeVictoryPopup(); location.href='/dashboard'">
        🏠 Retour Dashboard
      </button>
      <button class="btn btn-secondary btn-lg" onclick="closeVictoryPopup()">
        ✕ Fermer
      </button>
    </div>
  `;
  
  overlay.appendChild(popup);
  document.body.appendChild(overlay);
  
  // Lancer les confettis
  launchConfetti(5000, 200);
  
  // Ajouter le son de victoire (optionnel)
  playVictorySound();
  
  // Vibration sur mobile
  if (navigator.vibrate) {
    navigator.vibrate([200, 100, 200, 100, 400]);
  }
  
  // Fermer au clic sur l'overlay
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeVictoryPopup();
    }
  });
}

/**
 * Ferme le popup de victoire
 */
function closeVictoryPopup() {
  const overlay = document.getElementById('victory-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 300);
  }
  
  const confettiContainer = document.getElementById('confetti-container');
  if (confettiContainer) {
    confettiContainer.remove();
  }
}

/**
 * Animation de célébration sur un but marqué
 * @param {string} team - 'team1' ou 'team2'
 * @param {HTMLElement} scoreElement - Élément score à animer
 */
function celebrateGoal(team, scoreElement) {
  // Animation du score
  if (scoreElement) {
    scoreElement.classList.add('goal-scored-animation');
    setTimeout(() => {
      scoreElement.classList.remove('goal-scored-animation');
    }, 500);
  }
  
  // Mini confettis
  launchConfetti(2000, 50);
  
  // Effet burst
  createBurstEffect(team);
  
  // Son de but (optionnel)
  playGoalSound();
  
  // Vibration courte
  if (navigator.vibrate) {
    navigator.vibrate(100);
  }
}

/**
 * Crée un effet burst de couleur
 * @param {string} team - 'team1' ou 'team2'
 */
function createBurstEffect(team) {
  const burst = document.createElement('div');
  burst.className = 'celebration-burst';
  burst.style.left = '50%';
  burst.style.top = '50%';
  burst.style.transform = 'translate(-50%, -50%)';
  
  document.body.appendChild(burst);
  
  setTimeout(() => {
    burst.remove();
  }, 600);
}

/**
 * Joue un son de victoire (si activé)
 */
function playVictorySound() {
  try {
    // Son de victoire (nécessite un fichier audio)
    // const audio = new Audio('/static/sounds/victory.mp3');
    // audio.volume = 0.5;
    // audio.play().catch(() => {});
    
    // Alternative: synthèse vocale
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance('Victoire!');
      utterance.lang = 'fr-FR';
      utterance.rate = 1.2;
      utterance.pitch = 1.5;
      utterance.volume = 0.3;
      // speechSynthesis.speak(utterance); // Décommenter pour activer
    }
  } catch (e) {
    // Ignorer les erreurs audio
  }
}

/**
 * Joue un son de but (si activé)
 */
function playGoalSound() {
  try {
    // Son de but (nécessite un fichier audio)
    // const audio = new Audio('/static/sounds/goal.mp3');
    // audio.volume = 0.4;
    // audio.play().catch(() => {});
    
    // Alternative: beep avec Web Audio API
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = 800;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.3);
  } catch (e) {
    // Ignorer les erreurs audio
  }
}

/**
 * Anime le compte à rebours avant le début du match
 * @param {Function} callback - Fonction appelée à la fin du compte à rebours
 */
function startCountdown(callback) {
  const overlay = document.createElement('div');
  overlay.className = 'victory-overlay';
  overlay.id = 'countdown-overlay';
  
  const countdown = document.createElement('div');
  countdown.className = 'victory-popup';
  countdown.innerHTML = '<div class="victory-score" id="countdown-number">3</div>';
  
  overlay.appendChild(countdown);
  document.body.appendChild(overlay);
  
  let count = 3;
  const interval = setInterval(() => {
    count--;
    const numberEl = document.getElementById('countdown-number');
    
    if (count > 0) {
      numberEl.textContent = count;
      numberEl.style.animation = 'none';
      setTimeout(() => {
        numberEl.style.animation = 'celebrate 0.5s ease-out';
      }, 10);
    } else {
      numberEl.textContent = 'GO!';
      numberEl.style.animation = 'celebrate 0.5s ease-out';
      
      setTimeout(() => {
        overlay.style.opacity = '0';
        setTimeout(() => {
          overlay.remove();
          if (callback) callback();
        }, 300);
      }, 800);
      
      clearInterval(interval);
    }
  }, 1000);
}

/**
 * Affiche une notification toast
 * @param {string} message - Message à afficher
 * @param {string} type - Type: 'ok', 'err', 'inf'
 */
function showToast(message, type = 'inf') {
  let toastWrap = document.getElementById('toast-wrap');
  if (!toastWrap) {
    toastWrap = document.createElement('div');
    toastWrap.className = 'toast-wrap';
    toastWrap.id = 'toast-wrap';
    document.body.appendChild(toastWrap);
  }
  
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  
  toastWrap.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Animation slideOut pour les toasts
const style = document.createElement('style');
style.textContent = `
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Exporter les fonctions globalement
window.launchConfetti = launchConfetti;
window.showVictoryPopup = showVictoryPopup;
window.closeVictoryPopup = closeVictoryPopup;
window.celebrateGoal = celebrateGoal;
window.startCountdown = startCountdown;
window.showToast = showToast;
