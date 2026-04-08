"""Rotas de progresso de licoes e modulos — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db.database import get_db
from auth_utils import get_current_user, require_admin_or_gestor
from services.gamification_service import (
    award_lesson_points,
    check_module_completion,
    check_track_completion,
    update_streak,
)

router = APIRouter(prefix="/progress", tags=["progress"])


class LessonCompleteRequest(BaseModel):
    score: Optional[float] = None  # Para quizzes (0-100)
    time_spent_min: Optional[float] = None


@router.post("/lesson/{lesson_id}/start")
async def start_lesson(lesson_id: int, current_user: dict = Depends(get_current_user)):
    """Marca o inicio de uma licao."""
    db = await get_db()

    # Verifica se a licao existe
    cursor = await db.execute(
        "SELECT id, module_id FROM lessons WHERE id=?", (lesson_id,)
    )
    lesson = await cursor.fetchone()
    if not lesson:
        raise HTTPException(status_code=404, detail="Licao nao encontrada")

    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO lesson_progress (user_id, lesson_id, module_id, status, started_at)
           VALUES (?, ?, ?, 'em_andamento', ?)
           ON CONFLICT(user_id, lesson_id) DO UPDATE SET
               status = CASE WHEN status = 'nao_iniciada' THEN 'em_andamento' ELSE status END,
               started_at = CASE WHEN started_at IS NULL THEN ? ELSE started_at END""",
        (current_user["id"], lesson_id, lesson["module_id"], now, now),
    )

    # Atualizar matricula para em_andamento se ainda pendente
    await db.execute(
        """UPDATE enrollments SET status='em_andamento', started_at=COALESCE(started_at, ?)
           WHERE user_id=? AND track_id=(
               SELECT track_id FROM modules WHERE id=?
           ) AND status='pendente'""",
        (now, current_user["id"], lesson["module_id"]),
    )

    # Log
    await db.execute(
        "INSERT INTO access_log (user_id, action, metadata) VALUES (?, 'lesson_start', ?)",
        (current_user["id"], f'{{"lesson_id": {lesson_id}}}'),
    )

    await db.commit()
    return {"message": "Licao iniciada", "lesson_id": lesson_id}


@router.post("/lesson/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: int,
    body: LessonCompleteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Marca conclusao de licao, calcula pontos e verifica badges."""
    db = await get_db()
    user_id = current_user["id"]

    # Busca licao
    cursor = await db.execute(
        "SELECT id, module_id, points_value, passing_score, content_type FROM lessons WHERE id=?",
        (lesson_id,),
    )
    lesson = await cursor.fetchone()
    if not lesson:
        raise HTTPException(status_code=404, detail="Licao nao encontrada")

    # Determina status
    score = body.score
    if lesson["content_type"] == "quiz" and score is not None:
        status = "concluida" if score >= lesson["passing_score"] else "reprovada"
    else:
        status = "concluida"
        score = score or 100.0

    now = datetime.now(timezone.utc).isoformat()
    time_spent = body.time_spent_min or 0.0

    # Incrementa tentativas
    cursor = await db.execute(
        "SELECT attempts, status FROM lesson_progress WHERE user_id=? AND lesson_id=?",
        (user_id, lesson_id),
    )
    existing = await cursor.fetchone()
    attempts = (existing["attempts"] + 1) if existing else 1

    # Pontos apenas na primeira aprovacao
    already_completed = existing and existing["status"] == "concluida"
    points_earned = 0
    if status == "concluida" and not already_completed:
        points_earned = lesson["points_value"]

    await db.execute(
        """INSERT INTO lesson_progress
               (user_id, lesson_id, module_id, status, score, attempts, started_at, completed_at,
                time_spent_min, points_earned)
           VALUES (?, ?, ?, ?, ?, ?, COALESCE(
               (SELECT started_at FROM lesson_progress WHERE user_id=? AND lesson_id=?), ?
           ), ?, ?, ?)
           ON CONFLICT(user_id, lesson_id) DO UPDATE SET
               status=?, score=?, attempts=?, completed_at=?,
               time_spent_min=time_spent_min+?, points_earned=CASE WHEN status != 'concluida' THEN ? ELSE points_earned END""",
        (user_id, lesson_id, lesson["module_id"], status, score, attempts,
         user_id, lesson_id, now, now, time_spent, points_earned,
         status, score, attempts, now, time_spent, points_earned),
    )

    await db.commit()

    # Gamification
    new_badges = []
    if status == "concluida" and not already_completed:
        await award_lesson_points(user_id, points_earned, lesson_id, "conclusao_licao")
        new_badges = await check_module_completion(user_id, lesson["module_id"])
        new_badges += await check_track_completion(user_id, lesson["module_id"])
        await update_streak(user_id)

    # Log
    await db.execute(
        "INSERT INTO access_log (user_id, action, metadata) VALUES (?, 'lesson_complete', ?)",
        (user_id, f'{{"lesson_id": {lesson_id}, "status": "{status}", "score": {score}}}'),
    )
    await db.commit()

    return {
        "lesson_id": lesson_id,
        "status": status,
        "score": score,
        "points_earned": points_earned,
        "new_badges": new_badges,
        "passed": status == "concluida",
    }


@router.get("/my")
async def my_progress(current_user: dict = Depends(get_current_user)):
    """Retorna progresso consolidado do usuario logado."""
    return await _get_user_progress(current_user["id"])


@router.get("/user/{user_id}")
async def user_progress(
    user_id: int,
    current_user: dict = Depends(require_admin_or_gestor),
):
    """Retorna progresso de um SDR especifico (admin/gestor)."""
    db = await get_db()
    cursor = await db.execute("SELECT id, role FROM users WHERE id=?", (user_id,))
    target = await cursor.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    # Gestor nao pode ver outros gestores ou admins
    if current_user["role"] == "gestor" and target["role"] != "colaborador":
        raise HTTPException(status_code=403, detail="Acesso negado")

    return await _get_user_progress(user_id)


# ─────────────────────────────────────────────────────────────
# SYNC — recebe progresso do localStorage da plataforma
# ─────────────────────────────────────────────────────────────

class SyncProgressRequest(BaseModel):
    progress: dict  # {"m1-1": {"completed": true, "date": "..."}, ...}


@router.post("/sync")
async def sync_progress(body: SyncProgressRequest, current_user: dict = Depends(get_current_user)):
    """Recebe progresso do localStorage da plataforma e sincroniza com o backend."""
    db = await get_db()
    user_id = current_user["id"]
    synced = 0

    # Mapeamento de prefixo para module_id do banco
    cursor = await db.execute(
        'SELECT id, "order" FROM modules ORDER BY "order"'
    )
    modules = await cursor.fetchall()
    module_map = {}
    for m in modules:
        module_map[m["order"]] = m["id"]

    # Mapeamento prefixo → module order
    prefix_to_order = {
        "m1": 1, "m2": 2, "m3": 3, "m4": 4,
        "m5": 5, "m6": 6, "m7": 7, "m8": 8,
    }

    for key, val in body.progress.items():
        if not val.get("completed"):
            continue

        # Parse key: "m1-2" → module prefix "m1", lesson order 2
        parts = key.split("-")
        if len(parts) != 2:
            continue
        prefix, lesson_order_str = parts[0], parts[1]
        if not lesson_order_str.isdigit():
            continue
        lesson_order = int(lesson_order_str)

        # Skip onboarding prefix "onb" for now (tracked separately)
        if prefix not in prefix_to_order:
            continue

        mod_order = prefix_to_order[prefix]
        mod_id = module_map.get(mod_order)
        if not mod_id:
            continue

        # Find the lesson
        cursor = await db.execute(
            'SELECT id FROM lessons WHERE module_id=? AND "order"=?',
            (mod_id, lesson_order),
        )
        lesson = await cursor.fetchone()
        if not lesson:
            continue

        completed_at = val.get("date", datetime.now(timezone.utc).isoformat())

        # Upsert lesson_progress
        await db.execute(
            """INSERT INTO lesson_progress (user_id, lesson_id, module_id, status, score, attempts, completed_at, points_earned)
               VALUES (?, ?, ?, 'concluida', 100, 1, ?, 0)
               ON CONFLICT(user_id, lesson_id) DO UPDATE SET
                   status='concluida',
                   completed_at=COALESCE(completed_at, ?)""",
            (user_id, lesson["id"], mod_id, completed_at, completed_at),
        )
        synced += 1

    # Recalcular progresso da enrollment
    cursor = await db.execute(
        "SELECT e.id, e.track_id FROM enrollments e WHERE e.user_id=?",
        (user_id,),
    )
    enrollments = await cursor.fetchall()
    for enr in enrollments:
        cursor = await db.execute(
            """SELECT COUNT(*) AS total FROM lessons l
               JOIN modules m ON m.id = l.module_id
               WHERE m.track_id=?""",
            (enr["track_id"],),
        )
        total = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            """SELECT COUNT(*) AS done FROM lesson_progress lp
               JOIN lessons l ON l.id = lp.lesson_id
               JOIN modules m ON m.id = l.module_id
               WHERE m.track_id=? AND lp.user_id=? AND lp.status='concluida'""",
            (enr["track_id"], user_id),
        )
        done = (await cursor.fetchone())["done"]
        pct = round((done / total * 100), 1) if total > 0 else 0

        await db.execute(
            "UPDATE enrollments SET progress_pct=?, status=CASE WHEN ?>=100 THEN 'concluida' ELSE 'em_andamento' END WHERE id=?",
            (pct, pct, enr["id"]),
        )

    # Log de acesso
    await db.execute(
        "INSERT INTO access_log (user_id, action, metadata) VALUES (?, 'sync_progress', ?)",
        (user_id, f'{{"synced": {synced}}}'),
    )

    await db.commit()
    await update_streak(user_id)

    return {"synced": synced, "message": f"{synced} licoes sincronizadas"}


@router.post("/track-access")
async def track_access(current_user: dict = Depends(get_current_user)):
    """Registra acesso/page view do usuario na plataforma."""
    db = await get_db()
    await db.execute(
        "INSERT INTO access_log (user_id, action, metadata) VALUES (?, 'page_view', '{}')",
        (current_user["id"],),
    )
    # Atualizar streak
    await update_streak(current_user["id"])
    await db.commit()
    return {"message": "Acesso registrado"}


@router.post("/identify")
async def identify_user(current_user: dict = Depends(get_current_user)):
    """Retorna dados do usuario logado para a plataforma identificar quem esta acessando."""
    return {
        "id": current_user["id"],
        "name": current_user["name"],
        "email": current_user["email"],
        "role": current_user["role"],
    }


async def _get_user_progress(user_id: int) -> dict:
    db = await get_db()

    # Matriculas
    cursor = await db.execute(
        """SELECT e.id, e.track_id, t.name AS track_name, e.status,
                  e.progress_pct, e.started_at, e.due_date, e.completed_at, e.points_earned
           FROM enrollments e JOIN tracks t ON t.id = e.track_id
           WHERE e.user_id=?""",
        (user_id,),
    )
    enrollments = [dict(r) for r in await cursor.fetchall()]

    # Progresso por licao (ultimas 20)
    cursor = await db.execute(
        """SELECT lp.lesson_id, l.name AS lesson_name, m.name AS module_name,
                  lp.status, lp.score, lp.completed_at, lp.time_spent_min, lp.points_earned
           FROM lesson_progress lp
           JOIN lessons l ON l.id = lp.lesson_id
           JOIN modules m ON m.id = lp.module_id
           WHERE lp.user_id=?
           ORDER BY lp.completed_at DESC LIMIT 20""",
        (user_id,),
    )
    recent_lessons = [dict(r) for r in await cursor.fetchall()]

    # Totais
    cursor = await db.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status='concluida' THEN 1 ELSE 0 END) AS done,
                  SUM(time_spent_min) AS total_time,
                  SUM(points_earned) AS total_points
           FROM lesson_progress WHERE user_id=?""",
        (user_id,),
    )
    totals = dict(await cursor.fetchone())

    return {
        "user_id": user_id,
        "enrollments": enrollments,
        "recent_lessons": recent_lessons,
        "totals": totals,
    }
