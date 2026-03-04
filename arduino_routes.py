"""
Routes API pour la communication Arduino/Simulateur
Ces endpoints sont utilisés exclusivement par l'Arduino/Simulateur
"""

from flask import Blueprint, request, jsonify
import logging

# Import du gestionnaire Arduino
from arduino_manager import arduino_state

logger = logging.getLogger(__name__)

# Blueprint pour les routes Arduino
arduino_bp = Blueprint('arduino', __name__, url_prefix='/api/arduino')


# ═══════════════════════════════════════════════════════════
# HELPER: VALIDATION DU TOKEN
# ═══════════════════════════════════════════════════════════

def validate_arduino_token():
    """Valide le token dans l'en-tête Authorization"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        logger.warning(f"Requête Arduino sans Authorization header depuis {request.remote_addr}")
        return None, jsonify({"error": "Missing Authorization header"}), 401
    
    if not auth_header.startswith('Bearer '):
        logger.warning(f"Format Authorization invalide depuis {request.remote_addr}")
        return None, jsonify({"error": "Invalid Authorization format. Use: Bearer <token>"}), 401
    
    token = auth_header[7:]  # Enlever "Bearer "
    
    # Récupérer game_id depuis les paramètres
    data = request.get_json(silent=True) or {}
    game_id = data.get('game_id') or request.args.get('game_id')
    
    if not game_id:
        logger.warning(f"Requête Arduino sans game_id depuis {request.remote_addr}")
        return None, jsonify({"error": "Missing game_id"}), 400
    
    try:
        game_id = int(game_id)
    except ValueError:
        return None, jsonify({"error": "Invalid game_id format"}), 400
    
    # Valider le token
    if not arduino_state.validate_token(game_id, token):
        logger.warning(f"Token invalide pour game_id={game_id} depuis {request.remote_addr}")
        return None, jsonify({"error": "Invalid or expired token"}), 401
    
    return game_id, None, None


# ═══════════════════════════════════════════════════════════
# ENDPOINT: GET /api/arduino/get_command
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/get_command', methods=['GET'])
def get_command():
    """
    Récupère la prochaine commande à exécuter
    
    Headers:
        Authorization: Bearer <token>
    
    Query params:
        game_id: ID de la partie
    
    Response:
        200: {"action": "unlock_ball", "game_id": 5, "command_id": "cmd_abc123"}
        200: {"action": "none", "game_id": 5} (si aucune action)
        401: {"error": "Invalid token"}
    """
    game_id, error_response, status_code = validate_arduino_token()
    
    if error_response:
        return error_response, status_code
    
    # Récupérer les actions en attente
    pending_actions = arduino_state.get_pending_actions(game_id)
    
    if not pending_actions:
        logger.debug(f"Aucune action pour game_id={game_id}")
        return jsonify({
            "action": "none",
            "game_id": game_id
        }), 200
    
    # Retourner la première action non exécutée
    next_action = pending_actions[0]
    
    logger.info(f"Commande envoyée à Arduino: {next_action['action']} (id={next_action['id']}) pour game_id={game_id}")
    
    return jsonify({
        "action": next_action["action"],
        "game_id": game_id,
        "command_id": next_action["id"],
        "timestamp": next_action["timestamp"]
    }), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT: POST /api/arduino/confirm_command
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/confirm_command', methods=['POST'])
def confirm_command():
    """
    Confirme l'exécution d'une commande
    
    Headers:
        Authorization: Bearer <token>
    
    Body:
        {
            "game_id": 5,
            "command_id": "cmd_abc123"
        }
    
    Response:
        200: {"status": "ok"}
        401: {"error": "Invalid token"}
    """
    game_id, error_response, status_code = validate_arduino_token()
    
    if error_response:
        return error_response, status_code
    
    data = request.get_json()
    command_id = data.get('command_id')
    
    if not command_id:
        return jsonify({"error": "Missing command_id"}), 400
    
    # Marquer comme exécuté
    arduino_state.mark_executed(game_id, command_id)
    
    logger.info(f"Commande confirmée: {command_id} pour game_id={game_id}")
    
    return jsonify({"status": "ok"}), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT: POST /api/arduino/update_score
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/update_score', methods=['POST'])
def update_score():
    """
    Enregistre un but marqué (détecté par le capteur Arduino)
    
    Headers:
        Authorization: Bearer <token>
    
    Body:
        {
            "game_id": 5,
            "event": "goal",
            "team": "team1" ou "team2"
        }
    
    Response:
        200: {"status": "ok", "new_score": {"team1": 1, "team2": 0}}
        401: {"error": "Invalid token"}
    """
    game_id, error_response, status_code = validate_arduino_token()
    
    if error_response:
        return error_response, status_code
    
    data = request.get_json()
    event = data.get('event')
    team = data.get('team')
    
    if event != 'goal':
        return jsonify({"error": "Unknown event type"}), 400
    
    if team not in ['team1', 'team2']:
        return jsonify({"error": "Invalid team (must be team1 or team2)"}), 400
    
    # Mettre à jour le score
    success = arduino_state.update_score(game_id, team)
    
    if not success:
        return jsonify({"error": "Failed to update score"}), 500
    
    # Récupérer le nouvel état
    game_state = arduino_state.get_game_state(game_id)
    
    logger.info(f"But marqué par {team} pour game_id={game_id}: {game_state['score_team1']}-{game_state['score_team2']}")
    
    # Débloquer la balle pour le prochain point
    arduino_state.add_action(game_id, "unlock_ball")
    arduino_state.set_ball_state(game_id, False)
    
    return jsonify({
        "status": "ok",
        "new_score": {
            "team1": game_state["score_team1"],
            "team2": game_state["score_team2"]
        }
    }), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT: GET /api/arduino/game_state
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/game_state', methods=['GET'])
def get_game_state():
    """
    Récupère l'état complet de la partie (après reconnexion)
    
    Headers:
        Authorization: Bearer <token>
    
    Query params:
        game_id: ID de la partie
    
    Response:
        200: {
            "game_id": 5,
            "active": true,
            "score_team1": 3,
            "score_team2": 2,
            "ball_locked": false,
            "pending_actions": [...]
        }
    """
    game_id, error_response, status_code = validate_arduino_token()
    
    if error_response:
        return error_response, status_code
    
    # Récupérer l'état
    game_state = arduino_state.get_game_state(game_id)
    
    if not game_state:
        return jsonify({"error": "Game not found"}), 404
    
    # Récupérer les actions en attente
    pending_actions = arduino_state.get_pending_actions(game_id)
    
    logger.info(f"État récupéré pour game_id={game_id} par Arduino")
    
    return jsonify({
        "game_id": game_id,
        "active": game_state["active"],
        "score_team1": game_state["score_team1"],
        "score_team2": game_state["score_team2"],
        "ball_locked": game_state["ball_locked"],
        "pending_actions": [
            {
                "action": a["action"],
                "command_id": a["id"],
                "timestamp": a["timestamp"]
            }
            for a in pending_actions
        ]
    }), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT: POST /api/arduino/heartbeat
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    Heartbeat pour maintenir la connexion vivante
    
    Headers:
        Authorization: Bearer <token>
    
    Body:
        {
            "game_id": 5
        }
    
    Response:
        200: {"status": "alive"}
    """
    game_id, error_response, status_code = validate_arduino_token()
    
    if error_response:
        return error_response, status_code
    
    # Le validate_token met déjà à jour last_seen
    logger.debug(f"Heartbeat reçu pour game_id={game_id}")
    
    return jsonify({"status": "alive"}), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT DEBUG: GET /api/arduino/debug/queues (admin only)
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/debug/queues', methods=['GET'])
def debug_queues():
    """
    Récupère toutes les queues d'actions (pour debug)
    
    ⚠️ Cet endpoint devrait être protégé en production
    """
    # TODO: Ajouter une authentification admin
    queues = arduino_state.get_all_queues()
    stats = arduino_state.get_stats()
    
    return jsonify({
        "stats": stats,
        "queues": queues
    }), 200


# ═══════════════════════════════════════════════════════════
# ENDPOINT DEBUG: GET /api/arduino/debug/stats
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/debug/stats', methods=['GET'])
def debug_stats():
    """
    Récupère les statistiques du système Arduino
    """
    stats = arduino_state.get_stats()
    
    return jsonify(stats), 200
