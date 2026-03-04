"""
Module de communication Arduino/Simulateur pour Babyfoot Club
Gère les tokens, la queue d'actions et l'état de la partie
"""

import secrets
import time
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

        # Tokens actifs : game_id -> {"token": str, "created_at": float, "expires_at": float}
        self.active_tokens = {}

        # Queue d'actions : game_id -> [{"action": str, "id": str, "timestamp": float}]
        self.action_queues = {}

        # Actions exécutées : game_id -> set(["cmd_abc", ...])
        self.executed_commands = {}

        # État des parties : game_id -> {"score_team1": 0, "score_team2": 0, "ball_locked": True, "active": True}
        self.game_states = {}

        # Dernière connexion heartbeat : game_id -> timestamp
        self.last_seen = {}

        # Timeout des tokens (en secondes)
        self.token_timeout = 3600  # 1 heure

        logger.info("ArduinoState initialisé")

    # ═══════════════════════════════════════════════════════════
    # GESTION DES TOKENS
    # ═══════════════════════════════════════════════════════════

    def generate_token(self, game_id):
        """Génère un nouveau token unique pour une partie"""
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
        """Vérifie si un token est valide et met à jour last_seen"""
        with self.lock:
            if game_id not in self.active_tokens:
                logger.warning(f"Accès sans token pour game_id={game_id}")
                return False

            token_data = self.active_tokens[game_id]

            if time.time() > token_data["expires_at"]:
                logger.warning(f"Token expiré pour game_id={game_id}")
                del self.active_tokens[game_id]
                return False

            if token_data["token"] != token:
                logger.warning(f"Token invalide pour game_id={game_id}")
                return False

            self.last_seen[game_id] = time.time()
            return True

    def revoke_token(self, game_id):
        """Révoque un token (fin de partie ou stop manuel)"""
        with self.lock:
            if game_id in self.active_tokens:
                del self.active_tokens[game_id]
                logger.info(f"Token révoqué pour game_id={game_id}")

    def get_token(self, game_id):
        """Retourne le token actif pour une partie (ou None si inexistant/expiré)"""
        with self.lock:
            data = self.active_tokens.get(game_id)
            if data and time.time() <= data["expires_at"]:
                return data["token"]
            return None

    # ═══════════════════════════════════════════════════════════
    # GESTION DE LA QUEUE D'ACTIONS
    # ═══════════════════════════════════════════════════════════

    def add_action(self, game_id, action):
        """Ajoute une action à la queue et retourne son ID unique"""
        with self.lock:
            if game_id not in self.action_queues:
                self.action_queues[game_id] = []
            if game_id not in self.executed_commands:
                self.executed_commands[game_id] = set()

            action_id = f"cmd_{secrets.token_hex(8)}"
            action_data = {
                "id": action_id,
                "action": action,
                "timestamp": time.time(),
                "game_id": game_id
            }
            self.action_queues[game_id].append(action_data)
            logger.info(f"Action ajoutée: {action} (id={action_id}) game_id={game_id}")
            return action_id

    def get_pending_actions(self, game_id):
        """Récupère toutes les actions non encore exécutées (dans l'ordre FIFO)"""
        with self.lock:
            if game_id not in self.action_queues:
                return []
            executed = self.executed_commands.get(game_id, set())
            return [a for a in self.action_queues[game_id] if a["id"] not in executed]

    def mark_executed(self, game_id, action_id):
        """Marque une action comme exécutée (idempotent — protège contre les doublons)"""
        with self.lock:
            if game_id not in self.executed_commands:
                self.executed_commands[game_id] = set()
            self.executed_commands[game_id].add(action_id)
            logger.info(f"Action exécutée: {action_id} game_id={game_id}")

    def clear_queue(self, game_id):
        """Nettoie la queue d'une partie (appelé lors du cleanup)"""
        with self.lock:
            self.action_queues.pop(game_id, None)
            self.executed_commands.pop(game_id, None)
            logger.info(f"Queue nettoyée pour game_id={game_id}")

    # ═══════════════════════════════════════════════════════════
    # GESTION DE L'ÉTAT DE LA PARTIE
    # ═══════════════════════════════════════════════════════════

    def init_game_state(self, game_id):
        """Initialise l'état d'une nouvelle partie côté Arduino"""
        with self.lock:
            self.game_states[game_id] = {
                "score_team1": 0,
                "score_team2": 0,
                "ball_locked": True,
                "active": True,
                "started_at": time.time()
            }
            logger.info(f"État initialisé pour game_id={game_id}")

    def update_score(self, game_id, team):
        """Met à jour le score Arduino interne"""
        with self.lock:
            if game_id not in self.game_states:
                logger.warning(f"Score update pour game_id inconnu: {game_id}")
                return False
            if team == "team1":
                self.game_states[game_id]["score_team1"] += 1
            elif team == "team2":
                self.game_states[game_id]["score_team2"] += 1
            else:
                return False
            logger.info(f"Score Arduino: game_id={game_id} {self.game_states[game_id]}")
            return True

    def set_ball_state(self, game_id, locked):
        """Définit l'état de la balle"""
        with self.lock:
            if game_id in self.game_states:
                self.game_states[game_id]["ball_locked"] = locked

    def get_game_state(self, game_id):
        """Récupère l'état complet d'une partie"""
        with self.lock:
            return self.game_states.get(game_id)

    def end_game(self, game_id):
        """Marque une partie comme terminée"""
        with self.lock:
            if game_id in self.game_states:
                self.game_states[game_id]["active"] = False
                logger.info(f"Partie Arduino terminée: game_id={game_id}")

    def cleanup_old_games(self, max_age_seconds=3600):
        """Nettoie les parties terminées depuis longtemps"""
        with self.lock:
            now = time.time()
            to_remove = [
                gid for gid, state in self.game_states.items()
                if not state["active"] and (now - state.get("started_at", now)) > max_age_seconds
            ]
            for gid in to_remove:
                del self.game_states[gid]
                self.action_queues.pop(gid, None)
                self.executed_commands.pop(gid, None)
                self.last_seen.pop(gid, None)
                logger.info(f"Nettoyage partie ancienne: game_id={gid}")

    # ═══════════════════════════════════════════════════════════
    # STATISTIQUES ET DEBUG
    # ═══════════════════════════════════════════════════════════

    def get_stats(self):
        """Retourne des statistiques sur l'état du système"""
        with self.lock:
            pending_counts = {}
            for gid in self.action_queues:
                executed = self.executed_commands.get(gid, set())
                pending_counts[str(gid)] = sum(
                    1 for a in self.action_queues[gid] if a["id"] not in executed
                )
            return {
                "active_tokens": len(self.active_tokens),
                "active_games": sum(1 for s in self.game_states.values() if s["active"]),
                "total_games": len(self.game_states),
                "pending_actions_by_game": pending_counts,
                "connected_game_ids": [str(k) for k in self.active_tokens.keys()],
                "last_seen": {str(k): v for k, v in self.last_seen.items()},
                "server_time": time.time()
            }

    def get_all_queues(self):
        """Retourne toutes les queues (pour debug admin)"""
        with self.lock:
            result = {}
            for gid in self.action_queues:
                executed = self.executed_commands.get(gid, set())
                pending = [a for a in self.action_queues[gid] if a["id"] not in executed]
                result[str(gid)] = {
                    "pending": pending,
                    "executed_ids": list(executed),
                    "total_queued": len(self.action_queues[gid]),
                    "game_state": self.game_states.get(gid, {}),
                    "last_seen": self.last_seen.get(gid)
                }
            return result


# ── Instance globale partagée ─────────────────────────────
arduino_state = ArduinoState()


# ═══════════════════════════════════════════════════════════
# FONCTIONS HELPER (appelées depuis app.py)
# ═══════════════════════════════════════════════════════════

def start_game_arduino(game_id):
    """
    Initialise la session Arduino pour une partie :
    - Génère un token unique lié à game_id
    - Initialise la queue et l'état de la partie
    - Enfile unlock_servo comme première commande
    Retourne le token généré (à émettre via WebSocket pour debug).
    """
    token = arduino_state.generate_token(game_id)
    arduino_state.init_game_state(game_id)
    arduino_state.add_action(game_id, "unlock_servo")
    logger.info(f"[Arduino] Partie démarrée: game_id={game_id}, token généré")
    return token


def end_game_arduino(game_id):
    """
    Clôture la session Arduino d'une partie :
    - Enfile lock_servo en queue (pour que l'Arduino execute avant de couper)
    - Marque la partie inactive
    - Révoque le token
    """
    arduino_state.add_action(game_id, "lock_servo")
    arduino_state.end_game(game_id)
    arduino_state.revoke_token(game_id)
    logger.info(f"[Arduino] Partie terminée et token révoqué: game_id={game_id}")


def goal_scored_arduino(game_id, team):
    """Enregistre un but et ajoute unlock_servo pour libérer la balle"""
    arduino_state.update_score(game_id, team)
    arduino_state.add_action(game_id, "unlock_servo")
    arduino_state.set_ball_state(game_id, False)


def check_connection_health(game_id):
    """Retourne True si un heartbeat a été reçu dans les 60 dernières secondes"""
    last = arduino_state.last_seen.get(game_id, 0)
    return last > 0 and (time.time() - last) < 60
