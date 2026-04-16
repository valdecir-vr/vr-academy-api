"""Rotas de trilhas de aprendizado — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db.database import get_db
from auth_utils import get_current_user, require_admin
from services.gate_service import get_modules_lock_status

router = APIRouter(prefix="/tracks", tags=["tracks"])


class TrackCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_required: bool = True
    due_in_days: int = 30
    order: int = 0


@router.get("")
async def list_tracks(current_user: dict = Depends(get_current_user)):
    """Lista trilhas com progresso do usuario logado."""
    db = await get_db()
    user_id = current_user["id"]

    cursor = await db.execute(
        """SELECT t.id, t.name, t.description, t.is_required, t.due_in_days, t."order",
                  t.is_active, t.created_at,
                  e.status AS enrollment_status, e.progress_pct,
                  e.started_at, e.due_date, e.completed_at, e.points_earned,
                  (SELECT COUNT(*) FROM modules m WHERE m.track_id = t.id AND m.is_active=1) AS total_modules,
                  (SELECT COUNT(*) FROM modules m
                   JOIN lessons l ON l.module_id = m.id
                   WHERE m.track_id = t.id AND m.is_active=1) AS total_lessons
           FROM tracks t
           LEFT JOIN enrollments e ON e.track_id = t.id AND e.user_id = ?
           WHERE t.is_active = 1
           ORDER BY t."order" """,
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/{id}")
async def get_track(id: int, current_user: dict = Depends(get_current_user)):
    """Retorna trilha com modulos e licoes, incluindo progresso do usuario."""
    db = await get_db()
    user_id = current_user["id"]

    # Trilha
    cursor = await db.execute(
        """SELECT t.id, t.name, t.description, t.is_required, t.due_in_days, t."order",
                  e.status AS enrollment_status, e.progress_pct,
                  e.started_at, e.due_date, e.completed_at
           FROM tracks t
           LEFT JOIN enrollments e ON e.track_id = t.id AND e.user_id = ?
           WHERE t.id=? AND t.is_active=1""",
        (user_id, id),
    )
    track = await cursor.fetchone()
    if not track:
        raise HTTPException(status_code=404, detail="Trilha nao encontrada")

    # Modulos
    cursor = await db.execute(
        """SELECT m.id, m.name, m.description, m."order", m.points_value,
                  m.estimated_minutes, m.crivo_area, m.is_required
           FROM modules m
           WHERE m.track_id=? AND m.is_active=1
           ORDER BY m."order" """,
        (id,),
    )
    modules_rows = await cursor.fetchall()
    modules = []

    # Compute lock status for all modules at once (optimized)
    lock_map = await get_modules_lock_status(user_id, id)

    for mod in modules_rows:
        mod_dict = dict(mod)

        # Lock status from gate service
        mod_lock = lock_map.get(mod["id"], {"unlocked": True, "reason": None})
        mod_dict["is_locked"] = not mod_lock["unlocked"]
        mod_dict["lock_reason"] = mod_lock.get("reason")

        # Licoes do modulo
        cursor = await db.execute(
            """SELECT l.id, l.name, l.description, l.content_type, l.content_url,
                      l.duration_minutes, l.points_value, l."order", l.is_required, l.passing_score,
                      lp.status AS progress_status, lp.score, lp.completed_at,
                      lp.time_spent_min, lp.points_earned, lp.attempts
               FROM lessons l
               LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id = ?
               WHERE l.module_id=?
               ORDER BY l."order" """,
            (user_id, mod["id"]),
        )
        lessons = [dict(r) for r in await cursor.fetchall()]

        # If module is locked, override lesson statuses
        if mod_dict["is_locked"]:
            for lesson in lessons:
                lesson["progress_status"] = "bloqueada"

        # Progresso do modulo
        done = sum(1 for l in lessons if l.get("progress_status") == "concluida")
        mod_dict["lessons"] = lessons
        mod_dict["lessons_total"] = len(lessons)
        mod_dict["lessons_done"] = done
        mod_dict["module_progress_pct"] = round(done / len(lessons) * 100 if lessons else 0, 1)

        modules.append(mod_dict)

    result = dict(track)
    result["modules"] = modules
    return result


@router.post("")
async def create_track(
    body: TrackCreate,
    current_user: dict = Depends(require_admin),
):
    """Cria nova trilha. Somente admin."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO tracks (name, description, is_required, due_in_days, "order")
           VALUES (?, ?, ?, ?, ?)""",
        (body.name, body.description, 1 if body.is_required else 0,
         body.due_in_days, body.order),
    )
    await db.commit()

    # Auto-matricular todos os colaboradores ativos
    due_date = (datetime.now() + timedelta(days=body.due_in_days)).strftime("%Y-%m-%d")
    cursor2 = await db.execute(
        "SELECT id FROM users WHERE role='colaborador' AND is_active=1"
    )
    sdrs = await cursor2.fetchall()
    for sdr in sdrs:
        await db.execute(
            """INSERT OR IGNORE INTO enrollments (user_id, track_id, status, due_date)
               VALUES (?, ?, 'pendente', ?)""",
            (sdr[0], cursor.lastrowid, due_date),
        )
    await db.commit()

    return {"message": "Trilha criada com sucesso", "id": cursor.lastrowid}
