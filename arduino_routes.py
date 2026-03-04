"""
Routes API REST pour la communication Arduino/Simulateur — Babyfoot Club
Ces endpoints sont utilisés EXCLUSIVEMENT par l'Arduino physique ou le simulateur Python.
Authentification : Bearer token unique par partie (généré au lancement, révoqué à la fin).

Endpoints disponibles :
  GET  /api/arduino/get_command       — Récupère la prochaine action à exécuter
  POST /api/arduino/confirm_command   — Confirme l'exécution d'une action
  POST /api/arduino/update_score      — Signale un but détecté par le capteur
  GET  /api/arduino/game_state        — État complet (reprise après coupure)
  POST /api/arduino/heartbeat         — Maintient la connexion active
  GET  /api/arduino/debug/stats       — Stats système (admin uniquement)
  GET  /api/arduino/debug/queues      — Inspection des queues (admin uniquement)
"""

import time
import logging
from flask import Blueprint, request, jsonify, session

from arduino_manager import arduino_state

logger = logging.getLogger(__name__)

# Blueprint rattaché au préfixe /api/arduino
arduino_bp = Blueprint('arduino', __name__, url_prefix='/api/arduino')

# Anti-spam but : game_id -> timestamp du dernier but accepté
_last_goal_time = {}
_GOAL_COOLDOWN = 2.0  # secondes minimum entre deux buts d'une même partie


# ═══════════════════════════════════════════════════════════
# HELPER: VALIDATION DU TOKEN BEARER
# ═══════════════════════════════════════════════════════════

def _validate_token():
    """
    Extrait et valide le token Bearer depuis l'en-tête Authorization.
    Récupère game_id depuis le body JSON ou les query params.
    Retourne (game_id: int, None, None) si valide, sinon (None, error_response, status_code).
    """
    auth_header = request.headers.get('Authorization', '')

    if not auth_header:
        logger.warning(f"Requête Arduino sans Authorization header ({request.remote_addr})")
        return None, jsonify({"error": "Missing Authorization header"}), 401

    if not auth_header.startswith('Bearer '):
        logger.warning(f"Format Authorization invalide ({request.remote_addr})")
        return None, jsonify({"error": "Invalid format. Use: Authorization: Bearer <token>"}), 401

    token = auth_header[7:]  # Retirer "Bearer "

    # game_id : JSON body > query param
    data = request.get_json(silent=True) or {}
    raw_game_id = data.get('game_id') or request.args.get('game_id')

    if not raw_game_id:
        return None, jsonify({"error": "Missing game_id (body JSON or query param)"}), 400

    try:
        game_id = int(raw_game_id)
    except (ValueError, TypeError):
        return None, jsonify({"error": "Invalid game_id (must be integer)"}), 400

    if not arduino_state.validate_token(game_id, token):
        logger.warning(f"Token refusé pour game_id={game_id} ({request.remote_addr})")
        return None, jsonify({"error": "Invalid or expired token"}), 401

    return game_id, None, None


def _require_admin():
    """
    Vérifie si la session Flask correspond à un admin.
    Retourne (True, None) si admin, (False, error_response) sinon.
    Importe is_admin depuis app au runtime pour éviter les imports circulaires.
    """
    try:
        # Import tardif pour éviter la circularité app <-> arduino_routes
        import app as main_app
        username = session.get('username')
        if username and main_app.is_admin(username):
            return True, None
    except Exception:
        pass
    return False, (jsonify({"error": "Admin session required"}), 403)


# ═══════════════════════════════════════════════════════════
# GET /api/arduino/get_command
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/get_command', methods=['GET'])
def get_command():
    """
    Récupère la prochaine commande à exécuter.
    Si aucune commande en attente, retourne {"action": "none"}.
    Supporte la reconnexion : retourne TOUTES les actions en attente.

    Headers: Authorization: Bearer <token>
    Query:   game_id=<int>
    """
    game_id, err_resp, status = _validate_token()
    if err_resp:
        return err_resp, status

    pending = arduino_state.get_pending_actions(game_id)

    if not pending:
        return jsonify({
            "action": "none",
            "game_id": game_id,
            "pending_count": 0
        }), 200

    # Retourner la première action non exécutée
    next_action = pending[0]
    logger.info(f"[get_command] game_id={game_id} → {next_action['action']} (id={next_action['id']})")

    return jsonify({
        "action": next_action["action"],
        "command_id": next_action["id"],
        "game_id": game_id,
        "timestamp": next_action["timestamp"],
        "pending_count": len(pending)
    }), 200


# ═══════════════════════════════════════════════════════════
# POST /api/arduino/confirm_command
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/confirm_command', methods=['POST'])
def confirm_command():
    """
    Confirme l'exécution d'une commande par son ID.
    Idempotent : confirmer deux fois la même commande est sans effet.

    Headers: Authorization: Bearer <token>
    Body:    {"game_id": <int>, "command_id": "<str>"}
    """
    game_id, err_resp, status = _validate_token()
    if err_resp:
        return err_resp, status

    data = request.get_json(silent=True) or {}
    command_id = data.get('command_id')

    if not command_id:
        return jsonify({"error": "Missing command_id"}), 400

    # Vérifier que cette commande existe réellement dans la queue
    all_actions = arduino_state.action_queues.get(game_id, [])
    known_ids = {a["id"] for a in all_actions}
    if command_id not in known_ids:
        return jsonify({"error": "Unknown command_id"}), 404

    arduino_state.mark_executed(game_id, command_id)
    logger.info(f"[confirm_command] game_id={game_id} commande confirmée: {command_id}")

    # Retourner le nombre d'actions encore en attente
    pending = arduino_state.get_pending_actions(game_id)
    return jsonify({
        "status": "ok",
        "command_id": command_id,
        "remaining_pending": len(pending)
    }), 200


# ═══════════════════════════════════════════════════════════
# POST /api/arduino/update_score
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/update_score', methods=['POST'])
def update_score():
    """
    Signale un but détecté par le capteur Arduino.
    Anti-spam intégré : 2 secondes minimum entre deux buts.
    Met à jour current_game et émet score_updated via WebSocket.

    Headers: Authorization: Bearer <token>
    Body:    {"game_id": <int>, "event": "goal", "team": "team1"|"team2"}
    """
    game_id, err_resp, status = _validate_token()
    if err_resp:
        return err_resp, status

    data = request.get_json(silent=True) or {}
    event = data.get('event')
    team = data.get('team')

    if event != 'goal':
        return jsonify({"error": f"Unknown event: {event}. Only 'goal' is supported."}), 400

    if team not in ('team1', 'team2'):
        return jsonify({"error": "Invalid team (must be 'team1' or 'team2')"}), 400

    # Anti-spam : 2 secondes minimum entre deux buts d'une même partie
    now = time.time()
    last = _last_goal_time.get(game_id, 0)
    if now - last < _GOAL_COOLDOWN:
        remaining = round(_GOAL_COOLDOWN - (now - last), 1)
        return jsonify({"error": f"Trop rapide, attendre {remaining}s", "retry_after": remaining}), 429
    _last_goal_time[game_id] = now

    # ── Déléguer au _process_goal de app.py (met à jour current_game + WebSocket) ──
    try:
        import app as main_app

        # Vérifier que la partie globale est active
        if not main_app.current_game.get('active'):
            return jsonify({
                "error": "Aucune partie en cours",
                "game_active": False
            }), 200

        # Verrou thread-safe (partagé avec le handler Socket.IO)
        acquired = main_app._goal_lock.acquire(blocking=False)
        if not acquired:
            return jsonify({"error": "Traitement but en cours, réessayez"}), 429
        try:
            result = main_app._process_goal(team)
        finally:
            main_app._goal_lock.release()

        # Mise à jour de l'état Arduino interne (score miroir)
        arduino_state.update_score(game_id, team)
        # Ajouter unlock_servo pour permettre la remise en jeu
        arduino_state.add_action(game_id, "unlock_servo")
        arduino_state.set_ball_state(game_id, False)

        # Extraire la réponse Flask et la convertir
        result_data = result.get_json() if hasattr(result, 'get_json') else {}
        game_state = arduino_state.get_game_state(game_id) or {}

        logger.info(f"[update_score] game_id={game_id} but {team} accepté")

        return jsonify({
            "status": "ok",
            "team": team,
            "game_ended": result_data.get("game_ended", False),
            "winner": result_data.get("winner"),
            "scores": {
                "team1": main_app.current_game.get("team1_score", 0),
                "team2": main_app.current_game.get("team2_score", 0)
            },
            "arduino_scores": {
                "team1": game_state.get("score_team1", 0),
                "team2": game_state.get("score_team2", 0)
            }
        }), 200

    except Exception as e:
        logger.error(f"[update_score] Erreur traitement but: {e}")
        return jsonify({"error": "Erreur interne lors du traitement du but"}), 500


# ═══════════════════════════════════════════════════════════
# GET /api/arduino/game_state
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/game_state', methods=['GET'])
def get_game_state():
    """
    Récupère l'état complet de la partie pour la reprise après coupure.
    Inclut le score live, l'état des servos, et toutes les actions en attente.

    Headers: Authorization: Bearer <token>
    Query:   game_id=<int>
    """
    game_id, err_resp, status = _validate_token()
    if err_resp:
        return err_resp, status

    arduino_gs = arduino_state.get_game_state(game_id)
    if not arduino_gs:
        return jsonify({"error": "Game not found in Arduino state"}), 404

    pending = arduino_state.get_pending_actions(game_id)

    # Récupérer aussi le score live depuis current_game (source de vérité)
    try:
        import app as main_app
        live_t1 = main_app.current_game.get("team1_score", 0)
        live_t2 = main_app.current_game.get("team2_score", 0)
        game_active = main_app.current_game.get("active", False)
        team1_players = main_app.current_game.get("team1_players", [])
        team2_players = main_app.current_game.get("team2_players", [])
    except Exception:
        live_t1 = arduino_gs.get("score_team1", 0)
        live_t2 = arduino_gs.get("score_team2", 0)
        game_active = arduino_gs.get("active", False)
        team1_players = []
        team2_players = []

    logger.info(f"[game_state] game_id={game_id} récupéré par simulateur")

    return jsonify({
        "game_id": game_id,
        "active": game_active,
        "score_team1": live_t1,
        "score_team2": live_t2,
        "ball_locked": arduino_gs.get("ball_locked", True),
        "team1_players": team1_players,
        "team2_players": team2_players,
        "pending_actions": [
            {
                "action": a["action"],
                "command_id": a["id"],
                "timestamp": a["timestamp"]
            }
            for a in pending
        ],
        "pending_count": len(pending)
    }), 200


# ═══════════════════════════════════════════════════════════
# POST /api/arduino/heartbeat
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    Maintient la connexion active et supporte la détection de reconnexion.
    Retourne les actions en attente pour faciliter la reprise après coupure.

    Headers: Authorization: Bearer <token>
    Body:    {"game_id": <int>}
    """
    game_id, err_resp, status = _validate_token()
    if err_resp:
        return err_resp, status

    # validate_token met déjà à jour last_seen — on y ajoute les infos utiles
    pending = arduino_state.get_pending_actions(game_id)
    arduino_gs = arduino_state.get_game_state(game_id) or {}

    logger.debug(f"[heartbeat] game_id={game_id}, pending={len(pending)}")

    return jsonify({
        "status": "alive",
        "game_id": game_id,
        "game_active": arduino_gs.get("active", False),
        "pending_count": len(pending),
        "server_time": time.time()
    }), 200


# ═══════════════════════════════════════════════════════════
# GET /api/arduino/debug/stats  (admin uniquement)
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/debug/stats', methods=['GET'])
def debug_stats():
    """
    Statistiques globales du système Arduino/simulateur.
    Réservé aux admins authentifiés via session Flask.
    """
    ok, err = _require_admin()
    if not ok:
        return err

    stats = arduino_state.get_stats()
    return jsonify(stats), 200


# ═══════════════════════════════════════════════════════════
# GET /api/arduino/debug/queues  (admin uniquement)
# ═══════════════════════════════════════════════════════════

@arduino_bp.route('/debug/queues', methods=['GET'])
def debug_queues():
    """
    Inspection complète de toutes les queues et actions exécutées.
    Réservé aux admins authentifiés via session Flask.
    """
    ok, err = _require_admin()
    if not ok:
        return err

    queues = arduino_state.get_all_queues()
    stats = arduino_state.get_stats()

    return jsonify({
        "stats": stats,
        "queues": queues
    }), 200
