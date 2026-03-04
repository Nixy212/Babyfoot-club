#!/usr/bin/env python3
"""
SIMULATEUR ARDUINO - Baby-Foot Club
Simule le comportement de l'Arduino WiFi qui contrôle les servos et détecte les buts

Usage:
    python arduino_simulator.py --url https://ton-site.onrender.com --game-id 1 --token TON_TOKEN

Mode test local:
    python arduino_simulator.py --url http://127.0.0.1:5000 --game-id 1 --token test123
"""

import requests
import time
import argparse
import logging
import sys
from threading import Thread, Event
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ArduinoSimulator:
    """Simule un Arduino WiFi connecté au site Baby-Foot"""
    
    def __init__(self, base_url, game_id, token):
        self.base_url = base_url.rstrip('/')
        self.game_id = game_id
        self.token = token
        self.running = False
        self.stop_event = Event()
        
        # État local du simulateur
        self.servo1_locked = True  # Servo équipe 1
        self.servo2_locked = True  # Servo équipe 2
        self.ball_detected = False
        
        # Statistiques
        self.commands_received = 0
        self.commands_executed = 0
        self.goals_sent = 0
        self.errors = 0
        
        logger.info(f"Simulateur Arduino initialisé")
        logger.info(f"URL: {self.base_url}")
        logger.info(f"Game ID: {self.game_id}")
        logger.info(f"Token: {self.token[:10]}...")
    
    def _make_request(self, method, endpoint, data=None):
        """Effectue une requête HTTP avec gestion d'erreur"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=data, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sur {endpoint}")
            self.errors += 1
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Erreur de connexion à {endpoint}")
            self.errors += 1
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Token invalide ou expiré")
            else:
                logger.error(f"Erreur HTTP {e.response.status_code}: {e.response.text}")
            self.errors += 1
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            self.errors += 1
            return None
    
    def get_command(self):
        """Récupère la prochaine commande depuis le serveur"""
        response = self._make_request(
            "GET",
            "/api/arduino/get_command",
            {"game_id": self.game_id}
        )
        
        if response:
            self.commands_received += 1
        
        return response
    
    def confirm_command(self, command_id):
        """Confirme l'exécution d'une commande"""
        response = self._make_request(
            "POST",
            "/api/arduino/confirm_command",
            {"game_id": self.game_id, "command_id": command_id}
        )
        
        return response is not None
    
    def send_goal(self, team):
        """Envoie un but au serveur"""
        response = self._make_request(
            "POST",
            "/api/arduino/update_score",
            {
                "game_id": self.game_id,
                "event": "goal",
                "team": team
            }
        )
        
        if response:
            self.goals_sent += 1
            logger.info(f"⚽ But envoyé pour {team}: {response.get('new_score', {})}")
        
        return response
    
    def get_game_state(self):
        """Récupère l'état complet de la partie"""
        return self._make_request(
            "GET",
            "/api/arduino/game_state",
            {"game_id": self.game_id}
        )
    
    def send_heartbeat(self):
        """Envoie un heartbeat pour maintenir la connexion"""
        return self._make_request(
            "POST",
            "/api/arduino/heartbeat",
            {"game_id": self.game_id}
        )
    
    def execute_command(self, action, command_id):
        """Simule l'exécution d'une commande"""
        logger.info(f"🔧 Exécution: {action} (id={command_id})")
        
        if action == "unlock_ball":
            self.servo1_locked = False
            self.servo2_locked = False
            logger.info("  → Servos déverrouillés")
            time.sleep(0.5)  # Simule le temps d'exécution du servo
        
        elif action == "lock_ball":
            self.servo1_locked = True
            self.servo2_locked = True
            logger.info("  → Servos verrouillés")
            time.sleep(0.5)
        
        else:
            logger.warning(f"  → Action inconnue: {action}")
            return False
        
        # Confirmer l'exécution
        if self.confirm_command(command_id):
            self.commands_executed += 1
            logger.info(f"  ✅ Commande confirmée")
            return True
        else:
            logger.error(f"  ❌ Échec de confirmation")
            return False
    
    def simulate_ball_detection(self):
        """Simule la détection aléatoire d'une balle (pour tests)"""
        while self.running and not self.stop_event.is_set():
            # Attendre entre 5 et 15 secondes
            wait_time = random.uniform(5, 15)
            if self.stop_event.wait(wait_time):
                break
            
            # Si les servos sont déverrouillés, simuler un but aléatoire
            if not self.servo1_locked or not self.servo2_locked:
                team = random.choice(["team1", "team2"])
                logger.info(f"🎯 Capteur simulé: But détecté pour {team}")
                self.send_goal(team)
    
    def command_loop(self):
        """Boucle principale de récupération et exécution des commandes"""
        heartbeat_counter = 0
        
        while self.running and not self.stop_event.is_set():
            # Récupérer une commande
            command_data = self.get_command()
            
            if command_data and command_data.get("action") != "none":
                action = command_data.get("action")
                command_id = command_data.get("command_id")
                
                # Exécuter la commande
                self.execute_command(action, command_id)
            
            # Heartbeat tous les 10 cycles (~5 secondes)
            heartbeat_counter += 1
            if heartbeat_counter >= 10:
                self.send_heartbeat()
                heartbeat_counter = 0
            
            # Attendre avant la prochaine vérification
            if self.stop_event.wait(0.5):
                break
    
    def reconnect(self):
        """Simule une reconnexion après coupure réseau"""
        logger.info("🔄 Reconnexion...")
        
        # Récupérer l'état complet de la partie
        state = self.get_game_state()
        
        if state:
            logger.info(f"État récupéré: {state}")
            
            # Synchroniser l'état local
            self.servo1_locked = state.get("ball_locked", True)
            self.servo2_locked = state.get("ball_locked", True)
            
            # Exécuter les actions en attente
            pending = state.get("pending_actions", [])
            if pending:
                logger.info(f"⚠️ {len(pending)} action(s) en attente")
                for action_data in pending:
                    self.execute_command(
                        action_data["action"],
                        action_data["command_id"]
                    )
            else:
                logger.info("✅ Aucune action en attente")
        else:
            logger.error("❌ Échec de récupération de l'état")
    
    def start(self, simulate_goals=False):
        """Démarre le simulateur"""
        logger.info("🚀 Démarrage du simulateur...")
        self.running = True
        
        # Récupérer l'état initial
        self.reconnect()
        
        # Démarrer la boucle de commandes dans un thread
        command_thread = Thread(target=self.command_loop, daemon=True)
        command_thread.start()
        
        # Démarrer la simulation de buts si activée
        if simulate_goals:
            logger.info("🎲 Mode simulation de buts activé")
            goal_thread = Thread(target=self.simulate_ball_detection, daemon=True)
            goal_thread.start()
        
        logger.info("✅ Simulateur démarré")
        logger.info("Appuyez sur Ctrl+C pour arrêter")
        
        # Afficher les stats périodiquement
        try:
            while self.running:
                time.sleep(10)
                self.print_stats()
        except KeyboardInterrupt:
            logger.info("\n🛑 Arrêt demandé...")
            self.stop()
    
    def stop(self):
        """Arrête le simulateur"""
        self.running = False
        self.stop_event.set()
        logger.info("Simulateur arrêté")
        self.print_stats()
    
    def print_stats(self):
        """Affiche les statistiques"""
        logger.info("=" * 50)
        logger.info(f"📊 STATISTIQUES")
        logger.info(f"  Commandes reçues: {self.commands_received}")
        logger.info(f"  Commandes exécutées: {self.commands_executed}")
        logger.info(f"  Buts envoyés: {self.goals_sent}")
        logger.info(f"  Erreurs: {self.errors}")
        logger.info(f"  État servos: {'🔒 Verrouillés' if self.servo1_locked else '🔓 Déverrouillés'}")
        logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Simulateur Arduino pour Baby-Foot Club")
    parser.add_argument('--url', required=True, help="URL du site (ex: https://ton-site.onrender.com)")
    parser.add_argument('--game-id', type=int, required=True, help="ID de la partie")
    parser.add_argument('--token', required=True, help="Token d'authentification")
    parser.add_argument('--simulate-goals', action='store_true', help="Simuler des buts aléatoires")
    
    args = parser.parse_args()
    
    simulator = ArduinoSimulator(args.url, args.game_id, args.token)
    
    try:
        simulator.start(simulate_goals=args.simulate_goals)
    except KeyboardInterrupt:
        logger.info("\nArrêt...")
        simulator.stop()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
