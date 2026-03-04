# 🎮 SYSTÈME ARDUINO/SIMULATEUR - DOCUMENTATION COMPLÈTE

## 📋 Vue d'ensemble

Ce système permet à un Arduino WiFi (ou simulateur Python) de communiquer avec le site Baby-Foot Club pour :
- Recevoir des commandes (bloquer/débloquer les servos)
- Envoyer des buts détectés par le capteur
- Maintenir la synchronisation en cas de coupure réseau

---

## 🏗️ Architecture

```
┌─────────────────┐          ┌──────────────────┐
│                 │  HTTPS   │                  │
│  Arduino WiFi   │ ◄──────► │   Site Web       │
│  ou Simulateur  │  JSON    │   (Render)       │
│                 │          │                  │
└─────────────────┘          └──────────────────┘
        │                             │
        │                             │
    Servos +                      Base de
    Capteur                        données
```

---

## 📦 Fichiers créés

### 1. `arduino_manager.py`
**Rôle** : Gestion centralisée de l'état Arduino
- Tokens d'authentification
- Queue d'actions
- État des parties
- Synchronisation

### 2. `arduino_routes.py`
**Rôle** : Endpoints API pour la communication
- `/api/arduino/get_command` - Récupère la prochaine action
- `/api/arduino/confirm_command` - Confirme l'exécution
- `/api/arduino/update_score` - Envoie un but
- `/api/arduino/game_state` - Récupère l'état complet
- `/api/arduino/heartbeat` - Maintient la connexion

### 3. `arduino_simulator.py`
**Rôle** : Simulateur Python pour tester sans Arduino physique
- Simule les servos
- Simule le capteur de balle
- Gère la reconnexion automatique
- Mode test avec buts aléatoires

### 4. `arduino_integration.py`
**Rôle** : Code à intégrer dans `app.py`
- Handlers WebSocket
- Intégration avec le jeu existant
- Page de test (dev)

---

## 🔐 Sécurité

### Système de tokens

Chaque partie génère un **token unique** :
```
Authorization: Bearer <token_32_caracteres>
```

- ✅ Généré au démarrage de la partie
- ✅ Révoqué à la fin de la partie
- ✅ Expire après 1 heure
- ✅ Impossible à réutiliser

### Protection

- Tous les endpoints Arduino nécessitent un token valide
- Les anciens tokens ne peuvent jamais être réutilisés
- Timeout automatique si pas de heartbeat pendant 60s

---

## 📡 API Endpoints

### GET `/api/arduino/get_command`

**Récupère la prochaine commande à exécuter**

**Headers:**
```
Authorization: Bearer <token>
```

**Query params:**
```
game_id=5
```

**Response (200):**
```json
{
  "action": "unlock_ball",
  "game_id": 5,
  "command_id": "cmd_abc123",
  "timestamp": 1234567890.123
}
```

**Response (si aucune action):**
```json
{
  "action": "none",
  "game_id": 5
}
```

---

### POST `/api/arduino/confirm_command`

**Confirme l'exécution d'une commande**

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "game_id": 5,
  "command_id": "cmd_abc123"
}
```

**Response (200):**
```json
{
  "status": "ok"
}
```

---

### POST `/api/arduino/update_score`

**Envoie un but détecté par le capteur**

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "game_id": 5,
  "event": "goal",
  "team": "team1"
}
```

**Response (200):**
```json
{
  "status": "ok",
  "new_score": {
    "team1": 3,
    "team2": 2
  }
}
```

---

### GET `/api/arduino/game_state`

**Récupère l'état complet après reconnexion**

**Headers:**
```
Authorization: Bearer <token>
```

**Query params:**
```
game_id=5
```

**Response (200):**
```json
{
  "game_id": 5,
  "active": true,
  "score_team1": 3,
  "score_team2": 2,
  "ball_locked": false,
  "pending_actions": [
    {
      "action": "unlock_ball",
      "command_id": "cmd_xyz789",
      "timestamp": 1234567890.123
    }
  ]
}
```

---

### POST `/api/arduino/heartbeat`

**Maintient la connexion vivante**

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "game_id": 5
}
```

**Response (200):**
```json
{
  "status": "alive"
}
```

---

## 🖥️ Utilisation du simulateur

### Installation

```bash
pip install requests
```

### Lancement

```bash
python arduino_simulator.py \
    --url https://ton-site.onrender.com \
    --game-id 1 \
    --token TON_TOKEN_ICI
```

### Options

- `--url` : URL du site (requis)
- `--game-id` : ID de la partie (requis)
- `--token` : Token d'authentification (requis)
- `--simulate-goals` : Simuler des buts aléatoires (optionnel)

### Exemple avec simulation de buts

```bash
python arduino_simulator.py \
    --url https://babyfoot-club.onrender.com \
    --game-id 1 \
    --token abc123xyz789... \
    --simulate-goals
```

---

## 🔄 Flux de communication

### 1. Démarrage d'une partie

```
Site Web                    Arduino
   │                           │
   │  Generate Token           │
   │─────────────────────────► │
   │                           │
   │  "unlock_ball"            │
   │─────────────────────────► │
   │                           │
   │       Execute             │
   │                           │
   │  Confirm                  │
   │ ◄───────────────────────  │
```

### 2. But marqué

```
Arduino                    Site Web
   │                           │
   │  Capteur détecte balle    │
   │                           │
   │  POST /update_score       │
   │─────────────────────────► │
   │  team="team1"             │
   │                           │
   │  Score mis à jour         │
   │ ◄───────────────────────  │
   │  {team1: 3, team2: 2}     │
   │                           │
   │  GET /get_command         │
   │─────────────────────────► │
   │                           │
   │  "unlock_ball"            │
   │ ◄───────────────────────  │
```

### 3. Reconnexion après coupure

```
Arduino                    Site Web
   │                           │
   │  Coupure réseau...        │
   │                           │
   │  Reconnexion              │
   │                           │
   │  GET /game_state          │
   │─────────────────────────► │
   │                           │
   │  État complet + actions   │
   │ ◄───────────────────────  │
   │  pending: ["unlock_ball"] │
   │                           │
   │  Execute actions          │
   │  Confirm chaque action    │
   │─────────────────────────► │
```

---

## 🛠️ Intégration dans app.py

### Étape 1 : Ajouter les imports

```python
# Ajouter en haut de app.py
from arduino_routes import arduino_bp
from arduino_manager import arduino_state, start_game_arduino, end_game_arduino, goal_scored
```

### Étape 2 : Enregistrer le Blueprint

```python
# Après la création de l'app Flask
app.register_blueprint(arduino_bp)
logger.info("Routes Arduino enregistrées")
```

### Étape 3 : Modifier start_game

```python
# Dans @socketio.on('start_game')
# Après save_game_to_db:

game_id = result_id
arduino_token = start_game_arduino(game_id)

socketio.emit('arduino_token_generated', {
    "game_id": game_id,
    "token": arduino_token
}, namespace='/', room=room)
```

### Étape 4 : Modifier game_ended

```python
# Dans @socketio.on('game_ended')
# À la fin:

if 'id' in current_game:
    end_game_arduino(current_game['id'])
```

**Voir `arduino_integration.py` pour le code complet**

---

## 🧪 Tests

### Test 1 : Connexion basique

```bash
curl -X GET \
  "https://ton-site.onrender.com/api/arduino/get_command?game_id=1" \
  -H "Authorization: Bearer TON_TOKEN"
```

### Test 2 : Envoyer un but

```bash
curl -X POST \
  "https://ton-site.onrender.com/api/arduino/update_score" \
  -H "Authorization: Bearer TON_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"game_id":1,"event":"goal","team":"team1"}'
```

### Test 3 : Récupérer l'état

```bash
curl -X GET \
  "https://ton-site.onrender.com/api/arduino/game_state?game_id=1" \
  -H "Authorization: Bearer TON_TOKEN"
```

---

## 🐛 Debug

### Endpoint de debug (admin)

```
GET /api/arduino/debug/stats
GET /api/arduino/debug/queues
```

### Page de test (dev uniquement)

```
http://127.0.0.1:5000/test/arduino
```

### Logs

Le simulateur affiche des logs détaillés :
```
2024-03-04 15:30:45 - INFO - 🔧 Exécution: unlock_ball (id=cmd_abc123)
2024-03-04 15:30:45 - INFO -   → Servos déverrouillés
2024-03-04 15:30:45 - INFO -   ✅ Commande confirmée
2024-03-04 15:30:50 - INFO - 🎯 Capteur simulé: But détecté pour team1
2024-03-04 15:30:50 - INFO - ⚽ But envoyé pour team1: {'team1': 1, 'team2': 0}
```

---

## ⚠️ Gestion des erreurs

### Token invalide (401)

```json
{
  "error": "Invalid or expired token"
}
```

**Solution** : Demander un nouveau token au serveur

### Timeout

Le simulateur gère automatiquement les timeouts et réessaye

### Perte de connexion

Le simulateur se reconnecte automatiquement et récupère l'état complet

---

## 📊 Statistiques

Le simulateur affiche des stats périodiques :

```
==================================================
📊 STATISTIQUES
  Commandes reçues: 15
  Commandes exécutées: 15
  Buts envoyés: 3
  Erreurs: 0
  État servos: 🔓 Déverrouillés
==================================================
```

---

## 🚀 Déploiement

### Sur Render

1. Upload les fichiers sur GitHub :
   - `arduino_manager.py`
   - `arduino_routes.py`
   - `arduino_integration.py` (code à intégrer dans app.py)

2. Ajouter `requests` dans `requirements.txt`

3. Modifier `app.py` selon les instructions

4. Redéployer sur Render

### Sur Arduino physique

Le simulateur peut servir de base pour le code Arduino WiFi :

```cpp
// Exemple Arduino WiFi
#include <ESP8266HTTPClient.h>

String token = "TON_TOKEN";
int gameId = 1;
String baseUrl = "https://ton-site.onrender.com";

void getCommand() {
  HTTPClient http;
  http.begin(baseUrl + "/api/arduino/get_command?game_id=" + gameId);
  http.addHeader("Authorization", "Bearer " + token);
  
  int httpCode = http.GET();
  if (httpCode == 200) {
    String payload = http.getString();
    // Parser JSON et exécuter action
  }
  http.end();
}
```

---

## 🎯 Checklist de déploiement

- [ ] Fichiers uploadés sur GitHub
- [ ] `requirements.txt` mis à jour
- [ ] Code intégré dans `app.py`
- [ ] Testé en local avec le simulateur
- [ ] Déployé sur Render
- [ ] Token généré pour une partie de test
- [ ] Simulateur testé avec le site en production
- [ ] Logs vérifiés

---

## 🆘 Support

En cas de problème :

1. Vérifier les logs du simulateur
2. Vérifier les logs Render
3. Tester les endpoints avec curl
4. Utiliser la page `/test/arduino` (dev)
5. Vérifier que le token est valide

---

**Documentation créée le 2024-03-04**  
**Version 1.0 - Baby-Foot Club Arduino System**
