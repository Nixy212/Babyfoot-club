"""
Module de communication Arduino/Simulateur pour Babyfoot Club
Gère les tokens, la queue d'actions et l'état de la partie
"""

import secrets
import time
from datetime import datetime, timedelta
from threading import Lock
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# ÉTAT GLOBAL DU SYSTÈME ARDUINO
# ═══════════════════════════════════════════════════════════

class ArduinoState:
    """Gère l'état complet de la communication avec l'Arduino"""
    
    def __init__(self):
        self.lock = Lock()
        
        # Tokens actifs : game_id -> token
        self.active_tokens = {}
        
        # Queue d'actions : game_id -> [{"action": "unlock_ball", "id": "cmd_123", "timestamp": 1234567890}]
        self.action_queues = {}
        
        # Actions exécutées : game_id -> set(["cmd_123", "cmd_456"])
        self.executed_commands = {}
        
        # État des parties : game_id -> {"score_team1": 0, "score_team2": 0, "ball_locked": True, "active": True}
        self.game_states = {}
        
        # Dernière connexion : game_id -> timestamp
        self.last_seen = {}
        
        # Timeout des tokens (en secondes)
        self.token_timeout = 3600  # 1 heure
        
        logger.info("ArduinoState initialisé")
    
    # ═══════════════════════════════════════════════════════════
    # GESTION DES TOKENS
    # ═══════════════════════════════════════════════════════════
    
    def generate_token(self, game_id):
        """Génère un nouveau token pour une partie"""
        with self.lock:
            token = secrets.token_urlsafe(32)
            self.active_tokens[game_id] = {
                "token": token,
                "created_at": time.time(),
                "expires_at": time.time() + self.token_timeout
            }
            logger.info(f"Token généré pour game_id={game_id}")
            return token
    
    def validate_token(self, game_id, token):
        """Vérifie si un token est valide"""
        with self.lock:
            if game_id not in self.active_tokens:
                logger.warning(f"Tentative d'accès sans token pour game_id={game_id}")
                return False
            
            token_data = self.active_tokens[game_id]
            
            # Vérifier expiration
            if time.time() > token_data["expires_at"]:
                logger.warning(f"Token expiré pour game_id={game_id}")
                del self.active_tokens[game_id]
                return False
            
            # Vérifier correspondance
            if token_data["token"] != token:
                logger.warning(f"Token invalide pour game_id={game_id}")
                return False
            
            # Mettre à jour last_seen
            self.last_seen[game_id] = time.time()
            
            return True
    
    def revoke_token(self, game_id):
        """Révoque un token (fin de partie)"""
        with self.lock:
            if game_id in self.active_tokens:
                del self.active_tokens[game_id]
                logger.info(f"Token révoqué pour game_id={game_id}")
    
    # ═══════════════════════════════════════════════════════════
    # GESTION DE LA QUEUE D'ACTIONS
    # ═══════════════════════════════════════════════════════════
    
    def add_action(self, game_id, action):
        """Ajoute une action à la queue"""
        with self.lock:
            if game_id not in self.action_queues:
                self.action_queues[game_id] = []
            
            if game_id not in self.executed_commands:
                self.executed_commands[game_id] = set()
            
            # Générer un ID unique pour l'action
            action_id = f"cmd_{secrets.token_hex(8)}"
            
            action_data = {
                "id": action_id,
                "action": action,
                "timestamp": time.time(),
                "game_id": game_id
            }
            
            self.action_queues[game_id].append(action_data)
            logger.info(f"Action ajoutée: {action} (id={action_id}) pour game_id={game_id}")
            
            return action_id
    
    def get_pending_actions(self, game_id):
        """Récupère toutes les actions non exécutées"""
        with self.lock:
            if game_id not in self.action_queues:
                return []
            
            executed = self.executed_commands.get(game_id, set())
            
            # Filtrer les actions non exécutées
            pending = [
                action for action in self.action_queues[game_id]
                if action["id"] not in executed
            ]
            
            return pending
    
    def mark_executed(self, game_id, action_id):
        """Marque une action comme exécutée"""
        with self.lock:
            if game_id not in self.executed_commands:
                self.executed_commands[game_id] = set()
            
            self.executed_commands[game_id].add(action_id)
            logger.info(f"Action marquée comme exécutée: {action_id} pour game_id={game_id}")
    
    def clear_queue(self, game_id):
        """Nettoie la queue d'une partie terminée"""
        with self.lock:
            if game_id in self.action_queues:
                del self.action_queues[game_id]
            if game_id in self.executed_commands:
                del self.executed_commands[game_id]
            logger.info(f"Queue nettoyée pour game_id={game_id}")
    
    # ═══════════════════════════════════════════════════════════
    # GESTION DE L'ÉTAT DE LA PARTIE
    # ═══════════════════════════════════════════════════════════
    
    def init_game_state(self, game_id):
        """Initialise l'état d'une nouvelle partie"""
        with self.lock:
            self.game_states[game_id] = {
                "score_team1": 0,
                "score_team2": 0,
                "ball_locked": True,
                "active": True,
                "started_at": time.time()
            }
            logger.info(f"État de partie initialisé pour game_id={game_id}")
    
    def update_score(self, game_id, team):
        """Met à jour le score d'une équipe"""
        with self.lock:
            if game_id not in self.game_states:
                logger.warning(f"Tentative de mise à jour de score pour game_id inexistant: {game_id}")
                return False
            
            if team == "team1":
                self.game_states[game_id]["score_team1"] += 1
            elif team == "team2":
                self.game_states[game_id]["score_team2"] += 1
            else:
                return False
            
            logger.info(f"Score mis à jour pour game_id={game_id}: {self.game_states[game_id]}")
            return True
    
    def set_ball_state(self, game_id, locked):
        """Définit l'état de la balle (locked/unlocked)"""
        with self.lock:
            if game_id in self.game_states:
                self.game_states[game_id]["ball_locked"] = locked
                logger.info(f"État balle pour game_id={game_id}: {'verrouillé' if locked else 'déverrouillé'}")
    
    def get_game_state(self, game_id):
        """Récupère l'état complet d'une partie"""
        with self.lock:
            return self.game_states.get(game_id, None)
    
    def end_game(self, game_id):
        """Termine une partie"""
        with self.lock:
            if game_id in self.game_states:
                self.game_states[game_id]["active"] = False
                logger.info(f"Partie terminée: game_id={game_id}")
            
            # Révoquer le token
            self.revoke_token(game_id)
            
            # Nettoyer la queue après 5 minutes (permet debug)
            # On garde les données temporairement
    
    def cleanup_old_games(self, max_age_seconds=3600):
        """Nettoie les parties terminées depuis longtemps"""
        with self.lock:
            now = time.time()
            to_remove = []
            
            for game_id, state in self.game_states.items():
                if not state["active"]:
                    age = now - state.get("started_at", now)
                    if age > max_age_seconds:
                        to_remove.append(game_id)
            
            for game_id in to_remove:
                del self.game_states[game_id]
                self.clear_queue(game_id)
                if game_id in self.last_seen:
                    del self.last_seen[game_id]
                logger.info(f"Nettoyage de la partie ancienne: game_id={game_id}")
    
    # ═══════════════════════════════════════════════════════════
    # STATISTIQUES ET DEBUG
    # ═══════════════════════════════════════════════════════════
    
    def get_stats(self):
        """Retourne des statistiques sur l'état du système"""
        with self.lock:
            return {
                "active_tokens": len(self.active_tokens),
                "active_games": sum(1 for s in self.game_states.values() if s["active"]),
                "total_games": len(self.game_states),
                "pending_actions": {
                    game_id: len(self.get_pending_actions(game_id))
                    for game_id in self.action_queues.keys()
                },
                "last_cleanup": time.time()
            }
    
    def get_all_queues(self):
        """Retourne toutes les queues (pour debug)"""
        with self.lock:
            return {
                game_id: {
                    "pending": self.get_pending_actions(game_id),
                    "executed": list(self.executed_commands.get(game_id, set())),
                    "game_state": self.game_states.get(game_id, {})
                }
                for game_id in self.action_queues.keys()
            }


# Instance globale
arduino_state = ArduinoState()


# ═══════════════════════════════════════════════════════════
# FONCTIONS HELPER
# ═══════════════════════════════════════════════════════════

def start_game_arduino(game_id):
    """Démarre une partie côté Arduino"""
    token = arduino_state.generate_token(game_id)
    arduino_state.init_game_state(game_id)
    arduino_state.add_action(game_id, "unlock_ball")
    return token


def end_game_arduino(game_id):
    """Termine une partie côté Arduino"""
    arduino_state.add_action(game_id, "lock_ball")
    arduino_state.end_game(game_id)


def goal_scored(game_id, team):
    """Enregistre un but"""
    arduino_state.update_score(game_id, team)
    
    # Débloquer la balle pour le prochain point
    arduino_state.add_action(game_id, "unlock_ball")
    arduino_state.set_ball_state(game_id, False)


def check_connection_health(game_id):
    """Vérifie si l'Arduino est connecté"""
    last_seen = arduino_state.last_seen.get(game_id, 0)
    if last_seen == 0:
        return False
    
    # Si pas de nouvelles depuis 60 secondes, considéré déconnecté
    return (time.time() - last_seen) < 60
