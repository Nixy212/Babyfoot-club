"""
INTÉGRATION ARDUINO - À AJOUTER DANS app.py

Ce code doit être ajouté dans app.py pour activer la communication Arduino
"""

# ═══════════════════════════════════════════════════════════
# AJOUT 1: Imports (à ajouter en haut du fichier après les imports existants)
# ═══════════════════════════════════════════════════════════

# Import du système Arduino
from arduino_routes import arduino_bp
from arduino_manager import arduino_state, start_game_arduino, end_game_arduino, goal_scored

# ═══════════════════════════════════════════════════════════
# AJOUT 2: Enregistrer le Blueprint Arduino (après la création de l'app Flask)
# ═══════════════════════════════════════════════════════════

# Enregistrer les routes Arduino
app.register_blueprint(arduino_bp)
logger.info("Routes Arduino enregistrées: /api/arduino/*")

# ═══════════════════════════════════════════════════════════
# AJOUT 3: Modifier le handler start_game pour générer le token Arduino
# ═══════════════════════════════════════════════════════════

# Dans la fonction @socketio.on('start_game'), AJOUTER après save_game_to_db:

# Générer le token Arduino et initialiser la partie
game_id = result_id  # ID retourné par save_game_to_db
arduino_token = start_game_arduino(game_id)

logger.info(f"Token Arduino généré pour game_id={game_id}: {arduino_token[:10]}...")

# Émettre le token aux clients (visible uniquement par les admins si nécessaire)
socketio.emit('arduino_token_generated', {
    "game_id": game_id,
    "token": arduino_token,
    "token_preview": arduino_token[:10] + "..."
}, namespace='/', room=room)

# ═══════════════════════════════════════════════════════════
# AJOUT 4: Modifier le handler game_ended pour terminer la partie Arduino
# ═══════════════════════════════════════════════════════════

# Dans @socketio.on('game_ended'), AJOUTER à la fin:

# Terminer la partie côté Arduino
try:
    # Récupérer le game_id depuis la session ou la DB
    if hasattr(current_game, 'get') and 'id' in current_game:
        game_id = current_game['id']
        end_game_arduino(game_id)
        logger.info(f"Partie Arduino terminée: game_id={game_id}")
except Exception as e:
    logger.error(f"Erreur fin de partie Arduino: {e}")

# ═══════════════════════════════════════════════════════════
# AJOUT 5: Handler pour les buts marqués par l'Arduino (nouveau handler)
# ═══════════════════════════════════════════════════════════

@socketio.on('arduino_goal')
def handle_arduino_goal(data):
    """
    Handler appelé quand l'Arduino détecte un but
    Ce handler est appelé par le système Arduino via WebSocket ou peut être
    déclenché manuellement pour synchroniser avec les buts détectés
    """
    try:
        game_id = data.get('game_id')
        team = data.get('team')  # 'team1' ou 'team2'
        
        if not game_id or not team:
            logger.error("Données manquantes pour arduino_goal")
            return
        
        logger.info(f"But Arduino reçu: game_id={game_id}, team={team}")
        
        # Mettre à jour le score côté Arduino
        goal_scored(game_id, team)
        
        # Synchroniser avec l'état du jeu actuel
        if team == 'team1':
            current_game['team1_score'] += 1
        else:
            current_game['team2_score'] += 1
        
        # Émettre aux clients
        room = f"game_{game_id}"
        socketio.emit('score_updated', {
            "team1_score": current_game['team1_score'],
            "team2_score": current_game['team2_score']
        }, namespace='/', room=room)
        
        logger.info(f"Score mis à jour: {current_game['team1_score']}-{current_game['team2_score']}")
        
    except Exception as e:
        logger.error(f"Erreur arduino_goal: {e}")

# ═══════════════════════════════════════════════════════════
# AJOUT 6: Nettoyage périodique des parties anciennes (optionnel)
# ═══════════════════════════════════════════════════════════

import threading

def cleanup_old_arduino_games():
    """Nettoie les parties Arduino terminées depuis plus d'1h"""
    while True:
        try:
            arduino_state.cleanup_old_games(max_age_seconds=3600)
            time.sleep(600)  # Toutes les 10 minutes
        except Exception as e:
            logger.error(f"Erreur cleanup Arduino: {e}")
            time.sleep(60)

# Démarrer le thread de nettoyage
cleanup_thread = threading.Thread(target=cleanup_old_arduino_games, daemon=True)
cleanup_thread.start()
logger.info("Thread de nettoyage Arduino démarré")

# ═══════════════════════════════════════════════════════════
# AJOUT 7: Endpoint admin pour récupérer le token d'une partie
# ═══════════════════════════════════════════════════════════

@app.route('/admin/arduino/token/<int:game_id>')
def get_arduino_token_admin(game_id):
    """
    Récupère le token Arduino d'une partie (pour admin)
    Protégé par authentification admin
    """
    # TODO: Ajouter vérification admin
    if 'username' not in session:
        return jsonify({"error": "Non autorisé"}), 401
    
    # Vérifier si le token existe
    token_data = arduino_state.active_tokens.get(game_id)
    
    if not token_data:
        return jsonify({"error": "Aucun token actif pour cette partie"}), 404
    
    return jsonify({
        "game_id": game_id,
        "token": token_data["token"],
        "created_at": token_data["created_at"],
        "expires_at": token_data["expires_at"]
    }), 200

# ═══════════════════════════════════════════════════════════
# AJOUT 8: Page de test du simulateur (optionnel - dev uniquement)
# ═══════════════════════════════════════════════════════════

@app.route('/test/arduino')
def test_arduino_page():
    """Page de test du simulateur Arduino (dev uniquement)"""
    if not app.debug:
        return "Page disponible uniquement en mode debug", 403
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Arduino Simulator</title>
        <style>
            body { font-family: monospace; padding: 2rem; background: #1a1a1a; color: #fff; }
            .container { max-width: 800px; margin: 0 auto; }
            button { padding: 1rem; margin: 0.5rem; background: #8b6f47; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
            button:hover { background: #a68a5c; }
            .output { background: #2d2d2d; padding: 1rem; border-radius: 8px; margin-top: 1rem; max-height: 400px; overflow-y: auto; }
            .log { margin: 0.5rem 0; }
            .success { color: #4caf50; }
            .error { color: #f44336; }
            input { padding: 0.5rem; margin: 0.5rem; background: #2d2d2d; color: #fff; border: 1px solid #8b6f47; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎮 Test Simulateur Arduino</h1>
            
            <div>
                <h3>Configuration</h3>
                <input type="number" id="gameId" placeholder="Game ID" value="1">
                <input type="text" id="token" placeholder="Token Arduino" style="width: 300px;">
                <button onclick="getToken()">Générer Token</button>
            </div>
            
            <div>
                <h3>Actions</h3>
                <button onclick="getCommand()">Get Command</button>
                <button onclick="sendGoal('team1')">But Team 1</button>
                <button onclick="sendGoal('team2')">But Team 2</button>
                <button onclick="getGameState()">Get State</button>
                <button onclick="sendHeartbeat()">Heartbeat</button>
            </div>
            
            <div>
                <h3>Commande Simulateur</h3>
                <pre style="background: #2d2d2d; padding: 1rem; border-radius: 8px;">
python arduino_simulator.py \\
    --url """ + request.host_url.rstrip('/') + """ \\
    --game-id <GAME_ID> \\
    --token <TOKEN> \\
    --simulate-goals
                </pre>
            </div>
            
            <div class="output" id="output">
                <div class="log">Logs apparaîtront ici...</div>
            </div>
        </div>
        
        <script>
            function log(message, type = 'info') {
                const output = document.getElementById('output');
                const div = document.createElement('div');
                div.className = 'log ' + type;
                div.textContent = new Date().toLocaleTimeString() + ' - ' + message;
                output.appendChild(div);
                output.scrollTop = output.scrollHeight;
            }
            
            async function makeRequest(method, endpoint, body = null) {
                const gameId = document.getElementById('gameId').value;
                const token = document.getElementById('token').value;
                
                const url = endpoint + (method === 'GET' ? '?game_id=' + gameId : '');
                
                try {
                    const response = await fetch(url, {
                        method: method,
                        headers: {
                            'Authorization': 'Bearer ' + token,
                            'Content-Type': 'application/json'
                        },
                        body: body ? JSON.stringify({...body, game_id: parseInt(gameId)}) : null
                    });
                    
                    const data = await response.json();
                    log(method + ' ' + endpoint + ' → ' + JSON.stringify(data), response.ok ? 'success' : 'error');
                    return data;
                } catch (e) {
                    log('Erreur: ' + e.message, 'error');
                }
            }
            
            async function getToken() {
                const gameId = document.getElementById('gameId').value;
                try {
                    const response = await fetch('/admin/arduino/token/' + gameId);
                    const data = await response.json();
                    document.getElementById('token').value = data.token;
                    log('Token récupéré: ' + data.token.substring(0, 20) + '...', 'success');
                } catch (e) {
                    log('Erreur récupération token: ' + e.message, 'error');
                }
            }
            
            function getCommand() {
                makeRequest('GET', '/api/arduino/get_command');
            }
            
            function sendGoal(team) {
                makeRequest('POST', '/api/arduino/update_score', {event: 'goal', team: team});
            }
            
            function getGameState() {
                makeRequest('GET', '/api/arduino/game_state');
            }
            
            function sendHeartbeat() {
                makeRequest('POST', '/api/arduino/heartbeat');
            }
        </script>
    </body>
    </html>
    """
