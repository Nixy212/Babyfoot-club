# 📖 BABY-FOOT CLUB — Guide complet pour l'IA qui reprend ce projet

> **Lis ce fichier entièrement avant de toucher quoi que ce soit.**
> Il contient tout ce que les précédentes sessions ont appris à la dure.

---

## 1. C'est quoi ce projet ?

Application web de gestion d'un **babyfoot physique dans un club** (bureau, école, etc.).
Les joueurs se connectent, réservent un créneau, créent un lobby, jouent, et les scores sont
enregistrés avec un système ELO. Un Arduino ESP32 peut détecter les buts automatiquement.

**Stack :**
- Backend : Python 3.11.9 / Flask 3.0.0 + Flask-SocketIO 5.3.6
- DB : PostgreSQL en prod (Render), SQLite en local — dual-mode automatique
- Frontend : HTML/Jinja2 + CSS vanilla + JS vanilla — pas de framework frontend
- Deploy : Render (render.yaml)
- Hardware optionnel : Arduino ESP32 (buts physiques via HTTP ou WebSocket)

---

## 2. Structure des fichiers

```
app.py                ← TOUT LE SERVEUR (~3900 lignes). Routes HTTP + WebSocket + DB.
                        NE PAS DIVISER — les variables globales sont partagées.

gunicorn_config.py    ← 1 worker, 4 threads, timeout 120s. NE PAS TOUCHER.
render.yaml           ← Config Render (build + start command). OK tel quel.
runtime.txt           ← "python-3.11.9". Obligatoire pour Render.
requirements.txt      ← Dépendances Python.
.env.example          ← Variables d'env à configurer dans Render (pas commiter).

static/
  design-v3.css           ← TOUT le CSS (thème sombre, bronze/or). Un seul fichier.
  sw.js                   ← Service Worker PWA. VERSION CACHE = babyfoot-v30.
  profile-utils.js        ← Chargement avatars/pseudos. Utilisé dans TOUS les templates.
  icons.js                ← Icônes SVG via data-bficon="nom". Ex: data-bficon="trophy"
  global-animations.js    ← Animations UI + logique de reconnexion WebSocket auto.
  animations.js           ← Animations visuelles (particules, etc.) — optionnel.
  confetti.js             ← Confettis fin de partie — optionnel.
  socket.io.min.js        ← Client Socket.IO local (fallback si CDN down).
  pwa.js                  ← Installation PWA mobile.
  manifest.json           ← Manifest PWA.
  main.js                 ← Divers helpers JS globaux.
  images/                 ← logo.svg, fond.png, background-pattern.svg, icon_compte.png

templates/
  base.html           ← Layout partagé (nav, menu mobile, pwa.js, CSS). Tous les autres
                        templates font {% extends "base.html" %}.
  index.html          ← Page d'accueil publique (non connecté).
  login.html          ← Formulaire login.
  register.html       ← Formulaire inscription.
  dashboard.html      ← Hub principal après connexion (résumé stats, accès rapide).
  lobby.html          ← Salle d'attente avant partie (Socket.IO temps réel).
  live-score.html     ← Score en direct pendant la partie (Socket.IO).
  reservation.html    ← Réservation de créneaux (aujourd'hui + demain seulement).
  stats.html          ← Stats d'un joueur + graphe ELO historique.
  top.html            ← Classement ELO de tous les joueurs.
  scores.html         ← Historique des parties.
  settings.html       ← Profil, avatar, changement de mot de passe, cosmétiques, quêtes.
  admin.html          ← Panel admin : gestion users, badges, reset DB.
```

---

## 3. Déploiement et environnement

**Plateforme : Render** (render.com)
- Build : `pip install -r requirements.txt`
- Start : `gunicorn --config gunicorn_config.py app:app`
- Render injecte automatiquement `RENDER=true`

**Variables d'environnement à configurer dans Render → Environment :**

| Variable | Obligatoire | Description |
|---|---|---|
| `SECRET_KEY` | ✅ OUI | Clé Flask fixe (32+ chars random). Sessions cassées si absente. |
| `DATABASE_URL` | ✅ OUI | URL PostgreSQL Render. Format : `postgresql://user:pass@host:port/db` |
| `CORS_ORIGINS` | ✅ OUI | Domaine exact Render. Ex : `https://monapp.onrender.com` |
| `RENDER` | Auto | Injecté par Render. Active `SESSION_COOKIE_SECURE`. |
| `CLOUDINARY_URL` | ❌ optionnel | Pour avatars cloud. Format : `cloudinary://key:secret@cloud` |
| `ARDUINO_SECRET` | ❌ optionnel | Secret partagé avec l'ESP32 pour sécuriser les endpoints Arduino. |
| `SEED_PW_IMRAN` | ❌ optionnel | Mot de passe initial du compte Imran (super admin). |
| `SEED_PW_APOUTOU` | ❌ optionnel | Mot de passe initial du compte Apoutou (admin). |
| `SEED_PW_HAMARA` | ❌ optionnel | Mot de passe initial du compte Hamara (admin). |
| `SEED_PW_MDA` | ❌ optionnel | Mot de passe initial du compte MDA (admin). |

**⚠️ Si `DATABASE_URL` est absent → SQLite local → données perdues au restart Render.**

---

## 4. Base de données

### Dual-mode automatique
```python
USE_POSTGRES = bool(DATABASE_URL)  # True en prod, False en local
```

**Toutes les requêtes SQL doivent avoir les deux variantes :**
```python
q = "SELECT * FROM users WHERE username = %s" if USE_POSTGRES else "SELECT * FROM users WHERE username = ?"
cur.execute(q, (username,))
```
Ne jamais écrire une requête avec un seul format de placeholder. C'est la règle n°1.

### Schéma complet

```sql
-- Joueurs
users (
  username VARCHAR(50) PRIMARY KEY,
  password VARCHAR(200),          -- bcrypt hash
  total_goals INTEGER DEFAULT 0,
  total_games INTEGER DEFAULT 0,
  total_wins INTEGER DEFAULT 0,
  winstreak INTEGER DEFAULT 0,    -- série de victoires consécutives
  elo INTEGER DEFAULT 1000,
  role INTEGER DEFAULT 0,         -- 0=Joueur, 1=SuperAdmin, 2=Admin
  nickname VARCHAR(50),           -- surnom affiché
  bio VARCHAR(200),
  avatar_preset VARCHAR(10),      -- code preset avatar ('preset_1', etc.)
  avatar_url TEXT,                -- URL Cloudinary ou data:image/... base64
  unlocked_cosmetics TEXT,        -- JSON array : ["theme_fire", "frame_bronze", ...]
  active_theme TEXT DEFAULT 'default',
  active_frame TEXT DEFAULT 'none',
  created_at TIMESTAMP
)

-- Réservations
reservations (
  id SERIAL PRIMARY KEY,
  day VARCHAR(20),                -- 'Lundi', 'Mardi', etc. (compatibilité legacy)
  time VARCHAR(30),               -- '14:00 - 14:15' (compatibilité legacy)
  team1 TEXT DEFAULT '[]',        -- JSON array de usernames
  team2 TEXT DEFAULT '[]',        -- JSON array de usernames
  mode VARCHAR(10) DEFAULT '1v1', -- '1v1' ou '2v2'
  reserved_by VARCHAR(50),        -- username du créateur
  start_time TIMESTAMP,           -- champ principal pour la logique
  end_time TIMESTAMP,             -- champ principal pour la logique
  duration_minutes INTEGER DEFAULT 15,
  created_at TIMESTAMP,
  UNIQUE (start_time, reserved_by)
)

-- Parties jouées
games (
  id SERIAL PRIMARY KEY,
  team1_players TEXT,             -- JSON array de usernames
  team2_players TEXT,             -- JSON array de usernames
  team1_score INTEGER,
  team2_score INTEGER,
  winner VARCHAR(10),             -- 'team1' ou 'team2'
  mode VARCHAR(10) DEFAULT '1v1',
  started_by VARCHAR(50),
  date TIMESTAMP
)

-- Scores individuels (buts marqués par partie)
scores (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
  score INTEGER,
  date TIMESTAMP
)

-- Catalogue des quêtes
quests (
  id SERIAL PRIMARY KEY,
  key VARCHAR(50) UNIQUE,         -- identifiant unique ex: 'first_win'
  name VARCHAR(100),
  description TEXT,
  icon VARCHAR(10),
  condition_type VARCHAR(50),     -- 'total_wins', 'winstreak', 'elo', 'rank', etc.
  condition_value INTEGER,
  reward_cosmetic VARCHAR(100),   -- clé dans COSMETICS_CATALOG
  reward_label VARCHAR(100)
)

-- Progression des joueurs sur les quêtes
user_quests (
  username VARCHAR(50),
  quest_key VARCHAR(50),
  progress INTEGER DEFAULT 0,
  completed BOOLEAN DEFAULT FALSE,
  completed_at TIMESTAMP,
  PRIMARY KEY (username, quest_key)
)

-- Catalogue des badges (créés par Imran)
badges (
  id SERIAL PRIMARY KEY,
  name VARCHAR(80),
  description TEXT,
  icon VARCHAR(20) DEFAULT '🏅',
  color VARCHAR(20) DEFAULT '#cd7f32',
  image_url TEXT,                 -- URL Cloudinary ou data:image/... base64
  created_by VARCHAR(50),
  created_at TIMESTAMP
)

-- Attribution des badges aux joueurs
user_badges (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50),
  badge_id INTEGER REFERENCES badges(id) ON DELETE CASCADE,
  awarded_by VARCHAR(50),
  awarded_at TIMESTAMP,
  UNIQUE (username, badge_id)
)
```

### Migrations
Les migrations sont non-destructives et s'exécutent **automatiquement au démarrage** :
- `migrate_reservations_v2()` — ajout start_time/end_time/duration
- `migrate_elo_v2()` — ajout winstreak/total_wins
- `migrate_cosmetics_v1()` — ajout colonnes cosmétiques + tables quêtes
- `migrate_badges_v1()` — création tables badges
- `migrate_teams_to_text()` — correction types PostgreSQL legacy

**Ne jamais supprimer ces fonctions.** Elles protègent les bases existantes.

---

## 5. Système de rôles

| Rôle | Valeur | Compte | Droits |
|---|---|---|---|
| Joueur | `0` | Tout le monde | Jouer, réserver, voir stats |
| Admin | `2` | Apoutou, Hamara, MDA | + Gérer users, forcer parties, annuler réservations |
| Super Admin | `1` | Imran | + Reset DB, créer badges, débloquer cosmétiques |

```python
is_admin(username)       # role >= 1 (Admin ET Super Admin)
is_super_admin(username) # role == 1 uniquement
is_guest_player(username)# Joueur1, Joueur2, Joueur3 (comptes physiques partagés)
```

**Cache des rôles** : `_role_cache = {}` — évite requêtes DB répétées.
Invalider avec `invalidate_role_cache(username)` après un changement de rôle.

---

## 6. État global en mémoire (variables globales dans app.py)

Ces variables vivent en RAM. Elles se reset au redémarrage du serveur.

```python
current_game = {
    "team1_score": 0, "team2_score": 0,
    "team1_players": [], "team2_players": [],
    "active": False,
    "started_by": None,     # username qui a lancé
    "reserved_by": None,    # username avec réservation active
    "started_at": None,     # ISO datetime
    "winner": None          # 'team1' ou 'team2' (présent après fin)
}

active_lobby = {
    "host": None,           # username de l'hôte
    "invited": [],          # usernames invités (pas encore répondu)
    "accepted": [],         # usernames ayant accepté
    "declined": [],         # usernames ayant refusé
    "team1": [],            # joueurs dans équipe 1
    "team2": [],            # joueurs dans équipe 2
    "active": False,
    "join_requests": {}     # request_id -> {from: username}
}

connected_users = {}        # sid -> username (toutes les connexions WS actives)
pending_invitations = {}    # username -> {from, timestamp}
rematch_votes = {"team1": [], "team2": []}
rematch_no_votes = []
rematch_pending = False     # True entre game_ended et lancement du rematch
servo_commands = {"servo1": [], "servo2": []}  # queues de commandes ESP32
team_swap_requests = {}     # request_id -> {from, to}
_ARDUINO_SECRET = os.environ.get("ARDUINO_SECRET", "")  # lu une seule fois
```

**⚠️ Verrou thread** : `_lobby_lock` protège `active_lobby` contre les race conditions.
Toujours utiliser `with _lobby_lock:` pour modifier `active_lobby`.

---

## 7. Flux complets — comment ça marche

### Flux 1 : Connexion d'un joueur
```
1. GET /login           → login.html
2. POST /api/login      → vérifie bcrypt, set session['username']
3. GET /current_user    → retourne {username, nickname, avatar, is_admin, has_reservation}
   → Ce endpoint est appelé par base.html au chargement pour initialiser la nav
```

### Flux 2 : Réservation → Lobby → Partie
```
1. POST /api/reserve_and_lobby  → crée réservation + crée active_lobby avec host
   OU
   POST /api/reserve_now        → réservation seule
   POST /api/reserve_plan       → réservation planifiée (heure future)

2. WS emit 'create_lobby'       → si pas encore de lobby
3. WS emit 'invite_to_lobby'    → inviter d'autres joueurs
4. Joueurs invités reçoivent    ← 'lobby_invitation'
5. WS emit 'accept_lobby'       → rejoindre équipe automatiquement (équilibrage)
6. WS emit 'start_game_from_lobby' → lance la partie

7. Serveur émet               ← 'game_started' à tous les clients
8. Clients redirigent vers /live-score
```

### Flux 3 : Partie en cours
```
Score manuel (admin) :
  WS emit 'update_score' {team: 'team1'|'team2'}
  → current_game[team_score] += 1
  ← 'score_updated' broadcast à tous

Score Arduino (ESP32) :
  POST /api/arduino/goal {secret, team}  (HTTP)
  OU
  WS emit 'arduino_goal' {secret, team}  (WebSocket)
  → _process_goal(team)  — même logique que update_score
  ← 'score_updated'

À 9 buts : la balle adverse est bloquée (servo adverse = close)
  ← 'servo_adverse_lock'

À 10 buts : fin de partie
  → save_game_results(current_game) — ELO + quêtes calculés
  ← 'game_ended' broadcast
  ← 'rematch_prompt' broadcast
```

### Flux 4 : Fin de partie / Rematch
```
Joueurs votent :
  WS emit 'vote_rematch' {vote: 'yes'|'no'}
  ← 'rematch_vote_update' {yes, no, total}

Si vote non :
  ← 'host_replace_or_quit' → l'hôte peut proposer un remplaçant

Si tous oui → _launch_rematch()
  ← 'game_started' avec les mêmes équipes

Si l'hôte quitte :
  WS emit 'host_quit_rematch'
  ← 'rematch_cancelled'
```

### Flux 5 : Reconnexion en cours de partie
```
WS 'connect' :
  Si current_game.active → emit 'game_recovery' au client qui vient de se connecter
  Si current_game.winner et user était dans la partie → emit 'game_ended' + 'rematch_prompt'
```

---

## 8. Calcul ELO

Formule dans `compute_elo(winner_elo, loser_elo, winner_streak, score_w, score_l)` :

- **K dynamique** : 40 (elo<1050), 28 (1050-1250), 20 (1250-1400), 14 (1400+)
- **Bonus winstreak** : ×(1.0 + streak×0.15), maximum ×2.0
- **Bonus upset** : si le gagnant avait 200+ ELO de moins → ×1.5
- **Bonus domination** : score 10-0 ou 10-1 → ×1.2
- **Plancher** : ELO minimum = 800

En 2v2 : la moyenne ELO des deux équipes est utilisée, le delta est appliqué à chaque joueur
individuellement par rapport à la moyenne.

**7 paliers ELO :**
- Recrue 🎮 : 800–949
- Amateur 🌱 : 950–1099
- Rival 🔥 : 1100–1249
- Confirmé ⚡ : 1250–1399
- Expert 💎 : 1400–1549
- Élite 👑 : 1550–1699
- Maître 🏆 : 1700+

---

## 9. Système de quêtes et cosmétiques

### Quêtes (QUESTS_DEFINITIONS dans app.py)
Déclenchées automatiquement dans `check_and_unlock_quests()` appelée par `save_game_results()`.

| Clé | Condition | Récompense |
|---|---|---|
| `first_win` | 1 victoire | Cadre Bronze |
| `streak_3` | 3 victoires consécutives | Thème Fire |
| `streak_5` | 5 victoires consécutives | Cadre Flamme Animée |
| `perfect_game` | Gagner 10-0 | Badge Perfectionniste |
| `games_10` | 10 parties jouées | Thème Nuit |
| `goals_50` | 50 buts marqués | Thème Gold |
| `remontada` | Perdre 0-5 puis gagner | Cadre Phénix |
| `top1` | Être n°1 classement ELO | Thème Royal |
| `master_elo` | Atteindre 1700 ELO | Thème Maître |

### Cosmétiques (COSMETICS_CATALOG dans app.py)
- **Thèmes** : modifient l'apparence de live-score.html (`css_class` appliquée au body)
- **Cadres** : entourent l'avatar du joueur
- **Badges** : icônes profil (distincts des badges admin)

Colonnes utilisateurs : `unlocked_cosmetics` (JSON array), `active_theme`, `active_frame`

---

## 10. Arduino / ESP32

L'ESP32 communique avec le serveur de deux façons :

### HTTP (principal)
```
GET  /api/arduino/status     → état actuel (scores, servos attendus)
GET  /api/arduino/commands   → commandes servos en attente (pop de la queue)
POST /api/arduino/goal       → {secret, team: 'team1'|'team2'} → enregistre un but
POST /api/arduino/servo      → {secret, servo: 'servo1'|'servo2', action: 'open'|'close'}
```

### WebSocket (alternatif)
```
emit 'arduino_goal'  {secret, team}  → même logique que HTTP
emit 'arduino_ping'                  ← 'arduino_pong'
emit 'get_game_state'                ← 'game_state'
```

**Protection** : tous les endpoints Arduino vérifient `_ARDUINO_SECRET`.
Si non défini, les endpoints fonctionnent mais un warning est loggé.

**Anti double-but** : `_goal_lock` (threading.Lock) + délai minimum 1s entre deux buts
de la même IP (HTTP) ou 2s par sid (WebSocket).

**Servos** : `servo_commands` est une queue. L'ESP32 poll `/api/arduino/commands` régulièrement
et exécute les commandes dans l'ordre. À 9 buts : balle adverse bloquée. À 10 buts : tout fermé.

---

## 11. Référence complète des routes HTTP

### Pages (GET → HTML)
| Route | Auth requise | Template |
|---|---|---|
| `/` | Non | index.html |
| `/login` | Non | login.html |
| `/register` | Non | register.html |
| `/dashboard` | Oui | dashboard.html |
| `/reservation` | Oui | reservation.html |
| `/lobby` | Oui | lobby.html |
| `/live-score` | Oui | live-score.html |
| `/stats` | Oui | stats.html |
| `/stats/<username>` | Oui | stats.html |
| `/top` | Oui | top.html |
| `/scores` | Oui | scores.html |
| `/settings` | Oui | settings.html |
| `/admin` | Admin | admin.html |

### API Auth
| Route | Méthode | Payload | Retour |
|---|---|---|---|
| `/api/register` | POST | `{username, password}` | `{success, is_admin}` |
| `/api/login` | POST | `{username, password}` | `{success, is_admin}` |
| `/api/logout` | POST | — | `{success}` |
| `/current_user` | GET | — | `{username, nickname, avatar_preset, has_avatar, is_admin, is_super_admin, admin_class, has_reservation}` |
| `/api/is_admin` | GET | — | `{is_admin, is_super_admin, admin_class}` |

### API Données
| Route | Méthode | Description |
|---|---|---|
| `/users_list` | GET | Tous les users avec badges |
| `/leaderboard` | GET | Classement ELO avec badges |
| `/user_stats/<username>` | GET | Stats complètes d'un joueur |
| `/scores_all` | GET | Historique 100 dernières parties |
| `/reservations_all` | GET | Toutes les réservations (format legacy) |
| `/reservations_today` | GET | Réservations aujourd'hui + demain |
| `/api/babyfoot_status` | GET | Babyfoot libre/occupé + prochaines réservations |
| `/api/current_game` | GET | État actuel de la partie |
| `/api/has_active_game` | GET | Partie en cours + infos user |
| `/api/active_lobby` | GET | État actuel du lobby |
| `/api/online_users` | GET | Usernames connectés via WebSocket |
| `/api/public_stats` | GET | Stats globales (nb parties, joueurs actifs) |

### API Réservations
| Route | Méthode | Payload | Description |
|---|---|---|---|
| `/api/reserve_now` | POST | `{duration: 5|10|15, mode}` | Réserver maintenant |
| `/api/reserve_plan` | POST | `{start_time, duration, mode, date?}` | Réserver à une heure |
| `/api/reserve_and_lobby` | POST | `{duration, mode}` | Réserver + créer lobby en une fois |
| `/api/cancel_reservation_v2` | POST | `{id}` | Annuler par ID |
| `/save_reservation` | POST | legacy | Ancien format (jour/heure) — gardé pour compat |
| `/cancel_reservation` | POST | legacy | Ancien format — gardé pour compat |

### API Profil / Paramètres
| Route | Méthode | Description |
|---|---|---|
| `/api/profile` | GET | Profil complet (ELO, badges, palier) |
| `/api/profile` | POST | Modifier pseudo, bio, avatar_preset |
| `/api/upload_avatar` | POST | Upload avatar (base64 ou Cloudinary) |
| `/api/avatar/<username>` | GET | Image avatar seule (évite surcharge /current_user) |
| `/api/change_password` | POST | Changer mot de passe |

### API Cosmétiques / Quêtes
| Route | Description |
|---|---|
| `/api/my_quests` | Quêtes + progression du joueur connecté |
| `/api/my_cosmetics` | Cosmétiques débloqués + actifs |
| `/api/equip_cosmetic` | Équiper un thème ou cadre |
| `/api/cosmetics_catalog` | Catalogue complet quêtes + cosmétiques |
| `/api/admin/unlock_cosmetic` | Super admin : débloquer pour un joueur |
| `/api/admin/complete_quest` | Super admin : compléter une quête (test) |

### API Badges (Super Admin seulement)
| Route | Description |
|---|---|
| `/api/badges` | GET — liste tous les badges |
| `/api/badges/create` | POST `{name, description, icon, color, image_b64?}` |
| `/api/badges/<id>` | DELETE — supprimer un badge |
| `/api/badges/award` | POST `{username, badge_id}` — attribuer |
| `/api/badges/revoke` | POST `{username, badge_id}` — retirer |
| `/api/badges/user/<username>` | GET — badges d'un joueur |
| `/api/badges/all_users` | GET — vue globale |
| `/api/badges/upload_image` | POST — upload image badge |

### API Admin
| Route | Description |
|---|---|
| `/admin/reset_database` | POST — Super admin : vider toute la DB |
| `/api/delete_user` | POST `{username}` — Super admin : supprimer un compte |
| `/api/set_user_role` | POST `{username, role}` — Super admin : changer le rôle |

### Debug (admins)
| Route | Description |
|---|---|
| `/health` | Healthcheck DB (utilisé par Render) |
| `/debug/game` | JSON état complet : current_game, lobby, votes |
| `/debug/static` | JSON liste des fichiers static |
| `/debug/live` | Retourne 404 (page supprimée) |

---

## 12. Référence complète des événements WebSocket

### Client → Serveur (emit depuis le navigateur)

| Événement | Payload | Description |
|---|---|---|
| `create_lobby` | `{invited: []}` | Créer un lobby (admin ou réservation active requis) |
| `invite_to_lobby` | `{user}` | Inviter un joueur |
| `leave_lobby` | — | Quitter le lobby |
| `accept_lobby` | — | Accepter une invitation |
| `decline_lobby` | — | Refuser une invitation |
| `request_join_lobby` | — | Demander à rejoindre un lobby existant |
| `accept_join_request` | `{from, request_id}` | Hôte accepte une demande |
| `decline_join_request` | `{from, request_id}` | Hôte refuse une demande |
| `kick_from_lobby` | `{user}` | Exclure un joueur |
| `cancel_lobby` | — | Annuler le lobby |
| `request_team_swap` | `{with: username}` | Demander un échange d'équipe |
| `accept_team_swap` | `{request_id}` | Accepter l'échange |
| `decline_team_swap` | `{request_id}` | Refuser l'échange |
| `start_game_from_lobby` | — | Lancer la partie depuis le lobby |
| `start_game` | `{team1: [], team2: []}` | Lancer sans lobby (admin direct) |
| `update_score` | `{team: 'team1'|'team2'}` | Ajouter un but (admin seulement) |
| `stop_game` | — | Arrêter la partie |
| `reset_game` | — | Réinitialiser (admin) |
| `vote_rematch` | `{vote: 'yes'|'no'}` | Voter pour ou contre le rematch |
| `host_quit_rematch` | — | L'hôte annule le rematch |
| `unlock_servo1` | — | Débloquer servo 1 (admin) |
| `unlock_servo2` | — | Débloquer servo 2 (admin) |
| `arduino_goal` | `{secret, team}` | But ESP32 via WebSocket |
| `arduino_ping` | — | Ping Arduino |
| `get_game_state` | — | Demander l'état du jeu |

### Serveur → Clients (broadcast ou emit)

| Événement | Payload | Déclencheur |
|---|---|---|
| `game_started` | `current_game` | Partie lancée |
| `game_ended` | `current_game + winner` | Score atteint 10 |
| `game_stopped` | `{}` ou `{reason}` | Partie arrêtée manuellement |
| `game_reset` | `current_game` | Reset admin |
| `game_recovery` | `current_game` | Reconnexion en cours de partie |
| `game_state` | `{active, scores, players}` | Réponse à get_game_state |
| `score_updated` | `current_game` | But marqué (sauf 10e) |
| `score_ack` | `{team, score}` | Confirmation du but à l'émetteur |
| `elo_updated` | `{changes: [{player, old_elo, new_elo, delta, is_winner, tier_up, winstreak, quests_completed, ...}]}` | Fin de partie, ELO calculé |
| `rematch_prompt` | `{}` | Invitation à voter pour le rematch |
| `rematch_vote_update` | `{yes, no, total, no_player?}` | Mise à jour des votes |
| `rematch_cancelled` | `{}` | Rematch annulé |
| `host_replace_or_quit` | `{declined_player, host}` | Un joueur a voté NON |
| `lobby_created` | `{host, invited}` | Lobby créé |
| `lobby_update` | `active_lobby` | État du lobby modifié |
| `lobby_cancelled` | `{reason?, host?}` | Lobby annulé |
| `lobby_invitation` | `{from, to}` | Invitation reçue |
| `lobby_host_changed` | `{new_host, old_host}` | Hôte promu après déconnexion |
| `kicked_from_lobby` | `{kicked_user}` | Joueur exclu |
| `join_request` | `{from, host, request_id}` | Demande de rejoindre |
| `join_request_result` | `{accepted, host, from}` | Résultat de la demande |
| `team_swap_request` | `{from, to, request_id}` | Demande d'échange d'équipe |
| `servo1_unlock` | `{}` | Servo 1 débloqué (balle libérée) |
| `servo2_unlock` | `{}` | Servo 2 débloqué |
| `servo1_lock` | `{}` | Servo 1 bloqué |
| `servo2_lock` | `{}` | Servo 2 bloqué |
| `arduino_pong` | `{status: 'ok'}` | Réponse au ping |
| `error` | `{message}` | Erreur métier |

---

## 13. Règles critiques — NE JAMAIS ENFREINDRE

### 🔴 Service Worker (cause principale des bugs visuels)
```js
// static/sw.js — ligne 5
const CACHE_NAME = 'babyfoot-v30';
```
**Après chaque modif de CSS ou JS : incrémenter ce numéro (v30 → v31 → v32...).**
Sans ça, les navigateurs servent l'ancienne version du cache indéfiniment.
C'est la cause de 90% des bugs visuels rapportés.

### 🔴 Gunicorn — 1 seul worker
```python
# gunicorn_config.py
workers = 1  # ← NE JAMAIS METTRE PLUS
```
Flask-SocketIO en mode threading ne supporte pas plusieurs workers sans Redis/message queue.
Avec 2+ workers, les variables globales (current_game, active_lobby) ne sont pas partagées
→ bugs de synchronisation impossibles à debugger.

### 🔴 async_mode="threading"
```python
socketio = SocketIO(app, async_mode="threading", ...)
```
Render utilise le mode threading. Ne jamais passer à eventlet ou gevent sans tester.

### 🔴 Dual-mode SQL
Toujours les deux variantes. Jamais une seule.

### 🔴 Ne jamais diviser app.py
Les variables globales `current_game`, `active_lobby`, etc. sont partagées entre routes HTTP
et handlers WebSocket. Les séparer en modules casserait cette synchronisation.

---

## 14. Patterns de code à réutiliser

### Nouvelle route HTTP avec gestion d'erreur
```python
@app.route("/api/ma_route", methods=["POST"])
@handle_errors
def ma_route():
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifié"}), 401
    data = request.get_json(silent=True) or {}
    # ... logique ...
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        q = "SELECT ... WHERE username = %s" if USE_POSTGRES else "SELECT ... WHERE username = ?"
        cur.execute(q, (username,))
        row = row_to_dict(cur.fetchone())
        conn.commit()
        return jsonify({"success": True, "data": row})
    finally:
        cur.close()
        conn.close()
```

### Nouveau handler WebSocket
```python
@socketio.on('mon_event')
def handle_mon_event(data):
    username = get_socket_user()
    if not username:
        emit('error', {'message': 'Non authentifié'})
        return
    # ...
    socketio.emit('mon_event_result', {...}, namespace='/')  # broadcast tous
    emit('mon_event_ack', {...})  # réponse à l'émetteur seulement
```

### Vérification admin
```python
# Requiert admin (role >= 1)
if not is_admin(session.get('username')):
    return jsonify({"error": "Admin requis"}), 403

# Requiert super admin (role == 1, Imran seulement)
if not is_super_admin(session.get('username')):
    return jsonify({"error": "Réservé au super admin"}), 403
```

### Modifier le lobby de façon thread-safe
```python
with _lobby_lock:
    active_lobby['team1'].append(username)
    # ...
socketio.emit('lobby_update', active_lobby, namespace='/')
```

### Nouveau template
```html
{% extends "base.html" %}
{% block title %}Mon Titre{% endblock %}
{% block content %}
<div class="container">
  <!-- contenu -->
</div>
{% endblock %}
{% block scripts %}
<script>
// JS spécifique à cette page
</script>
{% endblock %}
```

---

## 15. Ce qui peut être modifié sans risque

- **CSS** : `static/design-v3.css` — modifier librement, mais incrémenter sw.js
- **Templates HTML** : librement, mais respecter `{% extends "base.html" %}`
- **Textes / labels** : tout ce qui est affiché côté client
- **Formule ELO** : `compute_elo()` dans app.py (ex: ajuster les K ou bonus)
- **Définitions des quêtes** : `QUESTS_DEFINITIONS` dans app.py
- **Catalogue cosmétiques** : `COSMETICS_CATALOG` dans app.py

## Ce qui NE doit PAS être modifié sans bien comprendre l'impact

- **Structure des tables DB** — utiliser une migration non-destructive
- **Noms des events WebSocket** — les templates côté client y sont liés
- **`_reset_game_state()` et `_launch_rematch()`** — logique centrale de fin de partie
- **`save_game_results()`** — calcule et persiste ELO + quêtes. Toute erreur ici = données corrompues
- **`gunicorn_config.py`** — ne pas toucher workers/threads
- **`sw.js`** — toujours incrémenter la version quand on modifie CSS/JS

---

## 16. Debugging rapide

### App visuellement cassée / vieux CSS
→ Navigateur sert le cache. Incrémenter `CACHE_NAME` dans `static/sw.js`.
→ Pour tester immédiatement : Chrome F12 → Application → Storage → Clear site data.

### WebSocket ne se connecte pas
→ Vérifier `CORS_ORIGINS` dans Render = domaine exact sans slash final.
→ Vérifier que `async_mode="threading"` est bien configuré.

### Sessions qui se perdent au restart
→ `SECRET_KEY` doit être une valeur fixe dans Render → Environment.
→ Si aléatoire, toutes les sessions sont invalidées à chaque restart.

### Données perdues
→ Vérifier que `DATABASE_URL` pointe vers PostgreSQL Render.
→ Sans ça, SQLite local est utilisé et les données disparaissent au restart.

### Parties zombies (bloquées en cours)
→ `GET /debug/game` pour voir l'état.
→ Un admin peut faire `WS emit 'reset_game'` depuis la page admin.
→ Nettoyage automatique après 2h via `schedule_zombie_game_cleanup()`.

### Vérifier l'état actuel en prod
```
GET /health         → DB connectée ?
GET /debug/game     → État current_game + lobby + votes
GET /debug/static   → Fichiers static présents ?
```

---

## 17. Ce qui est déjà résolu (ne pas réintroduire)

- ✅ **Race condition buts ESP32 + Socket simultanés** → `_goal_lock` (threading.Lock)
- ✅ **Race condition lobby (invite + join simultanés)** → `_lobby_lock`
- ✅ **Double invitation** → vérification `already_in` dans invite_to_lobby
- ✅ **Parties zombies** → `schedule_zombie_game_cleanup()` nettoie après 2h
- ✅ **Imports inline dispersés** → tous remontés en header de app.py
- ✅ **Cache navigateur (bug CSS)** → Service Worker version v30, à incrémenter
- ✅ **Sessions perdues** → SECRET_KEY fixe dans env
- ✅ **Types PostgreSQL incompatibles** → `migrate_teams_to_text()` corrige
- ✅ **Invitations expirées** → `cleanup_old_data()` nettoie >5 min
- ✅ **ESP32 reboot** → `api_arduino_commands` détecte >30s sans poll et vide la queue
- ✅ **SQL injection** → paramètres liés partout, jamais de concaténation de chaîne

---

## 18. Comptes du club

| Username | Rôle | Compte |
|---|---|---|
| Imran | Super Admin (1) | Créateur, accès illimité |
| Apoutou | Admin (2) | Membre fondateur |
| Hamara | Admin (2) | Membre fondateur |
| MDA | Admin (2) | Membre fondateur |
| Joueur1 | Joueur (0) | Compte physique partagé sur l'écran du babyfoot |
| Joueur2 | Joueur (0) | Compte physique partagé |
| Joueur3 | Joueur (0) | Compte physique partagé |

Les Joueur1/2/3 ont le mot de passe `guest` et sont exclus des classements ELO.

---

*Ce document a été généré après analyse complète du code. Dernière mise à jour : projet nettoyé pour Render, Railway supprimé, imports centralisés, service worker v30.*
