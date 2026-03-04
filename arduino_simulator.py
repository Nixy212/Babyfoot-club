#!/usr/bin/env python3
"""
SIMULATEUR ARDUINO — Baby-Foot Club
Simule le comportement de l'Arduino WiFi qui contrôle les servos et détecte les buts.
Utilise exclusivement les endpoints REST /api/arduino/*.

Usage:
    python arduino_simulator.py \\
        --url https://babyfoot-club.onrender.com \\
        --game-id 1 \\
        --token <TOKEN> \\
        [--simulate-goals] \\
        [--goal-interval 10] \\
        [--log-level DEBUG]

Fonctionnalités :
  - Boucle principale : récupère et exécute les commandes en file d'attente
  - Heartbeat périodique toutes les 15 secondes
  - Reconnexion automatique en cas de coupure réseau
  - Anti-doublon : ne ré-exécute jamais une commande déjà confirmée
  - Simulation optionnelle de buts aléatoires pour les tests
"""

import requests
import time
import argparse
import logging
import sys
import random
from threading import Thread, Event

# ── Logging configurable ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# SIMULATEUR
# ══════════════════════════════════════════════════════════════

class ArduinoSimulator:
    """Simule un Arduino WiFi connecté au site Baby-Foot"""

    HEARTBEAT_INTERVAL = 15      # secondes entre deux heartbeats
    COMMAND_POLL_INTERVAL = 0.5  # secondes entre deux polls de commande
    RECONNECT_DELAY = 5          # secondes avant de retenter après erreur réseau
    SERVO_ACTION_DELAY = 0.3     # temps simulé d'exécution servo (secondes)

    def __init__(self, base_url: str, game_id: int, token: str):
        self.base_url = base_url.rstrip("/")
        self.game_id = game_id
        self.token = token

        self.stop_event = Event()
        self.running = False

        # État local simulé
        self.servo1_locked = True
        self.servo2_locked = True

        # Suivi des commandes déjà exécutées (idempotence locale)
        self._executed_locally: set = set()

        # Statistiques
        self.stats = {
            "commands_received": 0,
            "commands_executed": 0,
            "commands_skipped_duplicate": 0,
            "goals_sent": 0,
            "heartbeats_sent": 0,
            "errors": 0,
            "reconnects": 0,
        }

        logger.info("=" * 55)
        logger.info("  🤖 SIMULATEUR ARDUINO — Baby-Foot Club")
        logger.info("=" * 55)
        logger.info(f"  URL      : {self.base_url}")
        logger.info(f"  Game ID  : {self.game_id}")
        logger.info(f"  Token    : {self.token[:12]}...")
        logger.info("=" * 55)

    # ── Requêtes HTTP ─────────────────────────────────────────

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: dict = None) -> dict | None:
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.get(url, headers=self._headers(), params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            logger.warning(f"⏱  Timeout GET {endpoint}")
            self.stats["errors"] += 1
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 Connexion perdue GET {endpoint}")
            self.stats["errors"] += 1
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                logger.error("🔑 Token invalide ou expiré — arrêt simulateur")
                self.stop()
            elif code == 429:
                logger.warning(f"⏳ Rate-limited sur {endpoint}, attente...")
                time.sleep(2)
            else:
                logger.error(f"HTTP {code} sur GET {endpoint}: {e.response.text[:200]}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"❌ Erreur GET {endpoint}: {e}")
            self.stats["errors"] += 1
        return None

    def _post(self, endpoint: str, data: dict = None) -> dict | None:
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.post(url, headers=self._headers(), json=data or {}, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            logger.warning(f"⏱  Timeout POST {endpoint}")
            self.stats["errors"] += 1
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 Connexion perdue POST {endpoint}")
            self.stats["errors"] += 1
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                logger.error("🔑 Token invalide ou expiré — arrêt simulateur")
                self.stop()
            elif code == 429:
                body = {}
                try:
                    body = e.response.json()
                except Exception:
                    pass
                retry_after = body.get("retry_after", 2)
                logger.warning(f"⏳ Rate-limited sur {endpoint}, attente {retry_after}s")
                time.sleep(float(retry_after))
            else:
                logger.error(f"HTTP {code} sur POST {endpoint}: {e.response.text[:200]}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"❌ Erreur POST {endpoint}: {e}")
            self.stats["errors"] += 1
        return None

    # ── Actions serveur ───────────────────────────────────────

    def get_command(self) -> dict | None:
        resp = self._get("/api/arduino/get_command", {"game_id": self.game_id})
        if resp:
            self.stats["commands_received"] += 1
        return resp

    def confirm_command(self, command_id: str) -> bool:
        resp = self._post("/api/arduino/confirm_command", {
            "game_id": self.game_id,
            "command_id": command_id
        })
        return resp is not None

    def send_goal(self, team: str) -> dict | None:
        resp = self._post("/api/arduino/update_score", {
            "game_id": self.game_id,
            "event": "goal",
            "team": team
        })
        if resp:
            self.stats["goals_sent"] += 1
            scores = resp.get("scores", {})
            logger.info(f"⚽ But accepté — {team} | Score : {scores.get('team1', '?')}-{scores.get('team2', '?')}")
            if resp.get("game_ended"):
                winner = resp.get("winner", "?")
                logger.info(f"🏆 Partie terminée ! Vainqueur : {winner}")
        return resp

    def get_game_state(self) -> dict | None:
        return self._get("/api/arduino/game_state", {"game_id": self.game_id})

    def send_heartbeat(self) -> bool:
        resp = self._post("/api/arduino/heartbeat", {"game_id": self.game_id})
        if resp:
            self.stats["heartbeats_sent"] += 1
            logger.debug(f"💓 Heartbeat OK — pending={resp.get('pending_count', 0)}")
        return resp is not None

    # ── Exécution des commandes ───────────────────────────────

    def _execute_action(self, action: str, command_id: str) -> bool:
        """Simule physiquement une action servo et confirme au serveur"""

        # Idempotence locale : ne ré-exécuter jamais deux fois la même commande
        if command_id in self._executed_locally:
            logger.debug(f"↩️  Commande déjà exécutée localement: {command_id}")
            self.stats["commands_skipped_duplicate"] += 1
            return True

        logger.info(f"⚙️  Exécution: {action} (id={command_id})")

        if action in ("unlock_servo", "unlock_ball"):
            time.sleep(self.SERVO_ACTION_DELAY)
            self.servo1_locked = False
            self.servo2_locked = False
            logger.info("  → 🔓 Servos déverrouillés")

        elif action in ("lock_servo", "lock_ball"):
            time.sleep(self.SERVO_ACTION_DELAY)
            self.servo1_locked = True
            self.servo2_locked = True
            logger.info("  → 🔒 Servos verrouillés")

        else:
            logger.warning(f"  ⚠️  Action inconnue ignorée: {action}")
            # Confirmer quand même pour éviter que la commande reste bloquée
            self._executed_locally.add(command_id)
            self.confirm_command(command_id)
            return True

        # Confirmer auprès du serveur
        if self.confirm_command(command_id):
            self._executed_locally.add(command_id)
            self.stats["commands_executed"] += 1
            logger.info(f"  ✅ Confirmé: {command_id}")
            return True
        else:
            logger.error(f"  ❌ Confirmation échouée: {command_id} (sera réessayé)")
            return False

    # ── Reconnexion ───────────────────────────────────────────

    def reconnect(self):
        """Récupère l'état complet et exécute toutes les actions en attente"""
        logger.info("🔄 Reconnexion — récupération de l'état...")
        self.stats["reconnects"] += 1

        state = self.get_game_state()
        if not state:
            logger.error("❌ Impossible de récupérer l'état — nouvelle tentative dans 5s")
            return False

        # Synchroniser l'état local
        self.servo1_locked = state.get("ball_locked", True)
        self.servo2_locked = state.get("ball_locked", True)
        t1 = state.get("score_team1", 0)
        t2 = state.get("score_team2", 0)
        logger.info(f"📊 État récupéré — Score : {t1}-{t2} | Balle verrouillée : {self.servo1_locked}")

        # Exécuter les actions en attente dans l'ordre
        pending = state.get("pending_actions", [])
        if pending:
            logger.info(f"⚠️  {len(pending)} action(s) en attente à exécuter")
            for action_data in pending:
                self._execute_action(
                    action_data.get("action", ""),
                    action_data.get("command_id", "")
                )
        else:
            logger.info("✅ Aucune action en attente")

        return True

    # ── Boucles ───────────────────────────────────────────────

    def _command_loop(self):
        """Boucle principale : poll commandes + heartbeat périodique"""
        last_heartbeat = time.time()
        consecutive_errors = 0

        while self.running and not self.stop_event.is_set():
            # Heartbeat
            if time.time() - last_heartbeat >= self.HEARTBEAT_INTERVAL:
                if not self.send_heartbeat():
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        logger.warning(f"🔌 {consecutive_errors} erreurs consécutives — tentative de reconnexion")
                        self.reconnect()
                        consecutive_errors = 0
                else:
                    consecutive_errors = 0
                last_heartbeat = time.time()

            # Poll commande
            cmd = self.get_command()
            if cmd:
                action = cmd.get("action", "none")
                command_id = cmd.get("command_id")
                if action != "none" and command_id:
                    self._execute_action(action, command_id)
                    consecutive_errors = 0
            else:
                consecutive_errors += 1

            if self.stop_event.wait(self.COMMAND_POLL_INTERVAL):
                break

    def _goal_simulation_loop(self, interval: float = 10.0):
        """Simule des buts aléatoires à intervalle régulier (pour tests)"""
        logger.info(f"🎲 Simulation de buts activée (interval ~{interval}s)")
        while self.running and not self.stop_event.is_set():
            wait = random.uniform(interval * 0.7, interval * 1.3)
            if self.stop_event.wait(wait):
                break
            # Ne simuler que si les servos sont déverrouillés
            if not self.servo1_locked or not self.servo2_locked:
                team = random.choice(["team1", "team2"])
                logger.info(f"🎯 [Simulation] But pour {team}")
                resp = self.send_goal(team)
                if resp and resp.get("game_ended"):
                    logger.info("🏁 Partie terminée — simulation de buts arrêtée")
                    break

    def _stats_loop(self):
        """Affiche les statistiques toutes les 60 secondes"""
        while self.running and not self.stop_event.is_set():
            if self.stop_event.wait(60):
                break
            self._print_stats()

    # ── Cycle de vie ──────────────────────────────────────────

    def start(self, simulate_goals: bool = False, goal_interval: float = 10.0):
        """Démarre le simulateur"""
        logger.info("🚀 Démarrage du simulateur...")
        self.running = True

        # Récupérer l'état initial
        success = self.reconnect()
        if not success:
            logger.warning("⚠️  Démarrage sans état initial — le simulateur va quand même tourner")

        # Boucle principale
        Thread(target=self._command_loop, daemon=True, name="cmd-loop").start()

        # Boucle simulation buts (optionnelle)
        if simulate_goals:
            Thread(
                target=self._goal_simulation_loop,
                args=(goal_interval,),
                daemon=True,
                name="goal-sim"
            ).start()

        # Boucle stats
        Thread(target=self._stats_loop, daemon=True, name="stats-loop").start()

        logger.info("✅ Simulateur actif — Ctrl+C pour arrêter")

        try:
            while self.running and not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Arrête proprement le simulateur"""
        if not self.running:
            return
        logger.info("\n🛑 Arrêt du simulateur...")
        self.running = False
        self.stop_event.set()
        self._print_stats()

    def _print_stats(self):
        s = self.stats
        logger.info("─" * 45)
        logger.info("📊  STATISTIQUES SIMULATEUR")
        logger.info(f"    Commandes reçues       : {s['commands_received']}")
        logger.info(f"    Commandes exécutées    : {s['commands_executed']}")
        logger.info(f"    Doublons ignorés       : {s['commands_skipped_duplicate']}")
        logger.info(f"    Buts envoyés           : {s['goals_sent']}")
        logger.info(f"    Heartbeats             : {s['heartbeats_sent']}")
        logger.info(f"    Reconnexions           : {s['reconnects']}")
        logger.info(f"    Erreurs                : {s['errors']}")
        servo_state = "🔒 Verrouillés" if self.servo1_locked else "🔓 Déverrouillés"
        logger.info(f"    Servos                 : {servo_state}")
        logger.info("─" * 45)


# ══════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Simulateur Arduino pour Baby-Foot Club",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Mode standard (attente de commandes du serveur)
  python arduino_simulator.py --url https://babyfoot-club.onrender.com --game-id 1 --token TOKEN

  # Mode test avec buts aléatoires toutes les ~10s
  python arduino_simulator.py --url http://127.0.0.1:5000 --game-id 1 --token TOKEN --simulate-goals

  # Mode debug verbeux avec buts rapides (toutes les 5s)
  python arduino_simulator.py --url http://127.0.0.1:5000 --game-id 1 --token TOKEN \\
      --simulate-goals --goal-interval 5 --log-level DEBUG
"""
    )
    parser.add_argument("--url",            required=True,        help="URL du serveur")
    parser.add_argument("--game-id",        type=int, required=True, help="ID de la partie")
    parser.add_argument("--token",          required=True,        help="Token Bearer généré au démarrage de la partie")
    parser.add_argument("--simulate-goals", action="store_true",  help="Simuler des buts aléatoires")
    parser.add_argument("--goal-interval",  type=float, default=10.0, help="Intervalle moyen entre buts simulés (secondes, défaut: 10)")
    parser.add_argument("--log-level",      default="INFO",       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Niveau de log (défaut: INFO)")

    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    sim = ArduinoSimulator(args.url, args.game_id, args.token)
    try:
        sim.start(simulate_goals=args.simulate_goals, goal_interval=args.goal_interval)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
