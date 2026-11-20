"""Configuration par variables d'environnement. Valeurs par défaut = installation personnelle GONA (Ryzen/iMac)."""
import os
from pathlib import Path

HOME = Path.home()
PROFILE_NAME = os.environ.get('GONA_MC_PROFILE_NAME', 'gpt5')
PROFILE = Path(os.environ.get('GONA_MC_PROFILE', str(HOME / '.hermes/profiles' / PROFILE_NAME)))
# jeton d'accès (fichier, jamais versionné)
TOKEN_FILE = Path(os.environ.get('GONA_MC_TOKEN_FILE', str(PROFILE / 'gona-mission-control/token')))
KANBAN_DB = Path(os.environ.get('HERMES_KANBAN_DB', str(HOME / '.hermes/kanban.db')))
HERMES_SRC = Path(os.environ.get('GONA_MC_HERMES_SRC', str(HOME / '.openclaw/workspace/hermes-agent')))
HERMES_CLI = os.environ.get('GONA_MC_HERMES_CLI', str(HOME / '.local/bin/hermes'))
# relais vers l'ancien dashboard (voix, envoi de messages Telegram) ; vide = désactivé
LEGACY_URL = os.environ.get('GONA_MC_LEGACY_URL', 'http://127.0.0.1:8790').rstrip('/')
LEGACY_TOKEN_FILE = Path(os.environ.get('GONA_MC_LEGACY_TOKEN_FILE', str(PROFILE / 'mission-control/token')))
MEDIA_EXTRA = tuple(Path(p) for p in os.environ.get('GONA_MC_MEDIA_ROOTS', '').split(':') if p)

# Backend du chat : 'telegram' (défaut, relais vers le gateway Telegram) ou 'api' (API locale Hermes, sans Telegram)
BACKEND = os.environ.get('GONA_MC_BACKEND', 'telegram').strip().lower()
HERMES_URL = os.environ.get('GONA_MC_HERMES_URL', 'http://127.0.0.1:8642')
HERMES_KEY_FILE = os.environ.get('GONA_MC_HERMES_KEY_FILE', '')
DATA_DIR = Path(os.environ.get('GONA_MC_DATA_DIR', str(PROFILE / 'gona-mission-control')))
