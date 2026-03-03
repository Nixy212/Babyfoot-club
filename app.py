import threading as _threading
import re as _re
import html as _html
import base64 as _base64
import uuid as _uuid

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
from functools import wraps
import zoneinfo
TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
def now_local():
    """Retourne l'heure actuelle en heure de Paris (UTC+1 hiver / UTC+2 été)."""
    return datetime.now(tz=TZ_PARIS).replace(tzinfo=None)
import json
import bcrypt
import os
import logging
import traceback
import sys
import collections
import time as _time

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ── Cloudinary (avatars) ──────────────────────────────────────
# Configurez CLOUDINARY_URL dans Render → Environment pour activer.
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')
USE_CLOUDINARY = bool(CLOUDINARY_URL)
if USE_CLOUDINARY:
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(url=CLOUDINARY_URL)
        logger.info("Cloudinary configuré — avatars uploadés dans le cloud")
    except ImportError:
        USE_CLOUDINARY = False
        logger.warning("Package 'cloudinary' non installé — fallback base64 activé")
    except ValueError as e:
        USE_CLOUDINARY = False
        logger.error(f"CLOUDINARY_URL invalide ({e}) — fallback base64 activé. Vérifiez le format : cloudinary://API_KEY:API_SECRET@CLOUD_NAME")
    except Exception as e:
        USE_CLOUDINARY = False
        logger.error(f"Erreur Cloudinary au démarrage ({e}) — fallback base64 activé")
        logger.warning("Package 'cloudinary' non installé — avatars stockés en DB (fallback). Ajoutez cloudinary dans requirements.txt")

app = Flask(__name__, static_folder='static', static_url_path='/static')
# ProxyFix : essentiel pour que Flask comprenne HTTPS derrière Render
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)

# ── Secrets ──────────────────────────────────────────────────

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    import secrets as _secrets
    _secret_key = _secrets.token_hex(32)
    logger.warning("SECRET_KEY non definie — cle aleatoire generee (sessions invalidees au redemarrage). Definissez SECRET_KEY dans Render → Environment !")

app.secret_key = _secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Render met RENDER=true automatiquement
_is_production = (
    os.environ.get('RENDER') is not None
    or os.environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true'
)
app.config['SESSION_COOKIE_SECURE'] = _is_production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 Mo max request body

# ── SocketIO ──────────────────────────────────────────────────

# CORS : définir CORS_ORIGINS dans Render avec ton domaine (ex: https://monapp.onrender.com)
# Supporte 1 origine ou une liste séparée par virgules.
def _parse_cors_origins(raw):
    raw = (raw or '').strip()
    if not raw:
        return '*'
    parts = []
    for p in raw.split(','):
        p = p.strip()
        if not p:
            continue
        p = p.strip("'\"").rstrip('/')
        if p:
            parts.append(p)
    if not parts:
        return '*'
    return parts[0] if len(parts) == 1 else parts

_CORS_RAW = os.environ.get('CORS_ORIGINS', '')
_ALLOWED_ORIGINS = _parse_cors_origins(_CORS_RAW)
logger.info(f"CORS autorisé : {_ALLOWED_ORIGINS}")
socketio = SocketIO(
    app,
    cors_allowed_origins=_ALLOWED_ORIGINS,
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    async_mode="threading",
    manage_session=True,
    allow_upgrades=True,
    max_http_buffer_size=1_000_000,
    cookie=None,  # Ne pas utiliser les cookies SocketIO, on utilise les sessions Flask
)

# ── Service Worker ────────────────────────────────────────────

@app.route('/sw.js')
def service_worker():
    response = app.send_static_file('sw.js')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

# ── Headers HTTP globaux ──────────────────────────────────────

@app.after_request
def set_headers(response):
    if response.content_type and any(ct in response.content_type for ct in ['javascript', 'css', 'image', 'font']):
        response.headers['Cache-Control'] = 'public, max-age=604800, stale-while-revalidate=86400'
    elif response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # CSP : scripts/styles locaux + CDN Font Awesome
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.socket.io https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https://res.cloudinary.com; "
        "connect-src 'self' wss: ws:; "
        "frame-ancestors 'none';"
    )
    return response

@app.before_request
def handle_http_for_arduino():
    # Les endpoints Arduino sont accessibles en HTTP (pas de session Flask)
    if request.path.startswith('/api/arduino/'):
        return None
    return None

# ── Base de donnees ───────────────────────────────────────────

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    DB_PATH = os.environ.get('DB_PATH', 'babyfoot.db')

# ── Etat global ───────────────────────────────────────────────

current_game = {
    "team1_score": 0, "team2_score": 0,
    "team1_players": [], "team2_players": [],
    "active": False, "started_by": None,
    "reserved_by": None, "started_at": None
}

active_lobby = {
    "host": None, "invited": [], "accepted": [],
    "declined": [], "team1": [], "team2": [], "active": False
}

# ── Verrou lobby (évite les race conditions invitation + join simultanés) ──
_lobby_lock = _threading.Lock()

# Délai de grâce lobby : username -> timestamp de déconnexion
# Si un joueur se reconnecte dans les 8s, il n'est pas retiré du lobby
_lobby_grace = {}
_LOBBY_GRACE_SECONDS = 8

team_swap_requests = {}
rematch_votes = {"team1": [], "team2": []}
rematch_no_votes = []         # Joueurs qui ont voté NON
servo_commands = {"servo1": [], "servo2": []}
rematch_pending = False       # True entre game_ended et le lancement du rematch
pending_invitations = {}      # username -> {from, timestamp}
pending_rematch_replacements = {}  # replacement_username -> invitation rematch en attente

# ── connected_users : sid -> username pour les handlers SocketIO ──
connected_users = {}

def get_socket_user():
    # Identité WS strictement liée au SID courant.
    # Évite qu'une session HTTP changée dans un autre onglet applique des actions au mauvais compte.
    return connected_users.get(request.sid)

def emit_to_user(username, event_name, payload):
    """Emet un event Socket.IO a toutes les connexions d'un utilisateur."""
    delivered = False
    for sid, user in list(connected_users.items()):
        if user == username:
            socketio.emit(event_name, payload, to=sid, namespace='/')
            delivered = True
    return delivered

# ── Rate limiting login (anti brute-force) ────────────────────

_login_attempts = collections.defaultdict(list)  # ip -> [timestamps]
LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 60

def check_rate_limit(ip):
    """Retourne True si l'IP est bloquee (trop de tentatives)."""
    now = _time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= LOGIN_MAX_ATTEMPTS:
        return True
    _login_attempts[ip].append(now)
    return False

# ── Verrou anti double-but (ESP32 HTTP + Socket simultanes) ──

_goal_processing = False
_goal_lock = _threading.Lock()  # verrou thread-safe pour les buts
_reservation_lock = _threading.Lock()  # verrou anti course pour creation de reservation

# ── Connexion DB ──────────────────────────────────────────────

def get_db_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # IMPORTANT : activer les foreign keys SQLite a chaque connexion
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

# ── Initialisation DB ─────────────────────────────────────────

def init_database():
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(200) NOT NULL,
                total_goals INTEGER DEFAULT 0,
                total_games INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                nickname VARCHAR(50) DEFAULT NULL,
                bio VARCHAR(200) DEFAULT NULL,
                avatar_preset VARCHAR(10) DEFAULT NULL,
                avatar_url TEXT DEFAULT NULL,
                elo INTEGER DEFAULT 1000,
                role INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id SERIAL PRIMARY KEY,
                day VARCHAR(20) NOT NULL,
                time VARCHAR(30) NOT NULL,
                team1 TEXT NOT NULL DEFAULT '[]',
                team2 TEXT NOT NULL DEFAULT '[]',
                mode VARCHAR(10) DEFAULT '1v1',
                reserved_by VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration_minutes INTEGER DEFAULT 15,
                UNIQUE (start_time, reserved_by)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id SERIAL PRIMARY KEY,
                team1_players TEXT NOT NULL,
                team2_players TEXT NOT NULL,
                team1_score INTEGER NOT NULL,
                team2_score INTEGER NOT NULL,
                winner VARCHAR(10) NOT NULL,
                mode VARCHAR(10) DEFAULT '1v1',
                started_by VARCHAR(50),
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                total_goals INTEGER DEFAULT 0,
                total_games INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                nickname TEXT DEFAULT NULL,
                bio TEXT DEFAULT NULL,
                avatar_preset TEXT DEFAULT NULL,
                avatar_url TEXT DEFAULT NULL,
                elo INTEGER DEFAULT 1000,
                role INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                team1 TEXT NOT NULL DEFAULT '[]',
                team2 TEXT NOT NULL DEFAULT '[]',
                mode TEXT DEFAULT '1v1',
                reserved_by TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER DEFAULT 15
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                date TEXT DEFAULT (datetime('now'))
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team1_players TEXT NOT NULL,
                team2_players TEXT NOT NULL,
                team1_score INTEGER NOT NULL,
                team2_score INTEGER NOT NULL,
                winner TEXT NOT NULL,
                mode TEXT DEFAULT '1v1',
                started_by TEXT,
                date TEXT DEFAULT (datetime('now'))
            )
        """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"DB initialisee ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")

def migrate_reservations_v2():
    """Ajoute les colonnes start_time, end_time, duration_minutes et la contrainte UNIQUE si elles n'existent pas."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                ALTER TABLE reservations
                ADD COLUMN IF NOT EXISTS start_time TIMESTAMP,
                ADD COLUMN IF NOT EXISTS end_time TIMESTAMP,
                ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 15
            """)
            # Ajouter la contrainte UNIQUE si elle n'existe pas encore
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'reservations_start_time_reserved_by_key'
                    ) THEN
                        ALTER TABLE reservations
                        ADD CONSTRAINT reservations_start_time_reserved_by_key
                        UNIQUE (start_time, reserved_by);
                    END IF;
                END $$;
            """)
        else:
            cur.execute("PRAGMA table_info(reservations)")
            cols = [row[1] for row in cur.fetchall()]
            if 'start_time' not in cols:
                cur.execute("ALTER TABLE reservations ADD COLUMN start_time TEXT")
            if 'end_time' not in cols:
                cur.execute("ALTER TABLE reservations ADD COLUMN end_time TEXT")
            if 'duration_minutes' not in cols:
                cur.execute("ALTER TABLE reservations ADD COLUMN duration_minutes INTEGER DEFAULT 15")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Migration v2: {e}")

def migrate_elo_v2():
    """Ajoute winstreak et total_wins à la table users (non-destructif)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS winstreak INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_wins INTEGER DEFAULT 0")
        else:
            cur.execute("PRAGMA table_info(users)")
            cols = [row[1] for row in cur.fetchall()]
            if 'winstreak' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN winstreak INTEGER DEFAULT 0")
            if 'total_wins' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN total_wins INTEGER DEFAULT 0")
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Migration ELO v2 : colonnes winstreak + total_wins OK")
    except Exception as e:
        logger.warning(f"Migration ELO v2: {e}")

def migrate_cosmetics_v1():
    """Ajoute les colonnes cosmétiques + tables quêtes (non-destructif)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Colonnes users
        if USE_POSTGRES:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS unlocked_cosmetics TEXT DEFAULT '[]'")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS active_theme TEXT DEFAULT 'default'")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS active_frame TEXT DEFAULT 'none'")
            # Table quêtes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quests (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    icon VARCHAR(10),
                    condition_type VARCHAR(50),
                    condition_value INTEGER DEFAULT 1,
                    reward_cosmetic VARCHAR(100),
                    reward_label VARCHAR(100)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quests (
                    username VARCHAR(50) NOT NULL,
                    quest_key VARCHAR(50) NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed BOOLEAN DEFAULT FALSE,
                    completed_at TIMESTAMP,
                    PRIMARY KEY (username, quest_key)
                )
            """)
        else:
            cur.execute("PRAGMA table_info(users)")
            cols = [row[1] for row in cur.fetchall()]
            if 'unlocked_cosmetics' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN unlocked_cosmetics TEXT DEFAULT '[]'")
            if 'active_theme' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN active_theme TEXT DEFAULT 'default'")
            if 'active_frame' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN active_frame TEXT DEFAULT 'none'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    icon TEXT,
                    condition_type TEXT,
                    condition_value INTEGER DEFAULT 1,
                    reward_cosmetic TEXT,
                    reward_label TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quests (
                    username TEXT NOT NULL,
                    quest_key TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    completed_at TEXT,
                    PRIMARY KEY (username, quest_key)
                )
            """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Migration cosmetics v1 OK")
    except Exception as e:
        logger.warning(f"Migration cosmetics v1: {e}")

def migrate_badges_v1():
    """
    Crée les tables badges et user_badges (non-destructif).
    - badges      : catalogue des badges créés par Imran
    - user_badges : attribution badge ↔ joueur
    """
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS badges (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(80)  NOT NULL,
                    description TEXT,
                    icon        VARCHAR(20)  DEFAULT '🏅',
                    color       VARCHAR(20)  DEFAULT '#cd7f32',
                    image_url   TEXT         DEFAULT NULL,
                    created_by  VARCHAR(50)  NOT NULL DEFAULT 'Imran',
                    created_at  TIMESTAMP    DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_badges (
                    id          SERIAL PRIMARY KEY,
                    username    VARCHAR(50)  NOT NULL,
                    badge_id    INTEGER      NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
                    awarded_by  VARCHAR(50)  NOT NULL DEFAULT 'Imran',
                    awarded_at  TIMESTAMP    DEFAULT NOW(),
                    UNIQUE (username, badge_id)
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS badges (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    description TEXT,
                    icon        TEXT    DEFAULT '🏅',
                    color       TEXT    DEFAULT '#cd7f32',
                    image_url   TEXT    DEFAULT NULL,
                    created_by  TEXT    NOT NULL DEFAULT 'Imran',
                    created_at  TEXT    DEFAULT (datetime('now'))
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_badges (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT    NOT NULL,
                    badge_id    INTEGER NOT NULL,
                    awarded_by  TEXT    NOT NULL DEFAULT 'Imran',
                    awarded_at  TEXT    DEFAULT (datetime('now')),
                    UNIQUE (username, badge_id)
                )
            """)
        conn.commit()
        # Migration non-destructive : ajouter image_url si absent (bases existantes)
        try:
            if USE_POSTGRES:
                cur.execute("ALTER TABLE badges ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT NULL")
            else:
                try:
                    cur.execute("ALTER TABLE badges ADD COLUMN image_url TEXT DEFAULT NULL")
                except Exception:
                    pass  # colonne deja presente
            conn.commit()
        except Exception as e_alter:
            logger.warning(f"Migration badges image_url (non-bloquant): {e_alter}")
        cur.close()
        conn.close()
        logger.info("Migration badges v1 OK")
    except Exception as e:
        logger.warning(f"Migration badges v1: {e}")

# Définition des quêtes (source unique de vérité)
QUESTS_DEFINITIONS = [
    {"key": "first_win",    "name": "Première Victoire",   "icon": "🏆", "description": "Gagner ta première partie",          "condition_type": "total_wins",  "condition_value": 1,  "reward_cosmetic": "frame_bronze",   "reward_label": "Cadre Bronze"},
    {"key": "streak_3",     "name": "En Feu",              "icon": "🔥", "description": "Enchaîner 3 victoires d'affilée",    "condition_type": "winstreak",   "condition_value": 3,  "reward_cosmetic": "theme_fire",     "reward_label": "Thème Fire 🔥"},
    {"key": "streak_5",     "name": "Inarrêtable",         "icon": "👑", "description": "Enchaîner 5 victoires d'affilée",    "condition_type": "winstreak",   "condition_value": 5,  "reward_cosmetic": "frame_flame",    "reward_label": "Cadre Flamme Animée"},
    {"key": "perfect_game", "name": "Perfectionniste",     "icon": "🎯", "description": "Gagner une partie 10-0",             "condition_type": "perfect_game","condition_value": 1,  "reward_cosmetic": "badge_perfect",  "reward_label": "Badge Perfectionniste"},
    {"key": "games_10",     "name": "Fidèle",              "icon": "🎮", "description": "Jouer 10 parties",                  "condition_type": "total_games", "condition_value": 10, "reward_cosmetic": "theme_night",    "reward_label": "Thème Nuit 🌙"},
    {"key": "goals_50",     "name": "Buteur",              "icon": "⚽", "description": "Marquer 50 buts au total",          "condition_type": "total_goals", "condition_value": 50, "reward_cosmetic": "theme_gold",     "reward_label": "Thème Gold ✨"},
    {"key": "remontada",    "name": "Phénix",              "icon": "😤", "description": "Perdre 0-5 puis remporter la partie","condition_type": "remontada",   "condition_value": 1,  "reward_cosmetic": "frame_phoenix",  "reward_label": "Cadre Phénix"},
    {"key": "top1",         "name": "Champion",            "icon": "🥇", "description": "Être n°1 du classement",            "condition_type": "rank",        "condition_value": 1,  "reward_cosmetic": "theme_royal",    "reward_label": "Thème Royal 👑"},
    {"key": "master_elo",   "name": "Maître",              "icon": "🏆", "description": "Atteindre 1700 ELO",                "condition_type": "elo",         "condition_value": 1700,"reward_cosmetic": "theme_master",  "reward_label": "Thème Maître Ultra"},
]

# Définition des cosmétiques (pour le frontend)
COSMETICS_CATALOG = {
    # Thèmes live-score
    "theme_fire":   {"type": "theme", "label": "Thème Fire",   "icon": "🔥", "preview_colors": ["#1a0500", "#3d0a00", "#ff4500"],  "css_class": "theme-fire"},
    "theme_night":  {"type": "theme", "label": "Thème Nuit",   "icon": "🌙", "preview_colors": ["#0a0015", "#1a0035", "#7c3aed"],  "css_class": "theme-night"},
    "theme_gold":   {"type": "theme", "label": "Thème Gold",   "icon": "✨", "preview_colors": ["#1a1200", "#2d2000", "#ffd700"],  "css_class": "theme-gold"},
    "theme_royal":  {"type": "theme", "label": "Thème Royal",  "icon": "👑", "preview_colors": ["#020820", "#071040", "#1e3a8a"],  "css_class": "theme-royal"},
    "theme_master": {"type": "theme", "label": "Thème Maître", "icon": "🏆", "preview_colors": ["#0d0d0d", "#1a1a1a", "#cd7f32"],  "css_class": "theme-master"},
    # Cadres avatar
    "frame_bronze":  {"type": "frame", "label": "Cadre Bronze",         "icon": "🥉", "css_class": "frame-bronze"},
    "frame_flame":   {"type": "frame", "label": "Cadre Flamme Animée",  "icon": "🔥", "css_class": "frame-flame"},
    "frame_phoenix": {"type": "frame", "label": "Cadre Phénix",         "icon": "😤", "css_class": "frame-phoenix"},
    # Badges profil
    "badge_perfect": {"type": "badge", "label": "Perfectionniste",      "icon": "🎯", "css_class": "badge-perfect"},
}

def seed_quests():
    """Insère les quêtes de base si elles n'existent pas."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for q in QUESTS_DEFINITIONS:
            if USE_POSTGRES:
                cur.execute("""
                    INSERT INTO quests (key, name, description, icon, condition_type, condition_value, reward_cosmetic, reward_label)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET
                        name=EXCLUDED.name, description=EXCLUDED.description,
                        reward_cosmetic=EXCLUDED.reward_cosmetic, reward_label=EXCLUDED.reward_label
                """, (q["key"], q["name"], q["description"], q["icon"],
                      q["condition_type"], q["condition_value"], q["reward_cosmetic"], q["reward_label"]))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO quests (key, name, description, icon, condition_type, condition_value, reward_cosmetic, reward_label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (q["key"], q["name"], q["description"], q["icon"],
                      q["condition_type"], q["condition_value"], q["reward_cosmetic"], q["reward_label"]))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Seed quests: {e}")

def check_and_unlock_quests(username, conn, cur, player_data):
    """
    Vérifie et débloque les quêtes pour un joueur après une partie.
    player_data = dict avec elo, total_wins, total_games, total_goals, winstreak, is_winner, score_l, score_w, rank
    Retourne la liste des quêtes nouvellement complétées.
    """
    newly_completed = []
    try:
        for qdef in QUESTS_DEFINITIONS:
            key = qdef["key"]
            ctype = qdef["condition_type"]
            cval  = qdef["condition_value"]
            # Récupérer progression actuelle
            q_sel = ("SELECT progress, completed FROM user_quests WHERE username=%s AND quest_key=%s"
                     if USE_POSTGRES else
                     "SELECT progress, completed FROM user_quests WHERE username=? AND quest_key=?")
            cur.execute(q_sel, (username, key))
            row = row_to_dict(cur.fetchone())
            if row and (row.get("completed") or row.get("completed") == 1):
                continue  # déjà complétée

            # Calcul de la nouvelle progression
            new_progress = 0
            completed = False
            if ctype == "total_wins":
                new_progress = player_data.get("total_wins", 0)
                completed = new_progress >= cval
            elif ctype == "winstreak":
                new_progress = player_data.get("winstreak", 0)
                completed = new_progress >= cval
            elif ctype == "total_games":
                new_progress = player_data.get("total_games", 0)
                completed = new_progress >= cval
            elif ctype == "total_goals":
                new_progress = player_data.get("total_goals", 0)
                completed = new_progress >= cval
            elif ctype == "perfect_game":
                if player_data.get("is_winner") and player_data.get("score_l", 99) == 0:
                    new_progress = 1
                    completed = True
            elif ctype == "remontada":
                if player_data.get("remontada", False):
                    new_progress = 1
                    completed = True
            elif ctype == "elo":
                new_progress = player_data.get("elo", 0)
                completed = new_progress >= cval
            elif ctype == "rank":
                new_progress = 1 if player_data.get("rank", 99) == 1 else 0
                completed = new_progress >= cval

            # Upsert progression
            if USE_POSTGRES:
                cur.execute("""
                    INSERT INTO user_quests (username, quest_key, progress, completed, completed_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username, quest_key) DO UPDATE SET
                        progress=EXCLUDED.progress,
                        completed=EXCLUDED.completed,
                        completed_at=EXCLUDED.completed_at
                """, (username, key, new_progress, completed,
                      now_local().isoformat() if completed else None))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO user_quests (username, quest_key, progress, completed, completed_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, key, new_progress, 1 if completed else 0,
                      now_local().isoformat() if completed else None))

            if completed:
                # Débloquer le cosmétique
                cosmetic = qdef.get("reward_cosmetic")
                if cosmetic:
                    q_user = ("SELECT unlocked_cosmetics FROM users WHERE username=%s"
                              if USE_POSTGRES else
                              "SELECT unlocked_cosmetics FROM users WHERE username=?")
                    cur.execute(q_user, (username,))
                    urow = row_to_dict(cur.fetchone()) or {}
                    try:
                        unlocked = json.loads(urow.get("unlocked_cosmetics") or "[]")
                    except Exception:
                        unlocked = []
                    if cosmetic not in unlocked:
                        unlocked.append(cosmetic)
                        q_upd = ("UPDATE users SET unlocked_cosmetics=%s WHERE username=%s"
                                 if USE_POSTGRES else
                                 "UPDATE users SET unlocked_cosmetics=? WHERE username=?")
                        cur.execute(q_upd, (json.dumps(unlocked), username))
                newly_completed.append({
                    "key": key,
                    "name": qdef["name"],
                    "icon": qdef["icon"],
                    "reward_cosmetic": cosmetic,
                    "reward_label": qdef.get("reward_label", ""),
                })
    except Exception as e:
        logger.error(f"check_and_unlock_quests({username}): {e}")
    return newly_completed

def migrate_teams_to_text():
    """Corrige les colonnes mal typees dans reservations (PostgreSQL)."""
    if not USE_POSTGRES:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- Fix 1 : team1/team2 TEXT[] -> TEXT ---
        cur.execute("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'reservations' AND column_name IN ('team1', 'team2')
        """)
        cols = {row['column_name']: row['udt_name'] for row in cur.fetchall()}
        for col in ['team1', 'team2']:
            if col in cols and cols[col] != 'text':
                logger.info(f"Migration: {col} ({cols[col]}) -> TEXT")
                cur.execute(f"ALTER TABLE reservations ALTER COLUMN {col} TYPE TEXT USING {col}::text")
                cur.execute(f"ALTER TABLE reservations ALTER COLUMN {col} SET DEFAULT '[]'")
                logger.info(f"Migration {col} TEXT[] -> TEXT OK")

        # --- Fix 2 : colonne 'time' trop courte (VARCHAR(10) -> VARCHAR(30)) ---
        cur.execute("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'reservations' AND column_name = 'time'
        """)
        row = cur.fetchone()
        if row and row['character_maximum_length'] and row['character_maximum_length'] < 30:
            logger.info(f"Migration: colonne time VARCHAR({row['character_maximum_length']}) -> VARCHAR(30)")
            cur.execute("ALTER TABLE reservations ALTER COLUMN time TYPE VARCHAR(30)")
            logger.info("Migration time VARCHAR -> VARCHAR(30) OK")

        # --- Fix 3 : colonne 'mode' trop courte si besoin ---
        cur.execute("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'reservations' AND column_name = 'mode'
        """)
        row = cur.fetchone()
        if row and row['character_maximum_length'] and row['character_maximum_length'] < 20:
            logger.info(f"Migration: colonne mode VARCHAR({row['character_maximum_length']}) -> VARCHAR(20)")
            cur.execute("ALTER TABLE reservations ALTER COLUMN mode TYPE VARCHAR(20)")
            logger.info("Migration mode VARCHAR -> VARCHAR(20) OK")

        # --- Fix 4 : nouvelles colonnes profil utilisateur ---
        for col, definition in [
            ('nickname', 'VARCHAR(50)'),
            ('bio', 'VARCHAR(200)'),
            ('avatar_preset', 'VARCHAR(10)'),
            ('avatar_url', 'TEXT'),
            ('elo', 'INTEGER DEFAULT 1000'),
            ('role', 'INTEGER DEFAULT 0'),
        ]:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                conn.commit()
                logger.info(f"Migration: colonne users.{col} ajoutée")
            except Exception:
                conn.rollback()  # colonne existe déjà

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Migration schema: {e}")

def seed_accounts():
    """
    Crée les comptes initiaux du club.
    Les mots de passe admin sont lus depuis les variables d'environnement Render :
      SEED_PW_IMRAN, SEED_PW_APOUTOU, SEED_PW_HAMARA, SEED_PW_MDA
    Les comptes Joueur1/2/3 gardent le mot de passe 'guest' (comptes physiques partagés).
    """
    accounts = [
        ("Imran",   os.environ.get("SEED_PW_IMRAN",   ""), 1),
        ("Apoutou", os.environ.get("SEED_PW_APOUTOU", ""), 2),
        ("Hamara",  os.environ.get("SEED_PW_HAMARA",  ""), 2),
        ("MDA",     os.environ.get("SEED_PW_MDA",     ""), 2),
        ("Joueur1", "guest", 0),
        ("Joueur2", "guest", 0),
        ("Joueur3", "guest", 0),
    ]
    # Ignorer les comptes sans mot de passe configuré (variables non définies)
    accounts = [(u, p, r) for u, p, r in accounts if p]
    if not [a for a in accounts if a[2] >= 1]:
        logger.warning(
            "⚠️  Aucun compte admin seed configuré ! "
            "Définissez SEED_PW_IMRAN, SEED_PW_APOUTOU, etc. dans Render → Environment."
        )
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for username, password, role in accounts:
            q = "SELECT username, role FROM users WHERE username = %s" if USE_POSTGRES else "SELECT username, role FROM users WHERE username = ?"
            cur.execute(q, (username,))
            existing = row_to_dict(cur.fetchone())
            if not existing:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                q2 = (
                    "INSERT INTO users (username, password, total_goals, total_games, role) VALUES (%s, %s, 0, 0, %s)"
                    if USE_POSTGRES else
                    "INSERT INTO users (username, password, total_goals, total_games, role) VALUES (?, ?, 0, 0, ?)"
                )
                cur.execute(q2, (username, hashed, role))
            elif existing.get('role') is None or existing.get('role') != role:
                # Mettre à jour le rôle si changé
                q3 = "UPDATE users SET role = %s WHERE username = %s" if USE_POSTGRES else "UPDATE users SET role = ? WHERE username = ?"
                cur.execute(q3, (role, username))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Seed accounts: {e}")

def cleanup_old_data():
    """Nettoie les donnees anciennes et les reservations expirees."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("DELETE FROM scores WHERE date < NOW() - INTERVAL '6 months'")
            cur.execute("DELETE FROM games WHERE date < NOW() - INTERVAL '6 months'")
            # Supprimer les reservations dont la fin est passee depuis plus de 1 jour
            cur.execute("DELETE FROM reservations WHERE end_time < NOW() - INTERVAL '1 day'")
        else:
            cur.execute("DELETE FROM scores WHERE date < datetime('now', '-6 months')")
            cur.execute("DELETE FROM games WHERE date < datetime('now', '-6 months')")
            # Supprimer les reservations dont la fin est passee depuis plus de 1 jour
            cur.execute("DELETE FROM reservations WHERE end_time < datetime('now', '-1 day')")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erreur cleanup: {e}")

    # Nettoyer les invitations expirees (> 5 minutes)
    now = _time.time()
    expired = [u for u, inv in list(pending_invitations.items()) if now - inv.get('timestamp', 0) > 300]
    for u in expired:
        pending_invitations.pop(u, None)
    if expired:
        logger.info(f"Invitations expirees nettoyees: {expired}")

def schedule_cleanup():
    cleanup_old_data()
    def _loop():
        while True:
            _time.sleep(86400)
            cleanup_old_data()
    _threading.Thread(target=_loop, daemon=True).start()

def schedule_zombie_game_cleanup():
    """Nettoie automatiquement les parties actives depuis plus de 2h (parties zombies)."""
    def _loop():
        while True:
            _time.sleep(300)
            try:
                if current_game.get('active') and current_game.get('started_at'):
                    started = datetime.fromisoformat(current_game['started_at'])
                    if now_local() - started > timedelta(hours=2):
                        logger.warning("Partie zombie detectee (>2h) — nettoyage automatique")
                        _reset_game_state()
                        socketio.emit('game_stopped', {'reason': 'timeout'}, namespace='/')
            except Exception as e:
                logger.error(f"Erreur zombie cleanup: {e}")
    _threading.Thread(target=_loop, daemon=True).start()

# ── Helpers etat de jeu ───────────────────────────────────────

def _reset_game_state():
    """Reinitialise l'etat global d'une partie."""
    global current_game, rematch_votes, servo_commands, rematch_pending, pending_rematch_replacements
    current_game = {
        "team1_score": 0, "team2_score": 0,
        "team1_players": [], "team2_players": [],
        "active": False, "started_by": None, "reserved_by": None,
        "started_at": None
    }
    rematch_votes = {"team1": [], "team2": []}
    rematch_pending = False
    pending_rematch_replacements.clear()
    servo_commands["servo1"].append("close")
    servo_commands["servo2"].append("close")

def _launch_rematch(game):
    """Lance un rematch. Centralise le code de relance."""
    global current_game, rematch_votes, rematch_no_votes, servo_commands, rematch_pending, pending_rematch_replacements
    rematch_no_votes.clear()
    current_game = {
        "team1_score": 0, "team2_score": 0,
        "team1_players": game['team1_players'],
        "team2_players": game['team2_players'],
        "active": True,
        "started_by": game.get('started_by'),
        "reserved_by": game.get('reserved_by'),
        "started_at": now_local().isoformat()
    }
    rematch_votes = {"team1": [], "team2": []}
    rematch_pending = False
    pending_rematch_replacements.clear()
    servo_commands["servo1"].append("open")
    servo_commands["servo2"].append("open")
    socketio.emit('game_started', current_game, namespace='/')
    socketio.emit('servo1_unlock', {}, namespace='/')
    socketio.emit('servo2_unlock', {}, namespace='/')

# ── Roles ─────────────────────────────────────────────────────

# Cache roles pour eviter des requetes DB a chaque appel socket
_role_cache = {}

def _get_user_role(username):
    """Retourne le role depuis la DB avec cache memoire (0=user, 1=super_admin, 2=admin)."""
    if not username:
        return 0
    if username in _role_cache:
        return _role_cache[username]
    # Fallback hardcodé pour compatibilité (écrasé si en DB)
    hardcoded = {"Imran": 1, "Apoutou": 2, "Hamara": 2, "MDA": 2}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        q = "SELECT role FROM users WHERE username = %s" if USE_POSTGRES else "SELECT role FROM users WHERE username = ?"
        cur.execute(q, (username,))
        row = row_to_dict(cur.fetchone())
        cur.close(); conn.close()
        if row is not None and row.get('role') is not None:
            role = int(row['role'])
        else:
            role = hardcoded.get(username, 0)
    except Exception:
        role = hardcoded.get(username, 0)
    _role_cache[username] = role
    return role

def invalidate_role_cache(username=None):
    if username:
        _role_cache.pop(username, None)
    else:
        _role_cache.clear()

def is_super_admin(username):
    """Classe 1 — role=1. Acces illimite."""
    return _get_user_role(username) == 1

def is_admin(username):
    """Classe 2 — role >= 1 (inclut super admin)."""
    return _get_user_role(username) >= 1

def is_guest_player(username):
    return username in ["Joueur1", "Joueur2", "Joueur3"]

# ── Decorateurs utilitaires ───────────────────────────────────

def handle_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        except Exception as e:
            logger.error(f"Erreur {f.__name__}: {e}\n{traceback.format_exc()}")
            return jsonify({"success": False, "message": "Erreur interne du serveur"}), 500
    return decorated

def validate_username(u):
    if not u or not isinstance(u, str):
        raise ValueError("Nom d'utilisateur requis")
    u = u.strip()
    if len(u) < 3:
        raise ValueError("Minimum 3 caracteres")
    if len(u) > 20:
        raise ValueError("Maximum 20 caracteres")
    # Regex strict ASCII uniquement — bloque les homoglyphes Unicode (ex: а cyrillique ≠ a latin)
    if not _re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,19}$', u) and not _re.match(r'^[a-zA-Z0-9]{1,20}$', u):
        raise ValueError("Lettres ASCII, chiffres, - et _ uniquement")
    # Double vérification : aucun caractère non-ASCII
    try:
        u.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError("Caracteres non-ASCII interdits")
    if not _re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', u):
        raise ValueError("Lettres ASCII, chiffres, - et _ uniquement")
    return u

def validate_password(p):
    if not p or not isinstance(p, str):
        raise ValueError("Mot de passe requis")
    if len(p) < 6:
        raise ValueError("Minimum 6 caracteres")
    return p

# ── Reservation active ────────────────────────────────────────

def has_active_reservation(username):
    """Verifie si l'utilisateur a une reservation active en ce moment via start_time/end_time."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        now_iso = now_local().isoformat()
        if USE_POSTGRES:
            cur.execute(
                "SELECT id FROM reservations WHERE reserved_by = %s AND start_time <= %s AND end_time >= %s LIMIT 1",
                (username, now_iso, now_iso)
            )
        else:
            cur.execute(
                "SELECT id FROM reservations WHERE reserved_by = ? AND start_time <= ? AND end_time >= ? LIMIT 1",
                (username, now_iso, now_iso)
            )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Erreur has_active_reservation: {e}")
        return False

# ── Initialisation au demarrage ───────────────────────────────

try:
    init_database()
    migrate_reservations_v2()
    migrate_elo_v2()
    migrate_cosmetics_v1()
    migrate_badges_v1()
    migrate_teams_to_text()
    seed_accounts()
    seed_quests()
    schedule_cleanup()
    schedule_zombie_game_cleanup()
    logger.info("Systeme initialise")
except Exception as e:
    logger.error(f"Erreur init DB: {e}")

# ── Pages ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("dashboard.html")

@app.route("/reservation")
def reservation():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("reservation.html")

@app.route("/lobby")
def lobby_page():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("lobby.html")

@app.route("/admin")
def admin_page():
    if "username" not in session:
        return redirect(url_for('login_page'))
    if not is_admin(session.get('username')):
        return redirect(url_for('index'))
    return render_template("admin.html")

@app.route("/live-score")
def live_score():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("live-score.html")

@app.route("/stats")
def stats():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("stats.html")

@app.route("/top")
def top():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("top.html")

@app.route("/scores")
def scores():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("scores.html")

# ── Health ────────────────────────────────────────────────────

@app.route("/health")
def health_check():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected", "timestamp": now_local().isoformat()}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route("/debug/static")
def debug_static():
    username = session.get('username')
    if not is_admin(username):
        return jsonify({"error": "Admin requis"}), 403
    static_path = os.path.join(app.root_path, 'static')
    files_info = {
        "static_folder": app.static_folder,
        "static_url_path": app.static_url_path,
        "static_path_exists": os.path.exists(static_path),
        "root_path": app.root_path
    }
    if os.path.exists(static_path):
        files_info["static_files"] = os.listdir(static_path)
    return jsonify(files_info), 200

@app.route("/debug/live")
def debug_live():
    """Page de diagnostic live-score — supprimée en production."""
    return jsonify({"error": "Page de debug supprimée. Utilisez /debug/game pour l'état du jeu."}), 404

@app.route("/debug/game")
def debug_game():
    username = session.get('username')
    if not is_admin(username):
        return jsonify({"error": "Admin requis"}), 403
    return jsonify({
        "current_game": current_game,
        "active_lobby": active_lobby,
        "rematch_votes": rematch_votes,
        "servo_commands": servo_commands,
    })

# ── Auth ──────────────────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
@handle_errors
def api_register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Aucune donnee"}), 400
    username = validate_username(data.get("username", ""))
    password = validate_password(data.get("password", ""))
    conn = get_db_connection()
    cur = conn.cursor()
    q = "SELECT username FROM users WHERE username = %s" if USE_POSTGRES else "SELECT username FROM users WHERE username = ?"
    cur.execute(q, (username,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Nom d'utilisateur deja pris"}), 409
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    q2 = (
        "INSERT INTO users (username, password) VALUES (%s, %s)"
        if USE_POSTGRES else
        "INSERT INTO users (username, password) VALUES (?, ?)"
    )
    cur.execute(q2, (username, hashed))
    conn.commit()
    cur.close()
    conn.close()
    session.permanent = True
    session['username'] = username
    return jsonify({"success": True, "is_admin": is_admin(username)})

@app.route("/api/login", methods=["POST"])
@handle_errors
def api_login():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if check_rate_limit(client_ip):
        return jsonify({"success": False, "message": "Trop de tentatives, attendez 1 minute"}), 429
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Aucune donnee"}), 400
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or len(username) > 50 or not password:
        return jsonify({"success": False, "message": "Identifiants invalides"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    q = "SELECT * FROM users WHERE username = %s" if USE_POSTGRES else "SELECT * FROM users WHERE username = ?"
    cur.execute(q, (username,))
    user = row_to_dict(cur.fetchone())
    cur.close()
    conn.close()
    if not user:
        return jsonify({"success": False, "message": "Utilisateur inconnu"}), 401
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"success": False, "message": "Mot de passe incorrect"}), 401
    session.permanent = True
    session['username'] = username
    return jsonify({"success": True, "is_admin": is_admin(username)})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/current_user")
def current_user():
    username = session.get('username')
    if not username:
        return jsonify(None), 401
    admin_class = 1 if is_super_admin(username) else (2 if is_admin(username) else 0)
    # Charger les infos profil pour affichage global (nav avatar, surnom)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        q = ("SELECT nickname, avatar_preset, avatar_url, active_theme, active_frame FROM users WHERE username = %s"
             if USE_POSTGRES else
             "SELECT nickname, avatar_preset, avatar_url, active_theme, active_frame FROM users WHERE username = ?")
        cur.execute(q, (username,))
        prof = row_to_dict(cur.fetchone()) or {}
        cur.close(); conn.close()
    except Exception:
        prof = {}
    avatar_url_raw = prof.get("avatar_url") or ""
    return jsonify({
        "username": username,
        "nickname": prof.get("nickname") or "",
        "avatar_preset": prof.get("avatar_preset") or "",
        "avatar_url": "",  # Ne pas envoyer la base64 — trop lourd, utiliser /api/avatar/<username>
        "has_avatar": bool(avatar_url_raw),  # Flag cohérent avec /users_list
        "active_theme": prof.get("active_theme") or "default",
        "active_frame": prof.get("active_frame") or "none",
        "is_admin": is_admin(username),
        "is_super_admin": is_super_admin(username),
        "admin_class": admin_class,
        "has_reservation": has_active_reservation(username),
    })

@app.route("/api/is_admin")
def api_is_admin():
    username = session.get('username')
    if not username:
        return jsonify({"is_admin": False, "is_super_admin": False, "admin_class": 0})
    return jsonify({
        "is_admin": is_admin(username),
        "is_super_admin": is_super_admin(username),
        "admin_class": 1 if is_super_admin(username) else (2 if is_admin(username) else 0),
    })

# ── Data ──────────────────────────────────────────────────────

@app.route("/reservations_all")
@handle_errors
def reservations_all():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT day, time, mode, reserved_by FROM reservations")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = {}
    for row in rows:
        r = row_to_dict(row)
        day = r['day']
        time_val = r['time']
        if day not in result:
            result[day] = {}
        result[day][time_val] = {
            'reserved_by': r['reserved_by'],
            'mode': r.get('mode', '1v1')
        }
    return jsonify(result)

@app.route("/leaderboard")
@handle_errors
def leaderboard():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("""
                SELECT u.username, u.nickname, u.avatar_preset, u.avatar_url,
                       COALESCE(u.active_frame, 'none') as active_frame,
                       COALESCE(u.active_theme, 'default') as active_theme,
                       u.total_goals, u.total_games, u.elo,
                       COALESCE(u.winstreak, 0) as winstreak,
                       COALESCE(u.total_wins, 0) as wins
                FROM users u
                WHERE u.username NOT IN ('Joueur1', 'Joueur2', 'Joueur3')
                ORDER BY u.elo DESC
            """)
        else:
            cur.execute("""
                SELECT username, nickname, avatar_preset, avatar_url,
                       COALESCE(active_frame, 'none') as active_frame,
                       COALESCE(active_theme, 'default') as active_theme,
                       total_goals, total_games, elo,
                       COALESCE(winstreak, 0) as winstreak,
                       COALESCE(total_wins, 0) as wins
                FROM users
                WHERE username NOT IN ('Joueur1', 'Joueur2', 'Joueur3')
                ORDER BY elo DESC
            """)
        rows = [row_to_dict(r) for r in cur.fetchall()]

        # Charger les badges pour chaque joueur en une seule requête
        if rows:
            usernames = [r["username"] for r in rows]
            if USE_POSTGRES:
                placeholders = ",".join(["%s"] * len(usernames))
                cur.execute(f"""
                    SELECT ub.username, b.id, b.name, b.icon, b.color, b.image_url
                    FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
                    WHERE ub.username IN ({placeholders})
                    ORDER BY ub.awarded_at DESC
                """, usernames)
            else:
                placeholders = ",".join(["?"] * len(usernames))
                cur.execute(f"""
                    SELECT ub.username, b.id, b.name, b.icon, b.color, b.image_url
                    FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
                    WHERE ub.username IN ({placeholders})
                    ORDER BY ub.awarded_at DESC
                """, usernames)
            badge_rows = [row_to_dict(r) for r in cur.fetchall()]
            # Indexer par username
            badges_by_user = {}
            for br in badge_rows:
                u = br["username"]
                badges_by_user.setdefault(u, []).append({
                    "id": br["id"], "name": br["name"],
                    "icon": br["icon"], "color": br["color"],
                    "image_url": br.get("image_url") or ""
                })
            for row in rows:
                row["badges"] = badges_by_user.get(row["username"], [])
        else:
            for row in rows:
                row["badges"] = []
        for row in rows:
            avatar_raw = row.get("avatar_url") or ""
            row["has_avatar"] = bool(avatar_raw)
            # Eviter d'envoyer une éventuelle base64 volumineuse dans le classement.
            row["avatar_url"] = ""
            row["active_frame"] = row.get("active_frame") or "none"
            row["active_theme"] = row.get("active_theme") or "default"
    finally:
        cur.close()
        conn.close()
    return jsonify(rows)

@app.route("/user_stats/<username>")
@handle_errors
def user_stats(username):
    # Bloquer l'accès aux stats des comptes invités physiques
    if is_guest_player(username):
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cur = conn.cursor()
    q = "SELECT * FROM users WHERE username = %s" if USE_POSTGRES else "SELECT * FROM users WHERE username = ?"
    cur.execute(q, (username,))
    user = row_to_dict(cur.fetchone())
    if not user:
        cur.close()
        conn.close()
        accept_header = request.headers.get('Accept', '')
        if accept_header.startswith('text/html') or accept_header.startswith('application/xhtml'):
            return redirect(url_for('admin_page'))
        return jsonify(None), 404
    q2 = (
        "SELECT score, date FROM scores WHERE username = %s ORDER BY date DESC LIMIT 20"
        if USE_POSTGRES else
        "SELECT score, date FROM scores WHERE username = ? ORDER BY date DESC LIMIT 20"
    )
    cur.execute(q2, (username,))
    scores_rows = [row_to_dict(r) for r in cur.fetchall()]

    # Calculer buts marqués et buts pris
    goals_scored = 0
    goals_conceded = 0
    if USE_POSTGRES:
        # Calcul 100% SQL — pas de full-scan Python, quel que soit le nombre de matchs
        cur.execute("""
            SELECT
              COALESCE(SUM(CASE WHEN p.team = 'team1' THEN g.team1_score ELSE g.team2_score END), 0) AS scored,
              COALESCE(SUM(CASE WHEN p.team = 'team1' THEN g.team2_score ELSE g.team1_score END), 0) AS conceded
            FROM games g
            JOIN LATERAL (
              SELECT 'team1' AS team
              FROM json_array_elements_text(g.team1_players::json) AS pl(username)
              WHERE pl.username = %s
              UNION ALL
              SELECT 'team2' AS team
              FROM json_array_elements_text(g.team2_players::json) AS pl(username)
              WHERE pl.username = %s
            ) p ON true
        """, (username, username))
        row = row_to_dict(cur.fetchone())
        if row:
            goals_scored   = int(row.get('scored')   or 0)
            goals_conceded = int(row.get('conceded')  or 0)
    else:
        # SQLite : itération Python limitée aux 500 derniers matchs
        cur.execute("SELECT team1_players, team2_players, team1_score, team2_score FROM games ORDER BY id DESC LIMIT 500")
        for grow in cur.fetchall():
            gr = row_to_dict(grow)
            t1p = gr.get('team1_players', '[]')
            t2p = gr.get('team2_players', '[]')
            if isinstance(t1p, str):
                try: t1p = json.loads(t1p)
                except (json.JSONDecodeError, ValueError): t1p = []
            if isinstance(t2p, str):
                try: t2p = json.loads(t2p)
                except (json.JSONDecodeError, ValueError): t2p = []
            if username in t1p:
                goals_scored   += int(gr.get('team1_score') or 0)
                goals_conceded += int(gr.get('team2_score') or 0)
            elif username in t2p:
                goals_scored   += int(gr.get('team2_score') or 0)
                goals_conceded += int(gr.get('team1_score') or 0)

    cur.close()
    conn.close()
    total_games = user.get('total_games', 0)
    total_goals = user.get('total_goals', 0)
    stats_data = {
        "username": user['username'],
        "total_games": total_games,
        "total_goals": total_goals,
        "goals_scored": goals_scored,
        "goals_conceded": goals_conceded,
        "ratio": round(total_goals / total_games, 2) if total_games > 0 else 0,
        "best_score": max([s['score'] for s in scores_rows], default=0),
        "average_score": round(sum([s['score'] for s in scores_rows]) / len(scores_rows), 2) if scores_rows else 0,
        "recent_scores": scores_rows,
    }
    accept_header = request.headers.get('Accept', '')
    is_browser_nav = accept_header.startswith('text/html') or accept_header.startswith('application/xhtml')
    if is_browser_nav:
        current_u = session.get('username')
        # Admin peut voir n'importe qui, un joueur peut voir ses propres stats
        if is_admin(current_u) or current_u == username:
            return render_template('stats.html', user_stats=stats_data, target_username=username)
        else:
            return redirect(url_for('dashboard'))
    return jsonify(stats_data)

@app.route("/scores_all")
@handle_errors
def scores_all():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM games")
    count_row = cur.fetchone()
    total = (count_row[0] if isinstance(count_row, tuple) else list(count_row.values())[0]) if count_row else 0
    cur.execute("SELECT * FROM games ORDER BY date DESC LIMIT 100")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = []
    for row in rows:
        r = row_to_dict(row)
        t1 = r.get('team1_players', '[]')
        t2 = r.get('team2_players', '[]')
        if isinstance(t1, str):
            try:
                t1 = json.loads(t1)
            except Exception:
                t1 = [t1]
        if isinstance(t2, str):
            try:
                t2 = json.loads(t2)
            except Exception:
                t2 = [t2]
        r['team1_players'] = t1
        r['team2_players'] = t2
        if 'date' in r and hasattr(r['date'], 'isoformat'):
            r['date'] = r['date'].isoformat()
        elif 'date' not in r or r['date'] is None:
            r['date'] = ''
        result.append(r)
    return jsonify({"games": result, "total": total})

@app.route("/admin/reset_database", methods=["POST"])
def admin_reset_database():
    username = session.get('username')
    if not is_super_admin(username):
        return jsonify({"success": False, "message": "Reserve a l'administrateur principal (classe 1)"}), 403
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM scores")
        cur.execute("DELETE FROM reservations")
        cur.execute("DELETE FROM games")
        cur.execute("DELETE FROM users")
        conn.commit()
        cur.close()
        conn.close()
        seed_accounts()
        return jsonify({"success": True, "message": "Base de donnees reinitialisee"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/delete_user', methods=['POST'])
@handle_errors
def delete_user():
    admin_username = session.get('username')
    if not is_super_admin(admin_username):
        return jsonify({"success": False, "message": "Reserve a l'administrateur principal (classe 1)"}), 403
    data = request.get_json()
    username_to_delete = data.get('username')
    if not username_to_delete:
        return jsonify({"success": False, "message": "Nom d'utilisateur requis"}), 400
    if username_to_delete == admin_username:
        return jsonify({"success": False, "message": "Vous ne pouvez pas vous supprimer vous-meme"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    q_check = "SELECT username FROM users WHERE username = %s" if USE_POSTGRES else "SELECT username FROM users WHERE username = ?"
    cur.execute(q_check, (username_to_delete,))
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Utilisateur introuvable"}), 404
    # Supprimer reservations d'abord (scores supprimés par CASCADE)
    q_res = "DELETE FROM reservations WHERE reserved_by = %s" if USE_POSTGRES else "DELETE FROM reservations WHERE reserved_by = ?"
    cur.execute(q_res, (username_to_delete,))
    q_delete = "DELETE FROM users WHERE username = %s" if USE_POSTGRES else "DELETE FROM users WHERE username = ?"
    cur.execute(q_delete, (username_to_delete,))
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Admin {admin_username} a supprime le compte {username_to_delete}")
    invalidate_role_cache(username_to_delete)
    return jsonify({"success": True, "message": f"Compte '{username_to_delete}' supprime avec succes"})

@app.route('/api/set_user_role', methods=['POST'])
@handle_errors
def set_user_role():
    """Permet au super admin de changer le rôle d'un utilisateur."""
    admin_username = session.get('username')
    if not is_super_admin(admin_username):
        return jsonify({"success": False, "message": "Réservé au super admin"}), 403
    data = request.get_json()
    target = data.get('username')
    role = data.get('role')
    if not target or role not in [0, 1, 2]:
        return jsonify({"success": False, "message": "Paramètres invalides (role: 0=user, 1=super_admin, 2=admin)"}), 400
    if target == admin_username:
        return jsonify({"success": False, "message": "Vous ne pouvez pas changer votre propre rôle"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    q = "UPDATE users SET role = %s WHERE username = %s" if USE_POSTGRES else "UPDATE users SET role = ? WHERE username = ?"
    cur.execute(q, (role, target))
    if cur.rowcount == 0:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Utilisateur introuvable"}), 404
    conn.commit(); cur.close(); conn.close()
    invalidate_role_cache(target)
    logger.info(f"{admin_username} a changé le rôle de {target} → {role}")
    return jsonify({"success": True, "message": f"Rôle de {target} mis à jour"})

# ── Reservations ──────────────────────────────────────────────

@app.route("/save_reservation", methods=["POST"])
@handle_errors
def save_reservation():
    """Ancien endpoint de reservation par jour/heure (conserve pour compatibilite)."""
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Donnees manquantes"}), 400
    day = data.get("day")
    time_val = data.get("time")
    team1 = data.get("team1", [])
    team2 = data.get("team2", [])
    mode = data.get("mode", "1v1")
    reserved_by = session.get("username", "unknown")
    if not day or not time_val:
        return jsonify({"success": False, "message": "Jour et heure requis"}), 400

    # Valider que le jour est aujourd'hui ou demain seulement
    days_map = {
        'Lundi': 0, 'Mardi': 1, 'Mercredi': 2, 'Jeudi': 3,
        'Vendredi': 4, 'Samedi': 5, 'Dimanche': 6
    }
    today_wd = now_local().weekday()
    tomorrow_wd = (today_wd + 1) % 7
    target_wd = days_map.get(day)
    if target_wd is None or target_wd not in [today_wd, tomorrow_wd]:
        return jsonify({"success": False, "message": "Reservation limitee a aujourd'hui et demain"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if not is_admin(reserved_by):
            q_count = "SELECT COUNT(*) as cnt FROM reservations WHERE reserved_by = %s" if USE_POSTGRES else "SELECT COUNT(*) as cnt FROM reservations WHERE reserved_by = ?"
            cur.execute(q_count, (reserved_by,))
            count_row = row_to_dict(cur.fetchone())
            user_total = int(count_row.get('cnt') or count_row.get('count') or 0)
            q_existing_mine = (
                "SELECT id FROM reservations WHERE day = %s AND time = %s AND reserved_by = %s"
                if USE_POSTGRES else
                "SELECT id FROM reservations WHERE day = ? AND time = ? AND reserved_by = ?"
            )
            cur.execute(q_existing_mine, (day, time_val, reserved_by))
            is_update = cur.fetchone() is not None
            if not is_update and user_total >= 3:
                return jsonify({"success": False, "message": "Maximum 3 reservations par joueur"}), 400
        q_check = (
            "SELECT reserved_by FROM reservations WHERE day = %s AND time = %s"
            if USE_POSTGRES else
            "SELECT reserved_by FROM reservations WHERE day = ? AND time = ?"
        )
        cur.execute(q_check, (day, time_val))
        existing = cur.fetchone()
        if existing:
            existing_dict = row_to_dict(existing)
            if existing_dict['reserved_by'] != reserved_by and not is_admin(reserved_by):
                return jsonify({"success": False, "message": f"Ce creneau est deja reserve par {existing_dict['reserved_by']}"}), 409
        if USE_POSTGRES:
            cur.execute("DELETE FROM reservations WHERE day = %s AND time = %s", (day, time_val))
        else:
            cur.execute("DELETE FROM reservations WHERE day = ? AND time = ?", (day, time_val))

        # Calculer start_time / end_time
        start_iso_val = None
        end_iso_val = None
        try:
            match = _re.search(r'(\d{1,2}):(\d{2})', time_val)
            if match:
                h, m = int(match.group(1)), int(match.group(2))
                base = now_local()
                diff = (target_wd - base.weekday()) % 7
                base = base + timedelta(days=diff)
                start_dt = base.replace(hour=h, minute=m, second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=15)
                start_iso_val = start_dt.isoformat()
                end_iso_val = end_dt.isoformat()
        except Exception:
            pass

        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO reservations (day, time, team1, team2, mode, reserved_by, start_time, end_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (day, time_val, json.dumps(team1), json.dumps(team2), mode, reserved_by, start_iso_val, end_iso_val)
            )
        else:
            cur.execute(
                "INSERT INTO reservations (day, time, team1, team2, mode, reserved_by, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (day, time_val, json.dumps(team1), json.dumps(team2), mode, reserved_by, start_iso_val, end_iso_val)
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return jsonify({"success": True})

@app.route("/cancel_reservation", methods=["POST"])
@handle_errors
def cancel_reservation():
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True)
    day = data.get("day")
    time_val = data.get("time")
    username = session.get("username")
    conn = get_db_connection()
    cur = conn.cursor()
    if is_admin(username):
        q = "DELETE FROM reservations WHERE day = %s AND time = %s" if USE_POSTGRES else "DELETE FROM reservations WHERE day = ? AND time = ?"
        cur.execute(q, (day, time_val))
    else:
        q = (
            "DELETE FROM reservations WHERE day = %s AND time = %s AND reserved_by = %s"
            if USE_POSTGRES else
            "DELETE FROM reservations WHERE day = ? AND time = ? AND reserved_by = ?"
        )
        cur.execute(q, (day, time_val, username))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": bool(deleted)})

@app.route("/api/cancel_reservation_v2", methods=["POST"])
@handle_errors
def cancel_reservation_v2():
    """Annuler une reservation par son id."""
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True) or {}
    res_id = data.get("id")
    username = session["username"]
    if not res_id:
        return jsonify({"success": False, "message": "ID requis"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    if is_admin(username):
        q = "DELETE FROM reservations WHERE id = %s" if USE_POSTGRES else "DELETE FROM reservations WHERE id = ?"
        cur.execute(q, (res_id,))
    else:
        q = (
            "DELETE FROM reservations WHERE id = %s AND reserved_by = %s"
            if USE_POSTGRES else
            "DELETE FROM reservations WHERE id = ? AND reserved_by = ?"
        )
        cur.execute(q, (res_id, username))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": bool(deleted)})

@app.route("/api/reserve_and_lobby", methods=["POST"])
@handle_errors
def reserve_and_lobby():
    """Reserver maintenant et creer le lobby avec l'utilisateur comme hote."""
    global active_lobby
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True) or {}
    try:
        duration = int(data.get("duration", 15))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Duree invalide"}), 400
    mode = data.get("mode", "1v1")
    username = session["username"]
    if duration not in [5, 10, 15]:
        return jsonify({"success": False, "message": "Duree invalide (5, 10 ou 15 min)"}), 400
    now = now_local()
    start_time = now
    end_time = now + timedelta(minutes=duration)
    result = _do_reservation(username, start_time, end_time, duration, mode)
    result_data = result.get_json() if hasattr(result, 'get_json') else {}
    if result_data and result_data.get("success"):
        # Bloquer si une partie est en cours (sauf super admin)
        if current_game.get('active') and not is_super_admin(username):
            return jsonify({"success": False, "message": "Une partie est en cours — impossible de créer un lobby"}), 400
        # Creer le lobby avec l'utilisateur comme hote
        with _lobby_lock:
            if active_lobby.get('active'):
                socketio.emit('lobby_cancelled', {}, namespace='/')
            active_lobby = {
                "host": username, "invited": [],
                "accepted": [username], "declined": [],
                "team1": [username], "team2": [],
                "active": True, "join_requests": {}
            }
        socketio.emit('lobby_created', {'host': username, 'invited': []}, namespace='/')
        return jsonify({"success": True, "redirect": "/lobby"})
    return result

@app.route("/api/reserve_now", methods=["POST"])
@handle_errors
def reserve_now():
    """Reserver maintenant pour X minutes (5, 10 ou 15)."""
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True) or {}
    try:
        duration = int(data.get("duration", 15))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Duree invalide"}), 400
    mode = data.get("mode", "1v1")
    username = session["username"]
    if duration not in [5, 10, 15]:
        return jsonify({"success": False, "message": "Duree invalide (5, 10 ou 15 min)"}), 400
    now = now_local()
    start_time = now
    end_time = now + timedelta(minutes=duration)
    return _do_reservation(username, start_time, end_time, duration, mode)

@app.route("/api/reserve_plan", methods=["POST"])
@handle_errors
def reserve_plan():
    """Planifier une reservation a une heure precise (aujourd'hui ou demain uniquement)."""
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True) or {}
    start_str = data.get("start_time")
    try:
        duration = int(data.get("duration", 15))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Duree invalide"}), 400
    mode = data.get("mode", "1v1")
    username = session["username"]
    if duration not in [5, 10, 15]:
        return jsonify({"success": False, "message": "Duree invalide (5, 10 ou 15 min)"}), 400
    if not start_str:
        return jsonify({"success": False, "message": "Heure de debut requise"}), 400
    try:
        if 'T' in start_str:
            start_time = datetime.fromisoformat(start_str)
        else:
            date_str = data.get("date", now_local().date().isoformat())
            start_time = datetime.fromisoformat(f"{date_str}T{start_str}:00")
    except Exception:
        return jsonify({"success": False, "message": "Format d'heure invalide"}), 400
    now = now_local()
    # Refuser les reservations dans le passe (sauf admin)
    if not is_admin(username) and start_time < now - timedelta(minutes=1):
        return jsonify({"success": False, "message": "Impossible de reserver dans le passe"}), 400
    # Refuser si au-dela de demain (uniquement aujourd'hui et demain) — sauf admin
    if not is_admin(username):
        max_date = (now + timedelta(days=2)).date()
        if start_time.date() >= max_date:
            return jsonify({"success": False, "message": "Reservation limitee a aujourd'hui et demain"}), 400
    end_time = start_time + timedelta(minutes=duration)
    return _do_reservation(username, start_time, end_time, duration, mode)

def _do_reservation(username, start_time, end_time, duration, mode):
    with _reservation_lock:
        return _do_reservation_nolock(username, start_time, end_time, duration, mode)

def _do_reservation_nolock(username, start_time, end_time, duration, mode):
    """Logique commune de reservation avec verification anti-chevauchement."""
    now = now_local()
    # Double verification : seulement aujourd'hui et demain (sauf admin)
    if not is_admin(username):
        max_date = (now + timedelta(days=2)).date()
        if start_time.date() >= max_date:
            return jsonify({"success": False, "message": "Reservation limitee a aujourd'hui et demain"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        # Verifier le quota (sauf admin)
        if not is_admin(username):
            if USE_POSTGRES:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM reservations WHERE reserved_by = %s AND end_time > %s",
                    (username, now.isoformat())
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM reservations WHERE reserved_by = ? AND end_time > ?",
                    (username, now.isoformat())
                )
            row = row_to_dict(cur.fetchone()) or {}
            if int(row.get('cnt') or row.get('count') or 0) >= 3:
                return jsonify({"success": False, "message": "Maximum 3 reservations actives"}), 400

        # Verifier le chevauchement
        if USE_POSTGRES:
            cur.execute(
                "SELECT reserved_by FROM reservations WHERE start_time < %s AND end_time > %s",
                (end_iso, start_iso)
            )
        else:
            cur.execute(
                "SELECT reserved_by FROM reservations WHERE start_time < ? AND end_time > ?",
                (end_iso, start_iso)
            )
        conflict = cur.fetchone()
        if conflict:
            c = row_to_dict(conflict)
            if c['reserved_by'] != username and not is_admin(username):
                return jsonify({"success": False, "message": f"Ce creneau chevauche une reservation de {c['reserved_by']}"}), 409

        # Champs compatibilite
        days_fr = {
            'Monday': 'Lundi', 'Tuesday': 'Mardi', 'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi', 'Friday': 'Vendredi', 'Saturday': 'Samedi', 'Sunday': 'Dimanche'
        }
        day_fr = days_fr.get(start_time.strftime('%A'), start_time.strftime('%A'))
        time_str = start_time.strftime('%H:%M')
        end_str = end_time.strftime('%H:%M')
        time_display = f"{time_str} - {end_str}"

        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO reservations (day, time, team1, team2, mode, reserved_by, start_time, end_time, duration_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (start_time, reserved_by) DO NOTHING
            """, (day_fr, time_display, json.dumps([]), json.dumps([]), mode, username, start_iso, end_iso, duration))
        else:
            # Verifier doublon exact
            cur.execute(
                "SELECT id FROM reservations WHERE start_time = ? AND reserved_by = ?",
                (start_iso, username)
            )
            if cur.fetchone():
                return jsonify({"success": False, "message": "Vous avez deja une reservation a cette heure"}), 409
            cur.execute("""
                INSERT INTO reservations (day, time, team1, team2, mode, reserved_by, start_time, end_time, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (day_fr, time_display, json.dumps([]), json.dumps([]), mode, username, start_iso, end_iso, duration))
        conn.commit()
        return jsonify({
            "success": True,
            "start": start_iso,
            "end": end_iso,
            "duration": duration,
            "time_display": time_display
        })
    finally:
        cur.close()
        conn.close()

@app.route("/users_list")
@handle_errors
def users_list():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT username, nickname, avatar_preset, avatar_url, elo, role, active_theme, active_frame FROM users ORDER BY username ASC")
        rows = [row_to_dict(r) for r in cur.fetchall()]

        # Badges de tous les joueurs en une seule requête
        if rows:
            usernames = [r["username"] for r in rows]
            if USE_POSTGRES:
                placeholders = ",".join(["%s"] * len(usernames))
                cur.execute(f"""
                    SELECT ub.username, b.id, b.name, b.icon, b.color, b.image_url
                    FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
                    WHERE ub.username IN ({placeholders})
                    ORDER BY ub.awarded_at DESC
                """, usernames)
            else:
                placeholders = ",".join(["?"] * len(usernames))
                cur.execute(f"""
                    SELECT ub.username, b.id, b.name, b.icon, b.color, b.image_url
                    FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
                    WHERE ub.username IN ({placeholders})
                    ORDER BY ub.awarded_at DESC
                """, usernames)
            badges_by_user = {}
            for br in [row_to_dict(r) for r in cur.fetchall()]:
                badges_by_user.setdefault(br["username"], []).append({
                    "id": br["id"], "name": br["name"],
                    "icon": br["icon"], "color": br["color"],
                    "image_url": br.get("image_url") or ""
                })
        else:
            badges_by_user = {}
    finally:
        cur.close()
        conn.close()
    return jsonify([{
        "username":     r["username"],
        "nickname":     r.get("nickname") or "",
        "avatar_preset": r.get("avatar_preset") or "",
        "avatar_url":   "",   # Ne pas envoyer la base64 — utiliser /api/avatar/<username>
        "has_avatar":   bool(r.get("avatar_url")),
        "active_theme": r.get("active_theme") or "default",
        "active_frame": r.get("active_frame") or "none",
        "elo":          r.get("elo") or 1000,
        "role":         int(r.get("role") or 0),
        "badges":       badges_by_user.get(r["username"], []),
    } for r in rows])

@app.route("/api/current_game")
def api_current_game():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    return jsonify(current_game)

@app.route("/api/has_active_game")
def api_has_active_game():
    username = session.get('username')
    if not username:
        return jsonify({"error": "Non connecte"}), 401
    return jsonify({
        "has_active_game": current_game.get('active', False),
        "game_data": current_game if current_game.get('active') else None,
        "is_admin": is_admin(username),
        "has_reservation": has_active_reservation(username),
    })

@app.route("/api/active_lobby")
def api_active_lobby():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    return jsonify(active_lobby)

@app.route("/api/online_users")
def api_online_users():
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    # Dédupliquer : un user peut avoir plusieurs tabs ouvertes
    online = list(set(connected_users.values()))
    return jsonify({"online": online})

@app.route("/api/public_stats")
@handle_errors
def api_public_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM games")
    row = row_to_dict(cur.fetchone())
    total_games = int(row.get('cnt') or row.get('count') or 0)
    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE total_games > 0")
    row2 = row_to_dict(cur.fetchone())
    active_players = int(row2.get('cnt') or row2.get('count') or 0)
    cur.close()
    conn.close()
    return jsonify({
        "total_games": total_games,
        "active_players": active_players,
        "avg_duration_minutes": 15,
    })

@app.route("/reservations_today")
@handle_errors
def reservations_today():
    if "username" not in session:
        return jsonify([])
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        today = now_local().strftime('%A')
        days_fr = {
            'Monday': 'Lundi', 'Tuesday': 'Mardi', 'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi', 'Friday': 'Vendredi', 'Saturday': 'Samedi', 'Sunday': 'Dimanche'
        }
        day_fr = days_fr.get(today, today)
        tomorrow = (now_local() + timedelta(days=1)).strftime('%A')
        day_fr_tomorrow = days_fr.get(tomorrow, tomorrow)
        if USE_POSTGRES:
            cur.execute(
                "SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes FROM reservations WHERE day = %s ORDER BY time ASC LIMIT 5",
                (day_fr,)
            )
            today_rows = [row_to_dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes FROM reservations WHERE day = %s ORDER BY time ASC LIMIT 5",
                (day_fr_tomorrow,)
            )
            tomorrow_rows = [row_to_dict(r) for r in cur.fetchall()]
        else:
            cur.execute(
                "SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes FROM reservations WHERE day = ? ORDER BY time ASC LIMIT 5",
                (day_fr,)
            )
            today_rows = [row_to_dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes FROM reservations WHERE day = ? ORDER BY time ASC LIMIT 5",
                (day_fr_tomorrow,)
            )
            tomorrow_rows = [row_to_dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
    return jsonify(today_rows + tomorrow_rows)

@app.route("/api/babyfoot_status")
@handle_errors
def babyfoot_status():
    """Retourne l'etat actuel du babyfoot : libre ou occupe + prochaines reservations."""
    if "username" not in session:
        return jsonify({"error": "Non connecte"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        now = now_local()
        today = now.date()
        tomorrow = (now + timedelta(days=1)).date()
        if USE_POSTGRES:
            cur.execute("""
                SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes
                FROM reservations
                WHERE start_time >= %s AND start_time < %s
                ORDER BY start_time ASC
            """, (today.isoformat(), (tomorrow + timedelta(days=1)).isoformat()))
        else:
            cur.execute("""
                SELECT id, day, time, mode, reserved_by, start_time, end_time, duration_minutes
                FROM reservations
                WHERE start_time >= ? AND start_time < ?
                ORDER BY start_time ASC
            """, (today.isoformat(), (tomorrow + timedelta(days=1)).isoformat()))
        rows = [row_to_dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    now_str = now.isoformat()
    current = None
    upcoming = []
    for r in rows:
        # Serialiser les datetime PostgreSQL en string si necessaire
        for field in ('start_time', 'end_time'):
            if r.get(field) and hasattr(r[field], 'isoformat'):
                r[field] = r[field].isoformat()
        st = r.get('start_time', '')
        et = r.get('end_time', '')
        if st and et:
            if st <= now_str <= et:
                current = r
            elif st > now_str:
                upcoming.append(r)

    return jsonify({
        "is_free": current is None,
        "current": current,
        "upcoming": upcoming[:5],
        "all_today": [r for r in rows if str(r.get('start_time', ''))[:10] == today.isoformat()],
        "all_tomorrow": [r for r in rows if str(r.get('start_time', ''))[:10] == tomorrow.isoformat()],
        "server_time": now_str,
    })

# ── ELO helpers ───────────────────────────────────────────────────────────

def _k_factor(elo):
    """K dynamique selon le niveau : progression rapide en bas, précise en haut."""
    if elo < 1050: return 40
    if elo < 1250: return 28
    if elo < 1400: return 20
    return 14

def compute_elo(winner_elo, loser_elo, winner_streak=0, score_w=0, score_l=0):
    """
    Formule ELO dynamique baby-foot v2.
    - K variable selon le rang
    - Bonus winstreak : +15% par victoire consécutive, max ×2.0
    - Bonus upset : battre qqn 200+ ELO au-dessus → ×1.5
    - Bonus domination : gagner 10-0 ou 10-1 → +20%
    - Plancher 800
    """
    k = _k_factor(winner_elo)
    expected_w = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    base_gain = k * (1 - expected_w)
    base_loss = k * (0 - (1 - expected_w))

    # Multiplicateur winstreak (streak actuel avant cette victoire)
    streak_mult = min(1.0 + (winner_streak * 0.15), 2.0)

    # Bonus upset : adversaire 200+ ELO au-dessus
    upset_mult = 1.5 if (loser_elo - winner_elo) >= 200 else 1.0

    # Bonus domination : 10-0 ou 10-1
    dom_mult = 1.2 if score_l <= 1 and score_w == 10 else 1.0

    total_mult = streak_mult * upset_mult * dom_mult
    final_gain = base_gain * total_mult

    new_winner = max(800, round(winner_elo + final_gain))
    new_loser  = max(800, round(loser_elo  + base_loss))

    return new_winner, new_loser, round(final_gain), round(base_loss)

def elo_tier(elo):
    """7 paliers ELO baby-foot."""
    if elo >= 1700: return ("Maître 🏆",    "🏆", 1700, 9999)
    if elo >= 1550: return ("Élite 👑",      "👑", 1550, 1699)
    if elo >= 1400: return ("Expert 💎",     "💎", 1400, 1549)
    if elo >= 1250: return ("Confirmé ⚡",   "⚡", 1250, 1399)
    if elo >= 1100: return ("Rival 🔥",      "🔥", 1100, 1249)
    if elo >= 950:  return ("Amateur 🌱",    "🌱", 950,  1099)
    return              ("Recrue 🎮",    "🎮", 800,  949)

ELO_TIERS_FRONTEND = [
    {"name": "Recrue 🎮",    "icon": "🎮", "min": 800,  "max": 949,  "desc": "Bienvenue sur le terrain ! Chaque but compte."},
    {"name": "Amateur 🌱",   "icon": "🌱", "min": 950,  "max": 1099, "desc": "Tu prends tes marques, la technique arrive."},
    {"name": "Rival 🔥",     "icon": "🔥", "min": 1100, "max": 1249, "desc": "Tu contrôles le jeu et tu gagnes souvent."},
    {"name": "Confirmé ⚡",  "icon": "⚡", "min": 1250, "max": 1399, "desc": "Adversaire redoutable — tout le club le sait."},
    {"name": "Expert 💎",    "icon": "💎", "min": 1400, "max": 1549, "desc": "Top niveau, chaque point est précieux."},
    {"name": "Élite 👑",     "icon": "👑", "min": 1550, "max": 1699, "desc": "Parmi les meilleurs du club, sans discussion."},
    {"name": "Maître 🏆",    "icon": "🏆", "min": 1700, "max": 9999, "desc": "Imbattable. La table t'appartient."},
]

@app.route("/api/avatar/<username>")
def api_avatar(username):
    """Retourne uniquement l'image avatar — évite de surcharger /current_user."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        q = "SELECT avatar_url, avatar_preset FROM users WHERE username = %s" if USE_POSTGRES else "SELECT avatar_url, avatar_preset FROM users WHERE username = ?"
        cur.execute(q, (username,))
        row = row_to_dict(cur.fetchone()) or {}
        cur.close(); conn.close()
    except Exception:
        row = {}
    # Si c'est une data URL base64, servir l'image directement
    avatar_url = row.get("avatar_url") or ""
    if avatar_url.startswith("data:"):
        header, data = avatar_url.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
        img_bytes = _base64.b64decode(data)
        return Response(img_bytes, mimetype=mime, headers={"Cache-Control": "public, max-age=3600"})
    return jsonify({
        "avatar_url": avatar_url,
        "avatar_preset": row.get("avatar_preset") or "",
    })

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    q = "SELECT * FROM users WHERE username = %s" if USE_POSTGRES else "SELECT * FROM users WHERE username = ?"
    cur.execute(q, (username,))
    user = row_to_dict(cur.fetchone())
    if not user:
        cur.close(); conn.close()
        return jsonify({"error": "Introuvable"}), 404
    elo = user.get("elo") or 1000
    tier_name, tier_icon, tier_min, tier_max = elo_tier(elo)
    winstreak  = user.get("winstreak") or 0
    total_wins = user.get("total_wins") or 0
    # Calcul % progression vers le palier suivant
    pct = 0
    if tier_max < 9999:
        pct = round(max(0, min(100, (elo - tier_min) / (tier_max - tier_min + 1) * 100)))
    # Badges du joueur
    if USE_POSTGRES:
        cur.execute("""
            SELECT b.id, b.name, b.description, b.icon, b.color, ub.awarded_at
            FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
            WHERE ub.username = %s ORDER BY ub.awarded_at DESC
        """, (username,))
    else:
        cur.execute("""
            SELECT b.id, b.name, b.description, b.icon, b.color, ub.awarded_at
            FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
            WHERE ub.username = ? ORDER BY ub.awarded_at DESC
        """, (username,))
    badges = [row_to_dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify({
        "username":    user["username"],
        "nickname":    user.get("nickname") or "",
        "bio":         user.get("bio") or "",
        "avatar_preset": user.get("avatar_preset") or "",
        "avatar_url":  user.get("avatar_url") or "",
        "equipped_theme": user.get("active_theme") or "default",
        "equipped_frame": user.get("active_frame") or "none",
        "elo":         elo,
        "elo_tier":    tier_name,
        "elo_icon":    tier_icon,
        "elo_tier_min": tier_min,
        "elo_tier_max": tier_max,
        "elo_pct":     pct,
        "winstreak":   winstreak,
        "total_wins":  total_wins,
        "badges":      badges,
        "elo_tiers":   ELO_TIERS_FRONTEND,
    })

@app.route("/api/profile", methods=["POST"])
def api_update_profile():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    data = request.get_json()
    nickname = _html.escape((data.get("nickname") or "").strip())[:50]
    bio = _html.escape((data.get("bio") or "").strip())[:120]
    raw_preset = (data.get("avatar_preset") or "").strip()
    avatar_preset = (raw_preset if '<' not in raw_preset and '>' not in raw_preset else "")[:10]
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("UPDATE users SET nickname=%s, bio=%s, avatar_preset=%s WHERE username=%s",
                    (nickname or None, bio or None, avatar_preset or None, username))
    else:
        cur.execute("UPDATE users SET nickname=?, bio=?, avatar_preset=? WHERE username=?",
                    (nickname or None, bio or None, avatar_preset or None, username))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": "Profil mis à jour"})

@app.route("/api/upload_avatar", methods=["POST"])
def api_upload_avatar():
    """
    Upload d'avatar.
    - Si CLOUDINARY_URL est défini dans Render : upload vers Cloudinary (recommandé).
    - Sinon : fallback base64 en DB PostgreSQL, limité à 700 Ko.
    """
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    data = request.get_json(silent=True) or {}
    img_data = data.get("image", "")

    # Accepter uniquement les formats image bitmap sûrs (pas SVG — peut contenir du JS)
    ALLOWED_IMAGE_TYPES = ("data:image/jpeg", "data:image/jpg", "data:image/png",
                           "data:image/webp", "data:image/gif", "data:image/heic",
                           "data:image/heif", "data:application/octet-stream")
    if not any(img_data.startswith(t) for t in ALLOWED_IMAGE_TYPES):
        return jsonify({"error": "Format d'image invalide (JPEG, PNG, WebP, GIF uniquement)"}), 400
    # Bloquer explicitement SVG (peut contenir du JavaScript → XSS)
    if "svg" in img_data[:50].lower():
        return jsonify({"error": "Format SVG non autorisé"}), 400

    # Normaliser le type MIME : forcer jpeg pour octet-stream et heic
    if "heic" in img_data or "heif" in img_data or img_data.startswith("data:application/"):
        try:
            b64_part = img_data.split(",", 1)[1]
            img_data = f"data:image/jpeg;base64,{b64_part}"
        except Exception:
            pass

    # Vérifier que le b64 est valide
    try:
        b64_part = img_data.split(",", 1)[1]
        _base64.b64decode(b64_part)
    except Exception:
        return jsonify({"error": "Données image corrompues"}), 400

    if USE_CLOUDINARY:
        # ── Upload Cloudinary : stockage externe, pas de limite DB ──
        try:
            import cloudinary.uploader as _uploader
            result = _uploader.upload(
                img_data,
                folder="babyfoot_avatars",
                public_id=f"avatar_{username}",
                overwrite=True,
                transformation=[
                    {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                    {"quality": "auto", "fetch_format": "auto"}
                ]
            )
            avatar_url = result.get("secure_url", "")
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                if USE_POSTGRES:
                    cur.execute("UPDATE users SET avatar_url=%s, avatar_preset=NULL WHERE username=%s", (avatar_url, username))
                else:
                    cur.execute("UPDATE users SET avatar_url=?, avatar_preset=NULL WHERE username=?", (avatar_url, username))
                conn.commit()
            finally:
                cur.close()
                conn.close()
            return jsonify({"success": True, "avatar_url": avatar_url})
        except Exception as e:
            logger.error(f"Erreur Cloudinary upload: {e}")
            return jsonify({"error": "Erreur lors de l'upload — réessayez"}), 500
    else:
        # ── Fallback base64 en DB (max ~500 Ko image réelle) ──
        MAX_LEN = 700_000
        if len(img_data) > MAX_LEN:
            return jsonify({"error": "Image trop grande. Configurez CLOUDINARY_URL dans Render → Environment pour lever cette limite."}), 413
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            if USE_POSTGRES:
                cur.execute("UPDATE users SET avatar_url=%s, avatar_preset=NULL WHERE username=%s", (img_data, username))
            else:
                cur.execute("UPDATE users SET avatar_url=?, avatar_preset=NULL WHERE username=?", (img_data, username))
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return jsonify({"success": True, "avatar_url": img_data})

@app.route("/settings")
def settings_page():
    if "username" not in session:
        return redirect(url_for('login_page'))
    return render_template("settings.html")

@app.route("/api/change_password", methods=["POST"])
@handle_errors
def api_change_password():
    if "username" not in session:
        return jsonify({"success": False, "message": "Non authentifie"}), 401
    data = request.get_json(silent=True) or {}
    username = session["username"]
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    if not current_pw or not new_pw:
        return jsonify({"success": False, "message": "Champs requis"}), 400
    try:
        new_pw = validate_password(new_pw)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    q = "SELECT password FROM users WHERE username = %s" if USE_POSTGRES else "SELECT password FROM users WHERE username = ?"
    cur.execute(q, (username,))
    row = row_to_dict(cur.fetchone())
    if not row:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Utilisateur introuvable"}), 404
    if not bcrypt.checkpw(current_pw.encode(), row["password"].encode()):
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Mot de passe actuel incorrect"}), 401
    hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    q2 = "UPDATE users SET password = %s WHERE username = %s" if USE_POSTGRES else "UPDATE users SET password = ? WHERE username = ?"
    cur.execute(q2, (hashed, username))
    conn.commit()
    cur.close(); conn.close()
    logger.info(f"Mot de passe change pour {username}")
    return jsonify({"success": True, "message": "Mot de passe mis à jour avec succès"})

@app.route("/stats/<username>")
@handle_errors
def stats_by_username(username):
    return user_stats(username)


@app.route("/api/my_quests")
@handle_errors
def api_my_quests():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    results = []
    for qdef in QUESTS_DEFINITIONS:
        key = qdef["key"]
        q_sel = ("SELECT progress, completed, completed_at FROM user_quests WHERE username=%s AND quest_key=%s"
                 if USE_POSTGRES else
                 "SELECT progress, completed, completed_at FROM user_quests WHERE username=? AND quest_key=?")
        cur.execute(q_sel, (username, key))
        row = row_to_dict(cur.fetchone()) or {}
        completed = bool(row.get("completed"))
        progress  = row.get("progress") or 0
        cosmetic  = COSMETICS_CATALOG.get(qdef.get("reward_cosmetic") or "", {})
        results.append({
            "key":          key,
            "name":         qdef["name"],
            "description":  qdef["description"],
            "icon":         qdef["icon"],
            "condition_type":  qdef["condition_type"],
            "condition_value": qdef["condition_value"],
            "reward_cosmetic": qdef.get("reward_cosmetic"),
            "reward_label":    qdef.get("reward_label"),
            "reward_type":     cosmetic.get("type"),
            "progress":        progress,
            "completed":       completed,
            "completed_at":    str(row.get("completed_at") or ""),
        })
    cur.close(); conn.close()
    return jsonify(results)

@app.route("/api/my_cosmetics")
@handle_errors
def api_my_cosmetics():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    q = ("SELECT unlocked_cosmetics, active_theme, active_frame FROM users WHERE username=%s"
         if USE_POSTGRES else
         "SELECT unlocked_cosmetics, active_theme, active_frame FROM users WHERE username=?")
    cur.execute(q, (username,))
    row = row_to_dict(cur.fetchone()) or {}
    cur.close(); conn.close()
    try:
        unlocked = json.loads(row.get("unlocked_cosmetics") or "[]")
    except Exception:
        unlocked = []
    return jsonify({
        "unlocked": unlocked,
        "active_theme": row.get("active_theme") or "default",
        "active_frame": row.get("active_frame") or "none",
        "catalog": COSMETICS_CATALOG,
    })

@app.route("/api/equip_cosmetic", methods=["POST"])
@handle_errors
def api_equip_cosmetic():
    username = session.get("username")
    if not username:
        return jsonify({"error": "Non connecté"}), 401
    data = request.get_json() or {}
    raw_slot = str(data.get("slot") or data.get("type") or "").strip().lower()  # "theme" ou "frame"
    raw_key = str(data.get("key") or "").strip().lower()
    if raw_slot not in ("theme", "frame"):
        return jsonify({"success": False, "message": "Slot invalide (theme/frame)"}), 400
    if not raw_key:
        return jsonify({"success": False, "message": "Cosmétique manquant"}), 400

    # Accepte les clés courtes front ("fire", "bronze") et les clés canoniques ("theme_fire", "frame_bronze")
    aliases = {"theme": {"default": "default"}, "frame": {"none": "none"}}
    for ckey, meta in COSMETICS_CATALOG.items():
        ctype = (meta or {}).get("type")
        if ctype not in aliases:
            continue
        aliases[ctype][ckey.lower()] = ckey
        short_key = ckey.split("_", 1)[1] if "_" in ckey else ckey
        aliases[ctype][short_key.lower()] = ckey

    slot = raw_slot
    cosmetic_key = aliases[slot].get(raw_key)
    if not cosmetic_key:
        return jsonify({"success": False, "message": "Cosmétique invalide pour ce slot"}), 400

    # Vérifier que le joueur possède ce cosmétique
    conn = get_db_connection()
    cur = conn.cursor()
    q = ("SELECT unlocked_cosmetics FROM users WHERE username=%s"
         if USE_POSTGRES else
         "SELECT unlocked_cosmetics FROM users WHERE username=?")
    cur.execute(q, (username,))
    row = row_to_dict(cur.fetchone()) or {}
    try:
        unlocked = json.loads(row.get("unlocked_cosmetics") or "[]")
    except Exception:
        unlocked = []
    # Compat anciennes données: normaliser d'éventuelles clés courtes stockées en DB.
    unlocked_norm = set(unlocked)
    for k in unlocked:
        mapped = aliases[slot].get(str(k).strip().lower())
        if mapped:
            unlocked_norm.add(mapped)
    # "default" et "none" sont toujours équipables
    if cosmetic_key not in ("default", "none") and cosmetic_key not in unlocked_norm:
        # Super admin peut tout équiper
        if not is_super_admin(username):
            cur.close(); conn.close()
            return jsonify({"success": False, "message": "Cosmétique non débloqué"}), 403
    if slot == "theme":
        q_upd = ("UPDATE users SET active_theme=%s WHERE username=%s"
                 if USE_POSTGRES else
                 "UPDATE users SET active_theme=? WHERE username=?")
        cur.execute(q_upd, (cosmetic_key, username))
    elif slot == "frame":
        q_upd = ("UPDATE users SET active_frame=%s WHERE username=%s"
                 if USE_POSTGRES else
                 "UPDATE users SET active_frame=? WHERE username=?")
        cur.execute(q_upd, (cosmetic_key, username))
    else:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Slot invalide (theme/frame)"}), 400
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "slot": slot, "key": cosmetic_key})

@app.route("/api/admin/unlock_cosmetic", methods=["POST"])
@handle_errors
def api_admin_unlock_cosmetic():
    """Super admin : débloquer/forcer un cosmétique sur n'importe quel joueur."""
    admin = session.get("username")
    if not is_super_admin(admin):
        return jsonify({"success": False, "message": "Super admin requis"}), 403
    data = request.get_json() or {}
    target    = data.get("username")
    cosmetic  = data.get("cosmetic")
    reset     = data.get("reset", False)
    if not target or (not cosmetic and not reset):
        return jsonify({"success": False, "message": "Paramètres manquants"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    if reset:
        q_upd = ("UPDATE users SET unlocked_cosmetics='[]', active_theme='default', active_frame='none' WHERE username=%s"
                 if USE_POSTGRES else
                 "UPDATE users SET unlocked_cosmetics='[]', active_theme='default', active_frame='none' WHERE username=?")
        cur.execute(q_upd, (target,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": f"Cosmétiques de {target} réinitialisés"})
    q_sel = ("SELECT unlocked_cosmetics FROM users WHERE username=%s"
             if USE_POSTGRES else
             "SELECT unlocked_cosmetics FROM users WHERE username=?")
    cur.execute(q_sel, (target,))
    row = row_to_dict(cur.fetchone()) or {}
    try:
        unlocked = json.loads(row.get("unlocked_cosmetics") or "[]")
    except Exception:
        unlocked = []
    if cosmetic not in unlocked:
        unlocked.append(cosmetic)
    q_upd = ("UPDATE users SET unlocked_cosmetics=%s WHERE username=%s"
             if USE_POSTGRES else
             "UPDATE users SET unlocked_cosmetics=? WHERE username=?")
    cur.execute(q_upd, (json.dumps(unlocked), target))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "message": f"Cosmétique '{cosmetic}' débloqué pour {target}"})

@app.route("/api/admin/complete_quest", methods=["POST"])
@handle_errors
def api_admin_complete_quest():
    """Super admin : compléter une quête pour un joueur (pour test)."""
    admin = session.get("username")
    if not is_super_admin(admin):
        return jsonify({"success": False, "message": "Super admin requis"}), 403
    data = request.get_json() or {}
    target    = data.get("username", admin)
    quest_key = data.get("quest_key")
    if not quest_key:
        return jsonify({"success": False, "message": "quest_key requis"}), 400
    qdef = next((q for q in QUESTS_DEFINITIONS if q["key"] == quest_key), None)
    if not qdef:
        return jsonify({"success": False, "message": "Quête inconnue"}), 404
    conn = get_db_connection()
    cur = conn.cursor()
    # Marquer comme complétée
    if USE_POSTGRES:
        cur.execute("""
            INSERT INTO user_quests (username, quest_key, progress, completed, completed_at)
            VALUES (%s, %s, %s, TRUE, %s)
            ON CONFLICT (username, quest_key) DO UPDATE SET
                progress=EXCLUDED.progress, completed=TRUE, completed_at=EXCLUDED.completed_at
        """, (target, quest_key, qdef["condition_value"], now_local().isoformat()))
    else:
        cur.execute("""
            INSERT OR REPLACE INTO user_quests (username, quest_key, progress, completed, completed_at)
            VALUES (?, ?, ?, 1, ?)
        """, (target, quest_key, qdef["condition_value"], now_local().isoformat()))
    # Débloquer cosmétique
    cosmetic = qdef.get("reward_cosmetic")
    if cosmetic:
        q_sel = ("SELECT unlocked_cosmetics FROM users WHERE username=%s"
                 if USE_POSTGRES else
                 "SELECT unlocked_cosmetics FROM users WHERE username=?")
        cur.execute(q_sel, (target,))
        urow = row_to_dict(cur.fetchone()) or {}
        try:
            unlocked = json.loads(urow.get("unlocked_cosmetics") or "[]")
        except Exception:
            unlocked = []
        if cosmetic not in unlocked:
            unlocked.append(cosmetic)
            q_upd = ("UPDATE users SET unlocked_cosmetics=%s WHERE username=%s"
                     if USE_POSTGRES else
                     "UPDATE users SET unlocked_cosmetics=? WHERE username=?")
            cur.execute(q_upd, (json.dumps(unlocked), target))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "reward_cosmetic": cosmetic, "reward_label": qdef.get("reward_label")})

@app.route("/api/cosmetics_catalog")
def api_cosmetics_catalog():
    return jsonify({"catalog": COSMETICS_CATALOG, "quests": QUESTS_DEFINITIONS})

# ── Routes Badges (Imran uniquement) ─────────────────────────────────────────

@app.route("/api/badges", methods=["GET"])
@handle_errors
def api_list_badges():
    """Liste tous les badges du catalogue."""
    conn = get_db_connection()
    cur  = conn.cursor()
    if USE_POSTGRES:
        cur.execute("SELECT * FROM badges ORDER BY created_at DESC")
    else:
        cur.execute("SELECT * FROM badges ORDER BY created_at DESC")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)


@app.route("/api/badges/upload_image", methods=["POST"])
@handle_errors
def api_upload_badge_image():
    """Upload une image pour un badge — Imran uniquement.
    Accepte multipart/form-data avec le champ 'image'.
    Stocke dans Cloudinary si disponible, sinon base64 en DB retourné comme data-URI.
    """
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"success": False, "message": "Réservé à Imran"}), 403

    # Support JSON (data-URI base64) ou multipart
    img_data = None
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("image")
        if not f:
            return jsonify({"success": False, "message": "Aucun fichier reçu"}), 400
        mime = f.mimetype or ""
        allowed_mimes = ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif")
        if mime not in allowed_mimes:
            return jsonify({"success": False, "message": "Format non autorisé (JPEG, PNG, WebP, GIF)"}), 400
        raw = f.read()
        if len(raw) > 2 * 1024 * 1024:  # 2 Mo max
            return jsonify({"success": False, "message": "Image trop grande (max 2 Mo)"}), 413
        img_data = f"data:{mime};base64,{_base64.b64encode(raw).decode()}"
    else:
        data = request.get_json(silent=True) or {}
        img_data = data.get("image", "")

    if not img_data:
        return jsonify({"success": False, "message": "Aucune image fournie"}), 400

    ALLOWED_PREFIXES = ("data:image/jpeg", "data:image/jpg", "data:image/png",
                        "data:image/webp", "data:image/gif")
    if not any(img_data.startswith(p) for p in ALLOWED_PREFIXES):
        return jsonify({"success": False, "message": "Format d'image invalide"}), 400
    if "svg" in img_data[:50].lower():
        return jsonify({"success": False, "message": "SVG non autorisé"}), 400

    if USE_CLOUDINARY:
        try:
            import cloudinary.uploader as _uploader
            result = _uploader.upload(
                img_data,
                folder="babyfoot_badges",
                overwrite=False,
                transformation=[
                    {"width": 128, "height": 128, "crop": "fill"},
                    {"quality": "auto", "fetch_format": "auto"}
                ]
            )
            image_url = result.get("secure_url", "")
            return jsonify({"success": True, "image_url": image_url})
        except Exception as e:
            logger.error(f"Erreur Cloudinary badge upload: {e}")
            return jsonify({"success": False, "message": "Erreur upload cloud"}), 500
    else:
        # Fallback : retourner le data-URI (stocké dans image_url en DB)
        MAX_LEN = 300_000  # ~220 Ko image réelle
        if len(img_data) > MAX_LEN:
            return jsonify({"success": False, "message": "Image trop grande sans Cloudinary (max ~220 Ko). Configurez CLOUDINARY_URL."}), 413
        return jsonify({"success": True, "image_url": img_data})



@app.route("/api/badges/create", methods=["POST"])
@handle_errors
def api_create_badge():
    """Créer un badge — Imran uniquement.
    Reçoit du JSON : { name, description, icon, color, image_b64? }
    image_b64 est une data-URI base64 (optionnelle, stockée directement en DB).
    Plus de multipart, plus de Cloudinary — une seule étape, zéro dépendance externe.
    """
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"success": False, "message": "Réservé à Imran"}), 403

    data      = request.get_json(force=True, silent=True) or {}
    name      = (data.get("name") or "").strip()
    desc      = (data.get("description") or "").strip()
    icon      = (data.get("icon") or "🏅").strip()
    color     = (data.get("color") or "#cd7f32").strip()
    image_b64 = (data.get("image_b64") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Le nom est requis"}), 400
    if len(name) > 80:
        return jsonify({"success": False, "message": "Nom trop long (max 80 caractères)"}), 400

    # Validation image si présente
    image_url = None
    if image_b64:
        ALLOWED = ("data:image/jpeg", "data:image/jpg", "data:image/png",
                   "data:image/webp", "data:image/gif")
        if not any(image_b64.startswith(p) for p in ALLOWED):
            return jsonify({"success": False, "message": "Format image invalide (JPEG, PNG, WebP, GIF)"}), 400
        if len(image_b64) > 2_000_000:
            return jsonify({"success": False, "message": "Image trop grande (max ~1.5 Mo)"}), 413
        image_url = image_b64

    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        # S'assurer que la colonne image_url existe (migration non-destructive)
        try:
            if USE_POSTGRES:
                cur.execute("ALTER TABLE badges ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT NULL")
            else:
                cur.execute("PRAGMA table_info(badges)")
                cols = [r[1] if isinstance(r, (list, tuple)) else r['name'] for r in cur.fetchall()]
                if 'image_url' not in cols:
                    cur.execute("ALTER TABLE badges ADD COLUMN image_url TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            conn.rollback()  # colonne déjà présente ou erreur non bloquante, on continue

        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO badges (name, description, icon, color, image_url, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (name, desc, icon, color, image_url, caller)
            )
            badge_id = cur.fetchone()['id']
        else:
            cur.execute(
                "INSERT INTO badges (name, description, icon, color, image_url, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, desc, icon, color, image_url, caller)
            )
            badge_id = cur.lastrowid
        conn.commit()
        logger.info(f"Badge créé : #{badge_id} '{name}' par {caller}")
        return jsonify({"success": True, "id": badge_id, "name": name})
    finally:
        cur.close()
        conn.close()


@app.route("/api/badges/<int:badge_id>", methods=["DELETE"])
@handle_errors
def api_delete_badge(badge_id):
    """Supprimer un badge et toutes ses attributions — Imran uniquement."""
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"success": False, "message": "Réservé à Imran"}), 403

    conn = get_db_connection()
    cur  = conn.cursor()
    if USE_POSTGRES:
        cur.execute("DELETE FROM user_badges WHERE badge_id = %s", (badge_id,))
        cur.execute("DELETE FROM badges WHERE id = %s", (badge_id,))
    else:
        cur.execute("DELETE FROM user_badges WHERE badge_id = ?", (badge_id,))
        cur.execute("DELETE FROM badges WHERE id = ?", (badge_id,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})


@app.route("/api/badges/award", methods=["POST"])
@handle_errors
def api_award_badge():
    """Attribuer un badge à un joueur — Imran uniquement."""
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"success": False, "message": "Réservé à Imran"}), 403

    data     = request.get_json() or {}
    target   = (data.get("username") or "").strip()
    badge_id = data.get("badge_id")

    if not target or not badge_id:
        return jsonify({"success": False, "message": "username et badge_id requis"}), 400

    conn = get_db_connection()
    cur  = conn.cursor()
    # Vérifier que le badge existe
    if USE_POSTGRES:
        cur.execute("SELECT id, name FROM badges WHERE id = %s", (badge_id,))
    else:
        cur.execute("SELECT id, name FROM badges WHERE id = ?", (badge_id,))
    badge = row_to_dict(cur.fetchone())
    if not badge:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Badge introuvable"}), 404

    # Vérifier que le joueur existe
    if USE_POSTGRES:
        cur.execute("SELECT username FROM users WHERE username = %s", (target,))
    else:
        cur.execute("SELECT username FROM users WHERE username = ?", (target,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return jsonify({"success": False, "message": "Joueur introuvable"}), 404

    # Attribuer (IGNORE si déjà attribué)
    try:
        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO user_badges (username, badge_id, awarded_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (target, badge_id, caller)
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO user_badges (username, badge_id, awarded_by) VALUES (?, ?, ?)",
                (target, badge_id, caller)
            )
        conn.commit()
        logger.info(f"Badge #{badge_id} attribué à {target} par {caller}")
        cur.close(); conn.close()
        return jsonify({"success": True, "message": f"Badge '{badge['name']}' attribué à {target}"})
    except Exception as e:
        cur.close(); conn.close()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/badges/revoke", methods=["POST"])
@handle_errors
def api_revoke_badge():
    """Retirer un badge d'un joueur — Imran uniquement."""
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"success": False, "message": "Réservé à Imran"}), 403

    data     = request.get_json() or {}
    target   = (data.get("username") or "").strip()
    badge_id = data.get("badge_id")

    if not target or not badge_id:
        return jsonify({"success": False, "message": "username et badge_id requis"}), 400

    conn = get_db_connection()
    cur  = conn.cursor()
    if USE_POSTGRES:
        cur.execute("DELETE FROM user_badges WHERE username = %s AND badge_id = %s", (target, badge_id))
    else:
        cur.execute("DELETE FROM user_badges WHERE username = ? AND badge_id = ?", (target, badge_id))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})


@app.route("/api/badges/user/<username>", methods=["GET"])
@handle_errors
def api_user_badges(username):
    """Badges d'un joueur — accessible à tous."""
    conn = get_db_connection()
    cur  = conn.cursor()
    if USE_POSTGRES:
        cur.execute("""
            SELECT b.id, b.name, b.description, b.icon, b.color, ub.awarded_by, ub.awarded_at
            FROM user_badges ub
            JOIN badges b ON b.id = ub.badge_id
            WHERE ub.username = %s
            ORDER BY ub.awarded_at DESC
        """, (username,))
    else:
        cur.execute("""
            SELECT b.id, b.name, b.description, b.icon, b.color, ub.awarded_by, ub.awarded_at
            FROM user_badges ub
            JOIN badges b ON b.id = ub.badge_id
            WHERE ub.username = ?
            ORDER BY ub.awarded_at DESC
        """, (username,))
    rows = [row_to_dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)


@app.route("/api/badges/all_users", methods=["GET"])
@handle_errors
def api_badges_all_users():
    """Vue complète : qui a quels badges — Imran uniquement."""
    caller = session.get("username")
    if not is_super_admin(caller):
        return jsonify({"error": "Réservé à Imran"}), 403

    conn = get_db_connection()
    cur  = conn.cursor()
    if USE_POSTGRES:
        cur.execute("""
            SELECT ub.username, b.id AS badge_id, b.name, b.icon, b.color, ub.awarded_at
            FROM user_badges ub
            JOIN badges b ON b.id = ub.badge_id
            ORDER BY ub.username, ub.awarded_at DESC
        """)
    else:
        cur.execute("""
            SELECT ub.username, b.id AS badge_id, b.name, b.icon, b.color, ub.awarded_at
            FROM user_badges ub
            JOIN badges b ON b.id = ub.badge_id
            ORDER BY ub.username, ub.awarded_at DESC
        """)
    rows = [row_to_dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)


# ── Arduino HTTP endpoints ────────────────────────────────────

arduino_last_goal_time = {}

# Secret Arduino lu au démarrage (évite os.environ.get à chaque requête)
_ARDUINO_SECRET = os.environ.get("ARDUINO_SECRET", "")
if not _ARDUINO_SECRET:
    logger.error("🚨 ARDUINO_SECRET non defini ! Definissez cette variable dans Render → Environment.")
    logger.error("   Sans ce secret, l'endpoint Arduino est non protégé.")

def _is_arduino_request_authorized(payload=None):
    """Autorise si secret Arduino valide (query/header/body) ou session admin."""
    payload = payload or {}
    provided = (
        request.args.get("secret")
        or request.headers.get("X-Arduino-Secret")
        or payload.get("secret")
    )
    username = session.get("username")
    if username and is_admin(username):
        return True
    return bool(_get_arduino_secret()) and provided == _get_arduino_secret()

@app.route("/api/arduino/status", methods=["GET"])
def api_arduino_status():
    """Etat complet pour l'ESP32 (sync au demarrage + poll)."""
    if not _is_arduino_request_authorized():
        return jsonify({"success": False, "message": "Non autorise"}), 403
    active = current_game.get("active", False)
    t1 = current_game.get("team1_score", 0)
    t2 = current_game.get("team2_score", 0)
    servo1_expected = "open" if (active and t1 < 9) else "close"
    servo2_expected = "open" if (active and t2 < 9) else "close"
    return jsonify({
        "game_active":     active,
        "team1_score":     t1,
        "team2_score":     t2,
        "servo1_expected": servo1_expected,
        "servo2_expected": servo2_expected,
        "started_by":      current_game.get("started_by"),
        "team1_players":   current_game.get("team1_players", []),
        "team2_players":   current_game.get("team2_players", []),
    })

@app.route("/api/arduino/commands", methods=["GET"])
def api_arduino_commands():
    global servo_commands
    if not _is_arduino_request_authorized():
        return jsonify({"success": False, "message": "Non autorise"}), 403
    now = _time.time()
    if not hasattr(api_arduino_commands, 'last_poll'):
        api_arduino_commands.last_poll = 0
    if now - api_arduino_commands.last_poll > 30:
        # L'ESP32 n'a pas poll depuis 30s → probablement redemarrage, nettoyer la queue
        servo_commands["servo1"].clear()
        servo_commands["servo2"].clear()
        logger.info("Queue servos nettoyee (reboot ESP32 detecte)")
    api_arduino_commands.last_poll = now
    cmd1 = servo_commands["servo1"].pop(0) if servo_commands["servo1"] else "none"
    cmd2 = servo_commands["servo2"].pop(0) if servo_commands["servo2"] else "none"
    return jsonify({"servo1": cmd1, "servo2": cmd2})

@app.route("/api/arduino/servo", methods=["POST"])
def api_arduino_servo():
    """Controle direct des servos via HTTP (utilise le secret Arduino, pas la session)."""
    global servo_commands
    data = request.get_json(silent=True) or {}
    if not _is_arduino_request_authorized(data):
        return jsonify({"success": False, "message": "Non autorise"}), 403
    servo = data.get("servo")
    action = data.get("action")
    if servo not in ["servo1", "servo2"] or action not in ["open", "close"]:
        return jsonify({"success": False, "message": "Parametres invalides"}), 400
    servo_commands[servo].clear()
    servo_commands[servo].append(action)
    return jsonify({"success": True, "servo": servo, "action": action})

def _get_arduino_secret():
    """Retourne le secret Arduino depuis l'environnement (lu une seule fois au démarrage)."""
    return _ARDUINO_SECRET

@app.route("/api/arduino/goal", methods=["POST"])
def api_arduino_goal():
    global current_game, rematch_pending
    data = request.get_json(silent=True) or {}
    if not _is_arduino_request_authorized(data):
        return jsonify({"success": False, "message": "Secret invalide"}), 403
    now = _time.time()
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if client_ip in arduino_last_goal_time and now - arduino_last_goal_time[client_ip] < 1:
        return jsonify({"success": False, "message": "Trop rapide"}), 429
    arduino_last_goal_time[client_ip] = now
    if not current_game.get("active"):
        return jsonify({"success": False, "message": "Aucune partie en cours", "game_active": False}), 200
    team = data.get("team")
    if team not in ["team1", "team2"]:
        return jsonify({"success": False, "message": "Equipe invalide"}), 400
    # Verrou thread-safe : évite les doubles buts si ESP32 + Socket arrivent simultanément
    acquired = _goal_lock.acquire(blocking=False)
    if not acquired:
        return jsonify({"success": False, "message": "Traitement en cours"}), 429
    try:
        return _process_goal(team)
    finally:
        _goal_lock.release()


def _process_goal(team):
    """Logique partagée de traitement d'un but (HTTP Arduino et Socket)."""
    global current_game, servo_commands, rematch_pending
    current_game[f"{team}_score"] += 1
    if current_game[f"{team}_score"] == 9:
        # À 9 buts : verrouiller la balle adverse (avertissement)
        servo_adverse = 'servo1' if team == 'team2' else 'servo2'
        servo_commands[servo_adverse].append('close')
        socketio.emit(f"{servo_adverse}_lock", {}, namespace="/")
    if current_game[f"{team}_score"] >= 10:
        current_game["winner"] = team
        current_game["active"] = False
        servo_commands["servo1"].append("close")
        servo_commands["servo2"].append("close")
        try:
            save_game_results(current_game)
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
        socketio.emit("game_ended", current_game, namespace="/")
        rematch_pending = True
        socketio.emit("rematch_prompt", {}, namespace="/")
        return jsonify({"success": True, "game_ended": True, "winner": team})
    socketio.emit("score_updated", current_game, namespace="/")
    return jsonify({
        "success": True,
        "game_ended": False,
        "scores": {"team1": current_game["team1_score"], "team2": current_game["team2_score"]}
    })

# ── SocketIO handlers ─────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    global rematch_pending
    username = session.get('username')
    if not username:
        logger.warning(f"WS refuse: utilisateur non authentifie ({request.sid})")
        return False
    connected_users[request.sid] = username
    logger.info(f"WS connecte: {username} ({request.sid})")

    # Annuler le délai de grâce si le joueur était en train de naviguer
    if username in _lobby_grace:
        _lobby_grace.pop(username, None)
        logger.info(f"Lobby grace annulé pour {username} (reconnecté)")

    # Partie active → recuperation en cours de jeu
    if current_game.get('active'):
        join_room('game')
        emit('game_recovery', current_game)
    # Partie terminée et popup victoire pas encore fermée → rejouer game_ended SEULEMENT si l'user était dans la partie
    elif current_game.get('winner') and not current_game.get('active'):
        user_in_game = (
            username in current_game.get('team1_players', []) or
            username in current_game.get('team2_players', []) or
            is_admin(username) or
            username == current_game.get('started_by')
        )
        if user_in_game:
            emit('game_ended', current_game)
            if rematch_pending:
                emit('rematch_prompt', {})

    # Invitation lobby en attente → la renvoyer
    if username in pending_invitations:
        inv = pending_invitations[username]
        if _time.time() - inv.get('timestamp', 0) < 300:
            emit('lobby_invitation', {'from': inv['from'], 'to': username})

def _remove_player_from_lobby(username):
    """
    Retire un joueur de toutes les listes du lobby de façon atomique.
    Si c'est l'hôte qui part :
      - promouvoit le premier joueur accepté comme nouvel hôte,
      - ou annule le lobby si personne d'autre n'est présent.
    Retourne un dict {'action': 'left'|'host_promoted'|'cancelled', 'new_host': ...}
    """
    global active_lobby, pending_invitations
    if not active_lobby.get('active'):
        return {'action': 'none'}

    result = {'action': 'left', 'new_host': None}

    if username == active_lobby.get('host'):
        # L'hôte part → chercher un successeur parmi les joueurs acceptés
        # Chercher dans toutes les listes (accepted peut être désynchronisé)
        all_present = set()
        for lst in ['accepted', 'team1', 'team2']:
            all_present.update(active_lobby.get(lst, []))
        candidates = [u for u in active_lobby.get('accepted', []) if u != username]
        if not candidates:
            # Fallback: chercher dans team1/team2
            candidates = [u for u in all_present if u != username]
        if not candidates:
            # Personne d'autre → annuler le lobby
            for u in list(active_lobby.get('invited', [])):
                pending_invitations.pop(u, None)
            pending_invitations.pop(username, None)
            active_lobby = {
                "host": None, "invited": [], "accepted": [],
                "declined": [], "team1": [], "team2": [],
                "active": False, "join_requests": {}, "team_pref": {}
            }
            result['action'] = 'cancelled'
            return result
        # Promouvoir le premier candidat
        new_host = candidates[0]
        active_lobby['host'] = new_host
        result['action'] = 'host_promoted'
        result['new_host'] = new_host

    # Retirer l'utilisateur de toutes les listes
    for lst in ['invited', 'accepted', 'team1', 'team2', 'declined']:
        if username in active_lobby.get(lst, []):
            active_lobby[lst].remove(username)
    # Nettoyer ses éventuelles join_requests
    join_requests = active_lobby.get('join_requests', {})
    to_del = [rid for rid, v in join_requests.items() if v.get('from') == username]
    for rid in to_del:
        join_requests.pop(rid, None)
    pending_invitations.pop(username, None)
    return result


@socketio.on('disconnect')
def handle_disconnect():
    username = connected_users.pop(request.sid, None)
    logger.info(f"WS deconnecte: {request.sid} ({username})")
    if username and username in pending_rematch_replacements:
        inv = pending_rematch_replacements.pop(username, None) or {}
        emit_to_user(inv.get('host'), 'rematch_invite_declined', {
            'replacement_player': username,
            'declined_player': inv.get('declined_player'),
            'reason': 'offline'
        })
    if username and active_lobby.get('active'):
        # Délai de grâce : on attend avant de retirer le joueur du lobby
        # (navigation entre pages = déconnexion + reconnexion rapide)
        _lobby_grace[username] = _time.time()

        def _delayed_lobby_remove(uname, disc_time):
            _time.sleep(_LOBBY_GRACE_SECONDS)
            # Si le joueur s'est reconnecté depuis, son entrée a été supprimée de _lobby_grace
            if _lobby_grace.get(uname) != disc_time:
                return
            _lobby_grace.pop(uname, None)
            if not active_lobby.get('active'):
                return
            with _lobby_lock:
                result = _remove_player_from_lobby(uname)
            if result['action'] == 'cancelled':
                socketio.emit('lobby_cancelled', {'reason': 'host_left', 'host': uname}, namespace='/')
                logger.info(f"Lobby annulé : hôte {uname} déconnecté (grâce expirée)")
            elif result['action'] == 'host_promoted':
                socketio.emit('lobby_host_changed', {'new_host': result['new_host'], 'old_host': uname}, namespace='/')
                socketio.emit('lobby_update', active_lobby, namespace='/')
                logger.info(f"Lobby : {uname} déconnecté, nouvel hôte {result['new_host']}")
            elif result['action'] == 'left':
                socketio.emit('lobby_update', active_lobby, namespace='/')

        t = _threading.Thread(target=_delayed_lobby_remove, args=(username, _lobby_grace[username]), daemon=True)
        t.start()

@socketio.on('create_lobby')
def handle_create_lobby(data):
    global active_lobby
    username = get_socket_user()
    if not is_admin(username) and not has_active_reservation(username):
        emit('error', {'message': 'Seuls admins/reservateurs peuvent creer un lobby'})
        return
    # Bloquer si une partie est en cours (sauf super admin)
    if current_game.get('active') and not is_super_admin(username):
        emit('error', {'message': 'Une partie est en cours — impossible de créer un lobby'})
        return
    # Si un lobby est déjà actif, seul Imran peut en créer un nouveau (annule l'ancien)
    if active_lobby.get('active') and not is_super_admin(username):
        emit('error', {'message': 'Un lobby est déjà en cours — seul Imran peut le remplacer'})
        return
    with _lobby_lock:
        if active_lobby.get('active'):
            socketio.emit('lobby_cancelled', {}, namespace='/')
        invited_users = data.get('invited', [])
        active_lobby = {
            "host": username, "invited": invited_users,
            "accepted": [username], "declined": [],
            "team1": [username], "team2": [],
            "active": True, "join_requests": {}
        }
    socketio.emit('lobby_created', {'host': username, 'invited': invited_users}, namespace='/')
    for user in invited_users:
        socketio.emit('lobby_invitation', {'from': username, 'to': user}, namespace='/')

@socketio.on('invite_to_lobby')
def handle_invite_to_lobby(data):
    global active_lobby
    username = get_socket_user()
    invited_user = data.get('user')
    if username != active_lobby['host'] and not is_admin(username):
        emit('error', {'message': "Seul l'hote ou un admin peut inviter"})
        return
    # Compter uniquement les vrais joueurs (pas les guests) pour la limite du lobby
    real_accepted = [u for u in active_lobby['accepted'] if not is_guest_player(u)]
    real_invited  = [u for u in active_lobby['invited']  if not is_guest_player(u)]
    if not is_guest_player(invited_user) and len(real_accepted) + len(real_invited) >= 4:
        emit('error', {'message': 'Lobby complet'})
        return
    already_in = (
        invited_user in active_lobby['invited'] or
        invited_user in active_lobby['accepted'] or
        invited_user in active_lobby['team1'] or
        invited_user in active_lobby['team2']
    )
    if already_in:
        return
    pending_invitations[invited_user] = {'from': active_lobby['host'], 'timestamp': _time.time()}
    if is_guest_player(invited_user):
        active_lobby['accepted'].append(invited_user)
        # Placer dans l'équipe demandée (si précisée), sinon la moins remplie
        target_team = data.get('team', '')
        t1, t2 = len(active_lobby['team1']), len(active_lobby['team2'])
        placed = False
        if target_team == 'team1' and t1 < 2:
            active_lobby['team1'].append(invited_user)
            placed = True
        elif target_team == 'team2' and t2 < 2:
            active_lobby['team2'].append(invited_user)
            placed = True
        if not placed:
            # Fallback : équipe la moins remplie avec de la place
            if t1 <= t2 and t1 < 2:
                active_lobby['team1'].append(invited_user)
            elif t2 < 2:
                active_lobby['team2'].append(invited_user)
            elif t1 < 2:
                active_lobby['team1'].append(invited_user)
            else:
                active_lobby['accepted'].remove(invited_user)
                emit('error', {'message': 'Equipes completes'})
                return
    else:
        active_lobby['invited'].append(invited_user)
        # Stocker la préférence d'équipe de l'hôte pour ce joueur
        target_team = data.get('team', '')
        if target_team in ('team1', 'team2'):
            active_lobby.setdefault('team_pref', {})[invited_user] = target_team
        socketio.emit('lobby_invitation', {'from': active_lobby['host'], 'to': invited_user, 'team': target_team}, namespace='/')
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('leave_lobby')
def handle_leave_lobby():
    """Un joueur quitte volontairement le lobby sans annuler pour tout le monde."""
    global active_lobby
    username = get_socket_user()
    if not username or not active_lobby.get('active'):
        return
    with _lobby_lock:
        result = _remove_player_from_lobby(username)
    if result['action'] == 'none':
        return
    elif result['action'] == 'cancelled':
        socketio.emit('lobby_cancelled', {'reason': 'host_left', 'host': username}, namespace='/')
    elif result['action'] == 'host_promoted':
        socketio.emit('lobby_host_changed', {'new_host': result['new_host'], 'old_host': username}, namespace='/')
        socketio.emit('lobby_update', active_lobby, namespace='/')
    else:
        socketio.emit('lobby_update', active_lobby, namespace='/')


@socketio.on('accept_lobby')
def handle_accept_lobby():
    global active_lobby
    username = get_socket_user()
    if not username or not active_lobby.get('active'):
        return
    with _lobby_lock:
        # Vérification atomique : déjà dans une équipe ?
        if username in active_lobby.get('team1', []) or username in active_lobby.get('team2', []):
            return
        if username not in active_lobby.get('invited', []):
            if username not in active_lobby.get('accepted', []):
                return
        if username in active_lobby.get('invited', []):
            active_lobby['invited'].remove(username)
        if username not in active_lobby['accepted']:
            active_lobby['accepted'].append(username)
        t1, t2 = len(active_lobby['team1']), len(active_lobby['team2'])
        # Respecter la préférence d'équipe de l'hôte si possible
        pref = active_lobby.get('team_pref', {}).pop(username, '')
        placed = False
        if pref == 'team1' and t1 < 2:
            active_lobby['team1'].append(username)
            placed = True
        elif pref == 'team2' and t2 < 2:
            active_lobby['team2'].append(username)
            placed = True
        if not placed:
            # Fallback : équipe la moins remplie
            if t1 <= t2 and t1 < 2:
                active_lobby['team1'].append(username)
            elif t2 < 2:
                active_lobby['team2'].append(username)
            elif t1 < 2:
                active_lobby['team1'].append(username)
            else:
                emit('error', {'message': 'Equipes completes'})
                active_lobby['accepted'].remove(username)
                active_lobby['invited'].append(username)
                return
        pending_invitations.pop(username, None)
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('decline_lobby')
def handle_decline_lobby():
    global active_lobby
    username = get_socket_user()
    if not username or not active_lobby.get('active'):
        return
    if username not in active_lobby.get('invited', []):
        return
    active_lobby['invited'].remove(username)
    if username not in active_lobby['declined']:
        active_lobby['declined'].append(username)
    pending_invitations.pop(username, None)
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('request_join_lobby')
def handle_request_join_lobby():
    global active_lobby
    username = get_socket_user()
    if not username:
        return
    if not active_lobby['active']:
        emit('error', {'message': 'Aucun lobby actif'})
        return
    host = active_lobby['host']
    if username == host:
        return
    already_in = (
        username in active_lobby.get('invited', []) or
        username in active_lobby.get('accepted', []) or
        username in active_lobby.get('team1', []) or
        username in active_lobby.get('team2', [])
    )
    if already_in:
        emit('error', {'message': 'Vous etes deja dans ce lobby'})
        return
    request_id = str(_uuid.uuid4())[:8]
    if 'join_requests' not in active_lobby:
        active_lobby['join_requests'] = {}
    active_lobby['join_requests'][request_id] = {'from': username}
    socketio.emit('join_request', {
        'from': username,
        'host': host,
        'request_id': request_id
    }, namespace='/')

@socketio.on('accept_join_request')
def handle_accept_join_request(data):
    global active_lobby
    host = get_socket_user()
    from_user = data.get('from')
    request_id = data.get('request_id')
    if not active_lobby.get('active'):
        return
    if host != active_lobby['host'] and not is_admin(host):
        emit('error', {'message': 'Seul l hote peut accepter les demandes'})
        return
    with _lobby_lock:
        join_requests = active_lobby.get('join_requests', {})
        if request_id not in join_requests:
            # Requête déjà traitée (race condition) → ignorer silencieusement
            return
        join_requests.pop(request_id, None)
        # Vérifier que l'utilisateur n'est pas déjà dans le lobby (toutes listes)
        already_in = (
            from_user in active_lobby.get('invited', []) or
            from_user in active_lobby.get('accepted', []) or
            from_user in active_lobby.get('team1', []) or
            from_user in active_lobby.get('team2', [])
        )
        if not already_in:
            active_lobby.setdefault('invited', []).append(from_user)
            pending_invitations[from_user] = {'from': active_lobby['host'], 'timestamp': _time.time()}
    socketio.emit('join_request_result', {
        'accepted': True,
        'host': host,
        'from': from_user
    }, namespace='/')
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('decline_join_request')
def handle_decline_join_request(data):
    global active_lobby
    host = get_socket_user()
    from_user = data.get('from')
    request_id = data.get('request_id')
    if not active_lobby['active']:
        return
    join_requests = active_lobby.get('join_requests', {})
    join_requests.pop(request_id, None)
    socketio.emit('join_request_result', {
        'accepted': False,
        'host': host,
        'from': from_user
    }, namespace='/')

@socketio.on('request_team_swap')
def handle_request_team_swap(data):
    from_user = get_socket_user()
    to_user = data.get('with')
    request_id = f"{from_user}_{to_user}"
    team_swap_requests[request_id] = {'from': from_user, 'to': to_user}
    socketio.emit('team_swap_request', {'from': from_user, 'to': to_user, 'request_id': request_id}, namespace='/')

@socketio.on('accept_team_swap')
def handle_accept_team_swap(data):
    global active_lobby
    request_id = data.get('request_id')
    if request_id not in team_swap_requests:
        return
    swap = team_swap_requests.pop(request_id)
    fu, tu = swap['from'], swap['to']
    if fu in active_lobby['team1'] and tu in active_lobby['team2']:
        active_lobby['team1'].remove(fu)
        active_lobby['team2'].remove(tu)
        active_lobby['team1'].append(tu)
        active_lobby['team2'].append(fu)
    elif fu in active_lobby['team2'] and tu in active_lobby['team1']:
        active_lobby['team2'].remove(fu)
        active_lobby['team1'].remove(tu)
        active_lobby['team2'].append(tu)
        active_lobby['team1'].append(fu)
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('decline_team_swap')
def handle_decline_team_swap(data):
    request_id = data.get('request_id')
    if request_id in team_swap_requests:
        team_swap_requests.pop(request_id)

@socketio.on('kick_from_lobby')
def handle_kick_from_lobby(data):
    global active_lobby
    username = get_socket_user()
    kicked_user = data.get('user')
    if not username or not active_lobby.get('active'):
        return
    if username != active_lobby.get('host') and not is_admin(username):
        emit('error', {'message': "Seul l'hote ou un admin peut exclure"})
        return
    if kicked_user == active_lobby['host']:
        emit('error', {'message': "Impossible d'exclure l'hote"})
        return
    for lst in ['invited', 'accepted', 'team1', 'team2']:
        if kicked_user in active_lobby[lst]:
            active_lobby[lst].remove(kicked_user)
    pending_invitations.pop(kicked_user, None)
    socketio.emit('kicked_from_lobby', {'kicked_user': kicked_user}, namespace='/')
    socketio.emit('lobby_update', active_lobby, namespace='/')


@socketio.on('move_player_to_team')
def handle_move_player_to_team(data):
    """L'hôte ou un admin déplace un joueur d'une équipe à l'autre."""
    global active_lobby
    username = get_socket_user()
    target_user = data.get('user')
    target_team = data.get('team')  # 'team1' ou 'team2'
    if not username or not active_lobby.get('active'):
        return
    if username != active_lobby.get('host') and not is_admin(username):
        emit('error', {'message': "Seul l'hôte ou un admin peut déplacer un joueur"})
        return
    if target_team not in ('team1', 'team2'):
        return
    other_team = 'team2' if target_team == 'team1' else 'team1'
    with _lobby_lock:
        # Vérifier que le joueur est dans l'autre équipe
        if target_user not in active_lobby.get(other_team, []):
            # Peut-être déjà dans la bonne équipe
            return
        # Vérifier que la team cible a de la place
        if len(active_lobby.get(target_team, [])) >= 2:
            emit('error', {'message': f'Équipe {target_team} déjà complète'})
            return
        active_lobby[other_team].remove(target_user)
        active_lobby[target_team].append(target_user)
    socketio.emit('lobby_update', active_lobby, namespace='/')

@socketio.on('cancel_lobby')
def handle_cancel_lobby():
    global active_lobby
    username = get_socket_user()
    if not username or not active_lobby.get('active'):
        return
    if username != active_lobby.get('host') and not is_admin(username):
        emit('error', {'message': "Seul l'hote ou un admin peut annuler"})
        return
    for user in list(active_lobby.get('invited', [])):
        pending_invitations.pop(user, None)
    active_lobby = {
        "host": None, "invited": [], "accepted": [],
        "declined": [], "team1": [], "team2": [], "active": False
    }
    socketio.emit('lobby_cancelled', {}, namespace='/')

@socketio.on('start_game_from_lobby')
def handle_start_game_from_lobby():
    global current_game, active_lobby, rematch_votes, servo_commands
    username = get_socket_user()
    if username != active_lobby['host'] and not is_admin(username):
        emit('error', {'message': "Seul l'hote ou un admin peut lancer"})
        return
    if len(active_lobby['accepted']) < 2:
        emit('error', {'message': 'Au moins 2 joueurs requis'})
        return
    if not active_lobby['team1'] or not active_lobby['team2']:
        emit('error', {'message': 'Chaque equipe doit avoir au moins un joueur'})
        return
    current_game = {
        "team1_score": 0, "team2_score": 0,
        "team1_players": active_lobby['team1'],
        "team2_players": active_lobby['team2'],
        "active": True,
        "started_by": username,
        "reserved_by": username if has_active_reservation(username) else None,
        "started_at": now_local().isoformat()
    }
    active_lobby = {
        "host": None, "invited": [], "accepted": [],
        "declined": [], "team1": [], "team2": [], "active": False
    }
    rematch_votes = {"team1": [], "team2": []}
    servo_commands["servo1"].append("open")
    servo_commands["servo2"].append("open")
    socketio.emit('game_started', current_game, namespace='/')
    socketio.emit('servo1_unlock', {}, namespace='/')
    socketio.emit('servo2_unlock', {}, namespace='/')

@socketio.on('start_game')
def handle_start_game(data):
    global current_game, rematch_votes, servo_commands
    try:
        username = get_socket_user()
        if not username:
            emit('error', {'message': 'Non authentifié'})
            return
        if not is_admin(username) and not has_active_reservation(username):
            emit('error', {'message': 'Reservation active ou admin requis'})
            return
        team1 = [p for p in data.get('team1', []) if p and p.strip()]
        team2 = [p for p in data.get('team2', []) if p and p.strip()]
        if not team1 or not team2:
            emit('error', {'message': 'Chaque equipe doit avoir au moins un joueur'})
            return
        if current_game.get('active'):
            emit('error', {'message': 'Une partie est deja en cours'})
            return
        current_game = {
            "team1_score": 0, "team2_score": 0,
            "team1_players": team1, "team2_players": team2,
            "active": True, "started_by": username,
            "reserved_by": username if has_active_reservation(username) else None,
            "started_at": now_local().isoformat()
        }
        rematch_votes = {"team1": [], "team2": []}
        servo_commands["servo1"].append("open")
        servo_commands["servo2"].append("open")
        socketio.emit('game_started', current_game, namespace='/')
        socketio.emit('servo1_unlock', {}, namespace='/')
        socketio.emit('servo2_unlock', {}, namespace='/')
    except Exception as e:
        logger.error(f"Erreur start_game: {e}")
        emit('error', {'message': str(e)})

@socketio.on('unlock_servo1')
def handle_unlock_servo1():
    global servo_commands
    username = get_socket_user()
    if not is_admin(username):
        emit('error', {'message': 'Admin requis'})
        return
    servo_commands["servo1"].clear()
    servo_commands["servo1"].append("open")
    socketio.emit('servo1_unlock', {}, namespace='/')
    def relock():
        _time.sleep(5.0)
        servo_commands["servo1"].clear()
        servo_commands["servo1"].append("close")
        socketio.emit('servo1_lock', {}, namespace='/')
    _threading.Thread(target=relock, daemon=True).start()

@socketio.on('unlock_servo2')
def handle_unlock_servo2():
    global servo_commands
    username = get_socket_user()
    if not is_admin(username):
        emit('error', {'message': 'Admin requis'})
        return
    servo_commands["servo2"].clear()
    servo_commands["servo2"].append("open")
    socketio.emit('servo2_unlock', {}, namespace='/')
    def relock():
        _time.sleep(5.0)
        servo_commands["servo2"].clear()
        servo_commands["servo2"].append("close")
        socketio.emit('servo2_lock', {}, namespace='/')
    _threading.Thread(target=relock, daemon=True).start()

@socketio.on('stop_game')
def handle_stop_game():
    global current_game, rematch_votes, servo_commands, rematch_pending
    username = get_socket_user()
    can_stop = is_admin(username) or current_game.get('started_by') == username
    if not can_stop:
        emit('error', {'message': "Seul l'admin ou l'hote de la partie peut l'arreter"})
        return
    # Sauvegarder si des buts ont ete marques
    if current_game.get('active') and (current_game.get('team1_score', 0) > 0 or current_game.get('team2_score', 0) > 0):
        t1 = current_game.get('team1_score', 0)
        t2 = current_game.get('team2_score', 0)
        current_game['winner'] = 'team1' if t1 > t2 else ('team2' if t2 > t1 else 'team1')
        try:
            save_game_results(current_game)
        except Exception as e:
            logger.error(f"Erreur sauvegarde stop_game: {e}")
    _reset_game_state()
    socketio.emit('game_stopped', {}, namespace='/')
    socketio.emit('servo1_lock', {}, namespace='/')
    socketio.emit('servo2_lock', {}, namespace='/')

@socketio.on('update_score')
def handle_score(data):
    global current_game, rematch_pending
    try:
        username = get_socket_user()
        if not username:
            emit('error', {'message': 'Non authentifié'})
            return
        if not current_game.get('active'):
            emit('error', {'message': 'Aucune partie en cours'})
            return
        can_control = is_admin(username)
        if not can_control:
            emit('error', {'message': "Seul un admin peut ajouter des points"})
            return
        team = data.get('team')
        if team not in ['team1', 'team2']:
            emit('error', {'message': 'Equipe invalide'})
            return
        # Evite les doubles increments si plusieurs events arrivent en meme temps.
        acquired = _goal_lock.acquire(blocking=False)
        if not acquired:
            emit('error', {'message': 'Traitement score en cours'})
            return
        try:
            result = _process_goal(team)
        finally:
            _goal_lock.release()
        payload = result.get_json() if hasattr(result, 'get_json') else {}
        emit('score_ack', {
            'team': team,
            'score': current_game.get(f"{team}_score", 0),
            'game_ended': bool(payload.get('game_ended', False))
        })
    except Exception as e:
        logger.error(f"Erreur update_score: {e}")
        emit('error', {'message': str(e)})

@socketio.on('vote_rematch')
def handle_vote_rematch(data):
    global rematch_votes, rematch_no_votes, current_game, servo_commands, rematch_pending, pending_rematch_replacements
    username = get_socket_user()
    if not username:
        return
    all_players = list(current_game.get('team1_players', [])) + list(current_game.get('team2_players', []))
    host = current_game.get('started_by')

    if data.get('vote') == 'no':
        pending_rematch_replacements.clear()
        # Enregistrer le NON
        if username not in rematch_no_votes:
            rematch_no_votes.append(username)
        yes_count = len(rematch_votes['team1']) + len(rematch_votes['team2'])
        no_count = len(rematch_no_votes)
        # Envoyer update des votes à tout le monde
        socketio.emit('rematch_vote_update', {
            'yes': yes_count, 'no': no_count,
            'total': len(all_players),
            'no_player': username
        }, namespace='/')
        # Notifier l'hôte pour qu'il décide : remplacer ou quitter
        socketio.emit('host_replace_or_quit', {
            'declined_player': username,
            'host': host
        }, namespace='/')
        return

    # Vote OUI
    team = None
    if username in current_game.get('team1_players', []):
        team = 'team1'
    elif username in current_game.get('team2_players', []):
        team = 'team2'
    elif is_admin(username) or username == host:
        # Admin/hôte forcent le rematch
        _launch_rematch(current_game)
        return
    if not team:
        emit('error', {'message': 'Pas dans cette partie'})
        return
    if username not in rematch_votes[team]:
        rematch_votes[team].append(username)
    yes_count = len(rematch_votes['team1']) + len(rematch_votes['team2'])
    no_count = len(rematch_no_votes)
    socketio.emit('rematch_vote_update', {
        'yes': yes_count, 'no': no_count,
        'total': len(all_players)
    }, namespace='/')
    # Lancer uniquement si tous les joueurs qui N'ONT PAS voté NON ont voté OUI
    t1_needed = [p for p in current_game.get('team1_players', []) if p not in rematch_no_votes]
    t2_needed = [p for p in current_game.get('team2_players', []) if p not in rematch_no_votes]
    t1_yes = [p for p in rematch_votes['team1'] if p not in rematch_no_votes]
    t2_yes = [p for p in rematch_votes['team2'] if p not in rematch_no_votes]
    if len(t1_yes) >= len(t1_needed) and len(t2_yes) >= len(t2_needed) and (t1_needed or t2_needed):
        rematch_no_votes.clear()
        _launch_rematch(current_game)

@socketio.on('host_quit_rematch')
def handle_host_quit_rematch():
    global rematch_votes, rematch_no_votes, rematch_pending, pending_rematch_replacements
    username = get_socket_user()
    host = current_game.get('started_by')
    if username != host and not is_admin(username):
        return
    rematch_votes = {"team1": [], "team2": []}
    rematch_no_votes = []
    rematch_pending = False
    pending_rematch_replacements.clear()
    socketio.emit('rematch_cancelled', {}, namespace='/')

def _validate_rematch_replacement_request(actor_username, data):
    """Valide une demande de remplacement pour la revanche."""
    host = current_game.get('started_by')
    if actor_username != host and not is_admin(actor_username):
        return None, "Seul l'hote ou un admin peut remplacer un joueur"
    if current_game.get('active') or not rematch_pending:
        return None, "Aucune revanche en attente"

    data = data or {}
    declined_player = str(data.get('declined_player') or '').strip()
    replacement_player = str(data.get('replacement_player') or data.get('replacement') or '').strip()
    if not declined_player or not replacement_player:
        return None, "Parametres manquants"
    if declined_player == replacement_player:
        return None, "Le remplacant doit etre different"

    t1 = list(current_game.get('team1_players', []) or [])
    t2 = list(current_game.get('team2_players', []) or [])
    all_players = set(t1 + t2)
    if declined_player not in all_players:
        return None, "Joueur a remplacer introuvable"
    if replacement_player in all_players:
        return None, "Ce joueur est deja dans la partie"

    if not is_guest_player(replacement_player):
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            q = ("SELECT username FROM users WHERE username=%s"
                 if USE_POSTGRES else
                 "SELECT username FROM users WHERE username=?")
            cur.execute(q, (replacement_player,))
            exists = row_to_dict(cur.fetchone()) is not None
            if not exists:
                return None, "Le remplacant n'existe pas"
        except Exception:
            return None, "Impossible de verifier le remplacant"
        finally:
            try:
                if cur: cur.close()
            except Exception:
                pass
            try:
                if conn: conn.close()
            except Exception:
                pass

    target_team = None
    if declined_player in t1:
        t1[t1.index(declined_player)] = replacement_player
        target_team = 'team1'
    elif declined_player in t2:
        t2[t2.index(declined_player)] = replacement_player
        target_team = 'team2'

    return {
        'declined_player': declined_player,
        'replacement_player': replacement_player,
        'team1_players': t1,
        'team2_players': t2,
        'team': target_team
    }, None

def _apply_rematch_replacement(payload):
    """Applique le remplacement dans current_game et nettoie les votes."""
    global current_game, rematch_votes, rematch_no_votes, pending_rematch_replacements
    declined_player = payload['declined_player']
    replacement_player = payload['replacement_player']
    current_game['team1_players'] = payload['team1_players']
    current_game['team2_players'] = payload['team2_players']

    rematch_no_votes = [u for u in rematch_no_votes if u not in (declined_player, replacement_player)]
    rematch_votes['team1'] = [u for u in rematch_votes.get('team1', []) if u not in (declined_player, replacement_player)]
    rematch_votes['team2'] = [u for u in rematch_votes.get('team2', []) if u not in (declined_player, replacement_player)]
    pending_rematch_replacements.pop(replacement_player, None)

    socketio.emit('rematch_player_replaced', {
        'declined_player': declined_player,
        'replacement_player': replacement_player,
        'team': payload.get('team')
    }, namespace='/')

@socketio.on('rematch_replace_player')
def handle_rematch_replace_player(data):
    """Compatibilite legacy: remplacement direct sans invitation."""
    username = get_socket_user()
    if not username:
        emit('error', {'message': 'Non authentifie'})
        return
    payload, err = _validate_rematch_replacement_request(username, data)
    if err:
        emit('error', {'message': err})
        return
    _apply_rematch_replacement(payload)
    _launch_rematch(current_game)

@socketio.on('rematch_invite_player')
def handle_rematch_invite_player(data):
    """Hote/admin: invite un joueur a remplacer puis attend sa reponse."""
    global pending_rematch_replacements
    username = get_socket_user()
    if not username:
        emit('error', {'message': 'Non authentifie'})
        return

    payload, err = _validate_rematch_replacement_request(username, data)
    if err:
        emit('error', {'message': err})
        return

    replacement_player = payload['replacement_player']
    if is_guest_player(replacement_player):
        _apply_rematch_replacement(payload)
        _launch_rematch(current_game)
        return

    # Nettoyer les invitations de rematch expirees.
    now_ts = _time.time()
    stale = [u for u, inv in list(pending_rematch_replacements.items()) if now_ts - inv.get('timestamp', 0) > 120]
    for u in stale:
        pending_rematch_replacements.pop(u, None)

    invite_payload = {
        'actor': username,
        'host': username,
        'declined_player': payload['declined_player'],
        'replacement_player': replacement_player,
        'timestamp': now_ts
    }
    pending_rematch_replacements[replacement_player] = invite_payload

    delivered = emit_to_user(replacement_player, 'rematch_replacement_invite', {
        'host': username,
        'declined_player': payload['declined_player'],
        'replacement_player': replacement_player
    })
    if not delivered:
        pending_rematch_replacements.pop(replacement_player, None)
        emit('error', {'message': 'Le joueur selectionne est hors ligne'})
        return

    emit('rematch_invite_sent', {
        'to': replacement_player,
        'declined_player': payload['declined_player']
    })

@socketio.on('rematch_replacement_response')
def handle_rematch_replacement_response(data):
    """Le joueur invite accepte/refuse sa participation au rematch."""
    username = get_socket_user()
    if not username:
        return
    invite = pending_rematch_replacements.get(username)
    if not invite:
        emit('error', {'message': "Aucune invitation de remplacement en attente"})
        return

    # Invitation expiree.
    if _time.time() - invite.get('timestamp', 0) > 120:
        pending_rematch_replacements.pop(username, None)
        emit('error', {'message': "Invitation expiree"})
        return

    accept = bool((data or {}).get('accept'))
    pending_rematch_replacements.pop(username, None)

    if not accept:
        emit_to_user(invite.get('actor'), 'rematch_invite_declined', {
            'replacement_player': username,
            'declined_player': invite.get('declined_player')
        })
        return

    payload, err = _validate_rematch_replacement_request(invite.get('actor'), invite)
    if err:
        emit_to_user(invite.get('actor'), 'rematch_invite_declined', {
            'replacement_player': username,
            'declined_player': invite.get('declined_player'),
            'reason': 'invalid'
        })
        emit('error', {'message': err})
        return

    _apply_rematch_replacement(payload)
    _launch_rematch(current_game)
@socketio.on('reset_game')
def handle_reset():
    global current_game, rematch_votes, servo_commands, rematch_pending
    username = get_socket_user()
    if not is_admin(username):
        emit('error', {'message': 'Admin requis'})
        return
    _reset_game_state()
    socketio.emit('game_reset', current_game, namespace='/')

@socketio.on('arduino_goal')
def handle_arduino_goal(data):
    if data.get('secret') != _get_arduino_secret():
        emit('error', {'message': 'Secret invalide'})
        return
    if not hasattr(handle_arduino_goal, 'last_goal_time'):
        handle_arduino_goal.last_goal_time = {}
    now = _time.time()
    # Anti double-but : 2 secondes minimum entre deux buts du même sid
    last = handle_arduino_goal.last_goal_time.get(request.sid, 0)
    if now - last < 2:
        return
    handle_arduino_goal.last_goal_time[request.sid] = now
    if not current_game.get('active'):
        return
    team = data.get('team')
    if team not in ['team1', 'team2']:
        return
    acquired = _goal_lock.acquire(blocking=False)
    if not acquired:
        return
    try:
        _process_goal(team)
    finally:
        _goal_lock.release()

@socketio.on('arduino_ping')
def handle_arduino_ping(data):
    emit('arduino_pong', {'status': 'ok'})

@socketio.on('get_game_state')
def handle_get_game_state(data):
    emit('game_state', {
        'active': current_game.get('active', False),
        'team1_score': current_game.get('team1_score', 0),
        'team2_score': current_game.get('team2_score', 0),
        'team1_players': current_game.get('team1_players', []),
        'team2_players': current_game.get('team2_players', []),
    })

# ── Sauvegarde des resultats ──────────────────────────────────

def save_game_results(game):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            winner_team = game.get('winner', 'team1')
            t1_players = game.get('team1_players', [])
            t2_players = game.get('team2_players', [])
            if isinstance(t1_players, str):
                try: t1_players = json.loads(t1_players) or []
                except Exception: t1_players = []
            if isinstance(t2_players, str):
                try: t2_players = json.loads(t2_players) or []
                except Exception: t2_players = []
            all_players = t1_players + t2_players
            real_players = [p for p in all_players if not is_guest_player(p)]
            t1_score = game.get("team1_score", 0)
            t2_score = game.get("team2_score", 0)
            total_players = len(t1_players) + len(t2_players)
            mode = '2v2' if total_players >= 4 else '1v1'

            # Score de l'équipe gagnante / perdante pour bonus domination
            if winner_team == 'team1':
                score_w, score_l = t1_score, t2_score
            else:
                score_w, score_l = t2_score, t1_score

            # Charger ELO + winstreak actuels
            elos = {}
            streaks = {}
            for player in real_players:
                q = ("SELECT elo, winstreak FROM users WHERE username = %s"
                     if USE_POSTGRES else
                     "SELECT elo, winstreak FROM users WHERE username = ?")
                cur.execute(q, (player,))
                row = row_to_dict(cur.fetchone()) or {}
                elos[player]    = row.get('elo') or 1000
                streaks[player] = row.get('winstreak') or 0

            winners = [p for p in real_players if
                       (p in t1_players and winner_team == 'team1') or
                       (p in t2_players and winner_team == 'team2')]
            losers  = [p for p in real_players if p not in winners]

            new_elos    = dict(elos)
            elo_deltas_w = {}
            elo_deltas_l = {}

            if winners and losers:
                avg_w = sum(elos.get(p, 1000) for p in winners) / len(winners)
                avg_l = sum(elos.get(p, 1000) for p in losers)  / len(losers)
                # Winstreak moyen de l'équipe gagnante pour le bonus
                avg_streak_w = sum(streaks.get(p, 0) for p in winners) / len(winners)
                new_w_elo, new_l_elo, delta_w, delta_l = compute_elo(
                    avg_w, avg_l,
                    winner_streak=avg_streak_w,
                    score_w=score_w, score_l=score_l
                )
                for p in winners:
                    new_elos[p] = max(800, round(elos.get(p, 1000) + (new_w_elo - avg_w)))
                    elo_deltas_w[p] = new_elos[p] - elos.get(p, 1000)
                for p in losers:
                    new_elos[p] = max(800, round(elos.get(p, 1000) + (new_l_elo - avg_l)))
                    elo_deltas_l[p] = new_elos[p] - elos.get(p, 1000)

            # Sauvegarder les résultats + mettre à jour winstreak
            new_streaks = {}
            for player in real_players:
                player_score  = t1_score if player in t1_players else t2_score
                new_elo       = new_elos.get(player, elos.get(player, 1000))
                is_winner     = player in winners

                if is_winner:
                    new_streak = streaks.get(player, 0) + 1
                else:
                    new_streak = 0
                new_streaks[player] = new_streak

                if USE_POSTGRES:
                    cur.execute("""
                        UPDATE users
                        SET total_games = total_games + 1,
                            total_wins  = total_wins  + %s,
                            winstreak   = %s,
                            elo         = %s
                        WHERE username = %s
                    """, (1 if is_winner else 0, new_streak, new_elo, player))
                    if player_score > 0:
                        cur.execute("INSERT INTO scores (username, score) VALUES (%s, %s)", (player, player_score))
                        cur.execute("UPDATE users SET total_goals = total_goals + %s WHERE username = %s", (player_score, player))
                else:
                    cur.execute("""
                        UPDATE users
                        SET total_games = total_games + 1,
                            total_wins  = total_wins  + ?,
                            winstreak   = ?,
                            elo         = ?
                        WHERE username = ?
                    """, (1 if is_winner else 0, new_streak, new_elo, player))
                    if player_score > 0:
                        cur.execute("INSERT INTO scores (username, score) VALUES (?, ?)", (player, player_score))
                        cur.execute("UPDATE users SET total_goals = total_goals + ? WHERE username = ?", (player_score, player))

            t1_json = json.dumps(t1_players)
            t2_json = json.dumps(t2_players)
            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO games (team1_players, team2_players, team1_score, team2_score, winner, mode, started_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (t1_json, t2_json, t1_score, t2_score, winner_team, mode, game.get('started_by'))
                )
            else:
                cur.execute(
                    "INSERT INTO games (team1_players, team2_players, team1_score, team2_score, winner, mode, started_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (t1_json, t2_json, t1_score, t2_score, winner_team, mode, game.get('started_by'))
                )
            conn.commit()
            logger.info("Résultats sauvegardés (ELO v2 + winstreak)")

            # ── Vérification du rang pour la quête top1 ──
            rank_map = {}
            try:
                q_rank = ("SELECT username FROM users WHERE username NOT IN ('Joueur1','Joueur2','Joueur3') ORDER BY elo DESC"
                          if USE_POSTGRES else
                          "SELECT username FROM users WHERE username NOT IN ('Joueur1','Joueur2','Joueur3') ORDER BY elo DESC")
                cur.execute(q_rank)
                ranked = [row_to_dict(r)['username'] for r in cur.fetchall()]
                for i, u in enumerate(ranked):
                    rank_map[u] = i + 1
            except Exception:
                pass

            # ── Vérification des quêtes pour chaque joueur ──
            all_newly_completed = {}
            for player in real_players:
                new_elo    = new_elos.get(player, elos.get(player, 1000))
                new_streak = new_streaks.get(player, 0)
                is_winner  = player in winners
                # Charger total_games / total_goals / total_wins mis à jour
                q_pdata = ("SELECT total_games, total_goals, total_wins FROM users WHERE username=%s"
                           if USE_POSTGRES else
                           "SELECT total_games, total_goals, total_wins FROM users WHERE username=?")
                cur.execute(q_pdata, (player,))
                prow = row_to_dict(cur.fetchone()) or {}
                player_data = {
                    "elo":        new_elo,
                    "total_wins": prow.get("total_wins") or 0,
                    "total_games": prow.get("total_games") or 0,
                    "total_goals": prow.get("total_goals") or 0,
                    "winstreak":  new_streak,
                    "is_winner":  is_winner,
                    "score_w":    score_w,
                    "score_l":    score_l,
                    "rank":       rank_map.get(player, 99),
                    # Remontada : gagner alors qu'on perdait 0-5 (score adverse ≥5 avant dernier but)
                    # On ne peut pas savoir exactement, on simule via score_l élevé et victoire
                    "remontada":  is_winner and score_l >= 5,
                }
                completed_quests = check_and_unlock_quests(player, conn, cur, player_data)
                conn.commit()
                if completed_quests:
                    all_newly_completed[player] = completed_quests

            # ── Émettre les changements ELO enrichis ──
            elo_changes = []
            for player in real_players:
                old_elo    = elos.get(player, 1000)
                new_elo    = new_elos.get(player, old_elo)
                delta      = new_elo - old_elo
                old_tier   = elo_tier(old_elo)[0]
                new_tier_data = elo_tier(new_elo)
                new_tier   = new_tier_data[0]
                new_tier_icon = new_tier_data[1]
                tier_up    = (old_tier != new_tier and delta > 0)
                tier_down  = (old_tier != new_tier and delta < 0)
                is_winner  = player in winners
                streak     = new_streaks.get(player, 0)
                # Calcul du multiplicateur winstreak pour l'affichage
                prev_streak = streaks.get(player, 0)
                streak_mult = min(1.0 + (prev_streak * 0.15), 2.0) if is_winner and prev_streak > 0 else 1.0
                elo_changes.append({
                    "player":       player,
                    "old_elo":      old_elo,
                    "new_elo":      new_elo,
                    "delta":        delta,
                    "is_winner":    is_winner,
                    "tier_up":      tier_up,
                    "tier_down":    tier_down,
                    "new_tier":     new_tier,
                    "new_tier_icon": new_tier_icon,
                    "winstreak":    streak,
                    "streak_mult":  round(streak_mult, 2),
                    "score_w":      score_w,
                    "score_l":      score_l,
                    "quests_completed": all_newly_completed.get(player, []),
                })
            socketio.emit('elo_updated', {"changes": elo_changes}, namespace='/')
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.error(f"Erreur save_game_results: {e}")



# ── Point d'entree WSGI ───────────────────────────────────────
# Commande : gunicorn --config gunicorn_config.py app:app

