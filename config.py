"""VR Academy — Configuracoes do servidor."""

import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "academy.db")

# AiOS root para importar _config.py
AIOS_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
AIOS_TOOLS_DIR = os.path.join(AIOS_ROOT, "tools", "autonomous")

# Importar tokens do AiOS
sys.path.insert(0, AIOS_TOOLS_DIR)
try:
    from _config import (
        PD_TOKEN,
        DISCORD_WEBHOOK_ALERTAS,
        DISCORD_WEBHOOK_VENDAS,
        DISCORD_WEBHOOK_LEADERSHIP,
        DISCORD_WEBHOOK_PEOPLE,
        DISCORD_WEBHOOK_RANKING,
    )
except ImportError:
    PD_TOKEN = os.environ.get("PIPEDRIVE_API_TOKEN", "")
    DISCORD_WEBHOOK_ALERTAS = os.environ.get("DISCORD_WEBHOOK_ALERTAS", "")
    DISCORD_WEBHOOK_VENDAS = os.environ.get("DISCORD_WEBHOOK_VENDAS", "")
    DISCORD_WEBHOOK_LEADERSHIP = os.environ.get("DISCORD_WEBHOOK_LEADERSHIP", "")
    DISCORD_WEBHOOK_PEOPLE = os.environ.get("DISCORD_WEBHOOK_PEOPLE", "")
    DISCORD_WEBHOOK_RANKING = os.environ.get("DISCORD_WEBHOOK_RANKING", "")

# Server
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8421

# JWT
JWT_SECRET = os.environ.get("ACADEMY_JWT_SECRET", "vr-academy-vr-advogados-2026-secure")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRE_MINUTES = 15
JWT_REFRESH_EXPIRE_DAYS = 7

# Senha padrao de todos os usuarios no seed
DEFAULT_PASSWORD = "vr2026"

# Gamification
POINTS_LESSON_COMPLETE = 10
POINTS_MODULE_COMPLETE = 50
POINTS_TRACK_COMPLETE = 200
POINTS_PERFECT_SCORE = 25   # bonus por nota 100%
STREAK_BONUS_POINTS = 5     # bonus por dia de streak

# Alertas
ALERT_INACTIVE_DAYS = 7    # dias sem acesso → alerta vermelho
ALERT_CERT_EXPIRY_DAYS = 30  # dias para vencer cert → alerta amarelo
ALERT_TRACK_OVERDUE_DAYS = 3  # dias apos prazo → bloqueio

# Discord — webhook especifico para academy
DISCORD_WEBHOOK_ACADEMY = DISCORD_WEBHOOK_PEOPLE  # reusa o canal de pessoas
