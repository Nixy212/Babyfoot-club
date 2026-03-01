# 🎯 BABY-FOOT CLUB — Instructions pour Claude

## Ce qu'est ce projet
Application web de gestion d'un babyfoot physique.
- **Backend** : Python / Flask + Flask-SocketIO (WebSocket temps réel)
- **DB** : PostgreSQL en prod (Render), SQLite en local
- **Frontend** : HTML/Jinja2 + CSS vanilla + JS vanilla
- **Déploiement** : Render (render.yaml)
- **Hardware optionnel** : Arduino ESP32 (détection de buts physiques)

---

## Architecture en 30 secondes

```
app.py              ← TOUT le serveur (3900 lignes) — routes HTTP + WebSocket + DB
requirements.txt    ← dépendances Python
runtime.txt         ← Python 3.11.9 (obligatoire pour Render)
render.yaml         ← config déploiement Render
gunicorn_config.py  ← 1 worker, 4 threads, timeout 120s

static/
  design-v3.css         ← TOUT le CSS (thème sombre bronze/or)
  sw.js                 ← Service Worker — VERSION ACTUELLE : v30
  profile-utils.js      ← avatars/pseudos partagés entre tous les templates
  icons.js              ← icônes SVG custom (data-bficon="...")
  global-animations.js  ← animations + reconnexion WebSocket
  socket.io.min.js      ← fallback client Socket.IO (si CDN down)

templates/
  base.html         ← layout partagé (nav, menu mobile, scripts communs)
  dashboard.html    ← page principale après login
  lobby.html        ← salle d'attente avant partie (Socket.IO)
  live-score.html   ← score en temps réel (Socket.IO)
  reservation.html  ← réservation de créneaux
  stats.html        ← statistiques joueur + graphe ELO
  top.html          ← classement ELO
  scores.html       ← historique des parties
  settings.html     ← profil, avatar, cosmétiques, quêtes
  admin.html        ← panel admin (rôles, badges, reset DB)
  index.html        ← accueil public (avant login)
  login.html / register.html
  (debug-live.html supprimé — la route /debug/live retourne 404)
```

---

## Base de données

**Dual-mode** : `USE_POSTGRES = bool(DATABASE_URL)` bascule auto.

Tables : `users`, `reservations`, `games`, `scores`, `quests`, `user_quests`, `badges`, `user_badges`

Rôles utilisateurs :
- `0` = Joueur (défaut)
- `2` = Admin (gérer users, lancer/stopper parties)
- `1` = Super Admin (tout + reset DB, badges, cosmétiques)

---

## Variables d'environnement Render (toutes déjà configurées)

| Variable | Usage |
|---|---|
| `SECRET_KEY` | Clé fixe Flask — sessions persistantes |
| `DATABASE_URL` | URL PostgreSQL Render (commence par `postgresql://`) |
| `RENDER` | Auto par Render → active SESSION_COOKIE_SECURE |
| `CORS_ORIGINS` | Domaine exact Render (ex: `https://monapp.onrender.com`) |
| `CLOUDINARY_URL` | Optionnel — avatars cloud |

---

## Règles importantes à respecter

### ⚠️ Service Worker — CRITIQUE
Le fichier `static/sw.js` contient la version du cache : `babyfoot-v34`

**À chaque modification de CSS ou JS → incrémenter cette version.**
Sans ça, les navigateurs servent l'ancienne version indéfiniment.

```js
// sw.js ligne 5
const CACHE_NAME = 'babyfoot-v34'; // → v34, v35, etc.
```

### ⚠️ Gunicorn — Ne pas changer
Toujours : 1 worker sync, 4 threads, timeout 120s.
Flask-SocketIO ne supporte pas plusieurs workers sans Redis.

### ⚠️ app.py — Dual-mode DB
Toutes les requêtes SQL ont deux versions :
```python
q = "SELECT ... WHERE username = %s" if USE_POSTGRES else "SELECT ... WHERE username = ?"
```
Ne jamais écrire une requête avec un seul format.

### ⚠️ Socket.IO — async_mode="threading"
Ne pas changer. Render utilise le mode threading, pas eventlet/gevent.

---

## Fonctionnalités principales

| Feature | Fichiers concernés |
|---|---|
| Réservation créneaux | `reservation.html` + routes `/api/reserve_*` dans `app.py` |
| Lobby temps réel | `lobby.html` + events Socket.IO `create_lobby`, `invite_to_lobby`, etc. |
| Score live | `live-score.html` + event `update_score`, `game_ended` |
| Calcul ELO | Fonction `calculate_elo()` dans `app.py` |
| Quêtes/Cosmétiques | Tables `quests`, `user_quests` + fonction `check_quests()` dans `app.py` |
| Badges | Tables `badges`, `user_badges` + routes `/api/badges/*` |
| Arduino | Routes `/api/arduino/*` (sans session, accès direct ESP32) |

---

## Système de Cosmétiques

Les cosmétiques (thèmes et cadres d'avatar) sont débloqués via les quêtes.

### Clés des cosmétiques (`COSMETICS_CATALOG` dans `app.py`)
- Thèmes : `theme_fire`, `theme_night`, `theme_gold`, `theme_royal`, `theme_master`
- Cadres : `frame_bronze`, `frame_flame`, `frame_phoenix`
- `default` (thème) et `none` (cadre) sont toujours disponibles sans déverrouillage

### API endpoints
- `GET /api/my_cosmetics` → `{ unlocked: [...], active_theme, active_frame, catalog }`
- `POST /api/equip_cosmetic` → `{ type: "theme"|"frame", key: "..." }` — vérifie que le cosmétique est débloqué

### Affichage dans `settings.html`
- `unlockedCosmetics` est chargé via `/api/my_cosmetics` au chargement de la page
- Les items verrouillés sont rendus grisés avec icône 🔒 et le clic affiche un toast sans appeler l'API

---

## Ce qui est optionnel (peut être supprimé sans casser l'app)

- `static/confetti.js` — effets visuels fin de partie
- `static/animations.js` — animations UI décoratives
- `static/pwa.js` + `manifest.json` — installation mobile PWA
- `railway.json` + `.railwayignore` + `Procfile` — inutiles sur Render
- `templates/debug-live.html` — supprimé (route retourne 404)
- `tests/` — jamais exécuté en prod

---

## Bugs Render connus et résolus

| Problème | Cause | Solution |
|---|---|---|
| Visuel cassé / vieux CSS | Service Worker sert le cache | Incrémenter version dans `sw.js` |
| Déconnexions sessions | SECRET_KEY aléatoire au restart | SECRET_KEY fixe dans Render env |
| Données perdues | SQLite éphémère | DATABASE_URL PostgreSQL configurée |
| WebSocket refusés | CORS mal configuré | CORS_ORIGINS = domaine exact Render |
| App lente au démarrage | Cold start Render free tier | Normal — utiliser UptimeRobot pour ping |
| Pages vides (stats, top, reservation, live-score) | HTML manquant dans `{% block body %}` — seul le JS était présent | HTML reconstruit pour chaque page avec tous les IDs attendus par le JS |
| Pages cassées (scores, settings) | `</div>` orphelin au début du `{% block body %}` | Balise parasite supprimée |
| "Slot invalide (theme/frame)" sur cosmétiques | L'équipement d'un cosmétatique verrouillé renvoyait une erreur sans indication visuelle | Les boutons verrouillés sont maintenant grisés + icône 🔒 + texte "Verrouillé", et le clic affiche un toast d'explication au lieu d'appeler l'API |
| Slots vides lobby peu clairs | Les slots fantômes ne montraient pas comment inviter | Slots vides sans guest affichent bouton "Inviter" qui scroll vers la section invitation |
| Équipes vides dans le lobby (bug racine) | Navigation dashboard→lobby déconnecte le WebSocket ; `handle_disconnect` retirait immédiatement l'hôte du lobby avant que la page lobby se reconnecte | Délai de grâce de 8s (`_lobby_grace`) : si le joueur se reconnecte dans ce délai, le retrait est annulé. Voir `_lobby_grace` et `_LOBBY_GRACE_SECONDS` dans `app.py` |

---

## Comment modifier proprement

1. **CSS** → modifier `static/design-v3.css` + incrémenter version dans `static/sw.js`
2. **Nouvelle route HTTP** → ajouter dans `app.py` + penser au dual-mode SQL
3. **Nouveau event WebSocket** → ajouter handler `@socketio.on(...)` dans `app.py`
4. **Nouveau template** → hériter de `base.html` avec `{% extends "base.html" %}`
5. **Déployer** → push sur GitHub → Render redéploie automatiquement

---

## Stack versions

```
Flask==3.0.0
flask-socketio==5.3.6
python-socketio==5.11.0
python-engineio==4.9.0
gunicorn==21.2.0
psycopg2-binary==2.9.10
bcrypt==4.1.2
Python 3.11.9
```

---

## 🐛 Bugs corrigés (session 2025-03-01)

### Bug 1 — Bouton "Créer Lobby" du dashboard inopérant
**Cause** : `handleLobbyBtn()` utilisait `socket.emit('create_lobby')` qui exige une réservation active (`has_active_reservation`). Sans réservation, l'erreur socket était ignorée et l'utilisateur restait bloqué.

**Fix** (`templates/dashboard.html`) : `handleLobbyBtn` utilise désormais `fetch('/api/reserve_and_lobby')` qui crée automatiquement une réservation de 15 min + le lobby en une seule opération atomique. Le bouton est activé pour tous les utilisateurs connectés (la réservation se crée à la volée).

### Bug 2 — Joueur1/Joueur2/Joueur3 dupliqués dans les deux équipes
**Cause** : `renderTeam()` calculait `guestsForDisplay[i]` avec `i` local à chaque équipe. Résultat : team1 et team2 affichaient le même guest (ex: Joueur1 dans les deux slots).

**Fix** (`templates/lobby.html`) : `renderTeam()` accepte un paramètre `guestOffset`. `updateLobbyUI()` calcule le nombre de slots vides de team1 et passe cet offset à team2, garantissant que chaque équipe affiche des guests distincts.

### Nota bene — L'hôte dans team1
L'hôte est bien ajouté à `team1` côté serveur lors de la création du lobby (`reserve_and_lobby` et `handle_create_lobby`). Ce bug était un symptôme du Bug 1 : si le lobby n'était jamais créé (socket bloqué), `lobby.html` ne trouvait pas l'hôte dans le lobby et redirectait vers `/dashboard`.

### Réécriture complète lobby.html (session 2025-03-01 v2)

Le fichier `templates/lobby.html` a été entièrement réécrit.

**Problèmes racines identifiés :**
1. Logique d'affichage fragmentée en plusieurs fonctions avec états partagés → bugs de timing
2. `renderTeam()` avec `return` prématuré empêchait l'affichage des ghost slots
3. Calcul de l'offset des guests cassé quand `team1` était vide
4. Variables globales (`allUsers`, `lobbyData`) non synchronisées entre appels async

**Architecture nouvelle :**
- Une seule fonction `render()` qui reconstruit tout l'UI depuis `LOBBY` (source de vérité unique)
- `buildTeam(id, players, ghosts, addVirtualHost, color)` : logique claire et déterministe
  - `hostVirtual` : si `team1=[]` mais hôte existe → affiche l'hôte + 1 ghost
  - `free = GUESTS.filter(g => !placed)` puis `ghostsT1 = free.slice(0, t1Ghosts)`, `ghostsT2 = free.slice(t1Ghosts, ...)` → garantit 0 doublon
- Nommage explicite : `ME`, `LOBBY`, `GUESTS`, `IS_ADMIN`
- `socket.on('lobby_update')` → `LOBBY = data; render();` sans aucune logique supplémentaire
