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
  debug-live.html   ← debug dev uniquement, jamais montré aux users
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
Le fichier `static/sw.js` contient la version du cache : `babyfoot-v30`

**À chaque modification de CSS ou JS → incrémenter cette version.**
Sans ça, les navigateurs servent l'ancienne version indéfiniment.

```js
// sw.js ligne 5
const CACHE_NAME = 'babyfoot-v30'; // → v31, v32, etc.
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

## Ce qui est optionnel (peut être supprimé sans casser l'app)

- `static/confetti.js` — effets visuels fin de partie
- `static/animations.js` — animations UI décoratives
- `static/pwa.js` + `manifest.json` — installation mobile PWA
- `railway.json` + `.railwayignore` + `Procfile` — inutiles sur Render
- `templates/debug-live.html` — debug dev
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
