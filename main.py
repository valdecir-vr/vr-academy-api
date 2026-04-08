"""VR Academy — FastAPI Backend Server."""

import sys
import os

# Garante que server/ esta no Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SERVER_HOST, SERVER_PORT
from db.database import init_db, close_db
from db.seed import run_seed
from services.alert_service import run_all_checks
from services.gamification_service import update_weekly_ranking, update_monthly_points


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")


def setup_scheduler():
    """Configura jobs do scheduler."""

    # Verificacao de alertas — a cada 4 horas
    scheduler.add_job(
        run_all_checks,
        CronTrigger(hour="8,12,16,20", minute=0),
        id="alert_checks",
        name="Verificacao de Alertas",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Ranking semanal — segunda-feira 07:00
    scheduler.add_job(
        update_weekly_ranking,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="weekly_ranking",
        name="Ranking Semanal",
        replace_existing=True,
    )

    # Zerar pontos mensais — dia 1, 06:00
    scheduler.add_job(
        update_monthly_points,
        CronTrigger(day=1, hour=6, minute=0),
        id="monthly_points",
        name="Reset Mensal de Pontos",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[SCHEDULER] {len(scheduler.get_jobs())} jobs configurados.")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown do servidor."""
    print("[VR Academy] Inicializando...")
    await init_db()
    await run_seed()
    setup_scheduler()
    print(f"[VR Academy] Servidor pronto em {SERVER_HOST}:{SERVER_PORT}")
    yield
    scheduler.shutdown(wait=False)
    await close_db()
    print("[VR Academy] Servidor encerrado.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="VR Academy API",
    description="Backend do dashboard de treinamento VR Advogados — SDRs Pre-Vendas",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permite frontend local e LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.tracks import router as tracks_router
from routes.progress import router as progress_router
from routes.gamification import router as gamification_router
from routes.dashboard import router as dashboard_router
from routes.prescriptions import router as prescriptions_router

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(tracks_router, prefix="/api")
app.include_router(progress_router, prefix="/api")
app.include_router(gamification_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(prescriptions_router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
@app.get("/api/health")
async def health():
    """Health check — verifica se o servidor esta operacional."""
    from db.database import get_db
    try:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        db_ok = True
    except Exception as e:
        total_users = 0
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "vr-academy",
        "version": "1.0.0",
        "db_ok": db_ok,
        "total_users": total_users,
        "scheduler_running": scheduler.running,
    }


@app.get("/")
async def root():
    return {
        "service": "VR Academy API",
        "docs": "/docs",
        "health": "/health",
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
