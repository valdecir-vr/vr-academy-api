"""Rotas de gamificacao — ranking, badges, streaks — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends

from db.database import get_db
from auth_utils import get_current_user, require_admin_or_gestor

router = APIRouter(tags=["gamification"])


@router.get("/ranking")
async def ranking_publico(current_user: dict = Depends(get_current_user)):
    """
    Ranking para colaboradores: retorna top 5 com nomes reais + posicao propria (anonima).
    Admin/gestor ve o ranking completo com nomes.
    """
    db = await get_db()

    if current_user["role"] in ("admin", "gestor"):
        # Ranking completo
        cursor = await db.execute(
            """SELECT u.id, u.name, up.total_points, up.week_points, up.level,
                      s.current_streak,
                      RANK() OVER (ORDER BY up.total_points DESC) AS rank_pos
               FROM users u
               JOIN user_points up ON up.user_id = u.id
               LEFT JOIN streaks s ON s.user_id = u.id
               WHERE u.role='colaborador' AND u.is_active=1
               ORDER BY up.total_points DESC""",
        )
        rows = await cursor.fetchall()
        return {"ranking": [dict(r) for r in rows], "tipo": "completo"}

    # Colaborador: top 5 com nomes + posicao propria
    cursor = await db.execute(
        """SELECT u.id, u.name, up.total_points, up.week_points, up.level,
                  s.current_streak,
                  RANK() OVER (ORDER BY up.total_points DESC) AS rank_pos
           FROM users u
           JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           WHERE u.role='colaborador' AND u.is_active=1
           ORDER BY up.total_points DESC""",
    )
    all_rows = [dict(r) for r in await cursor.fetchall()]

    top5 = all_rows[:5]

    # Posicao propria
    my_position = next(
        (r for r in all_rows if r["id"] == current_user["id"]), None
    )

    if my_position:
        my_pos_anonymous = {
            "rank_pos": my_position["rank_pos"],
            "total_points": my_position["total_points"],
            "week_points": my_position["week_points"],
            "level": my_position["level"],
            "current_streak": my_position["current_streak"],
            "nome": "Voce",
        }
    else:
        my_pos_anonymous = None

    return {
        "top5": top5,
        "minha_posicao": my_pos_anonymous,
        "tipo": "publico",
    }


@router.get("/ranking/full")
async def ranking_full(current_user: dict = Depends(require_admin_or_gestor)):
    """Ranking completo com nomes — somente admin/gestor."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT u.id, u.name, u.email,
                  up.total_points, up.week_points, up.month_points, up.level,
                  s.current_streak, s.longest_streak,
                  e.progress_pct AS track_progress, e.status AS track_status,
                  lb.is_active AS lead_blocked,
                  RANK() OVER (ORDER BY up.total_points DESC) AS rank_pos,
                  RANK() OVER (ORDER BY up.week_points DESC) AS rank_semana
           FROM users u
           JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           LEFT JOIN enrollments e ON e.user_id = u.id
           LEFT JOIN lead_blocks lb ON lb.user_id = u.id AND lb.is_active=1
           WHERE u.role='colaborador' AND u.is_active=1
           ORDER BY up.total_points DESC""",
    )
    rows = await cursor.fetchall()
    return {"ranking": [dict(r) for r in rows]}


@router.get("/badges")
async def list_badges(current_user: dict = Depends(get_current_user)):
    """Lista todos os badges disponiveis + quais o usuario ja conquistou."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT b.id, b.name, b.description, b.category, b.points_value, b.is_secret,
                  ub.earned_at,
                  CASE WHEN ub.id IS NOT NULL THEN 1 ELSE 0 END AS earned
           FROM badges b
           LEFT JOIN user_badges ub ON ub.badge_id = b.id AND ub.user_id = ?
           WHERE b.is_secret = 0 OR ub.id IS NOT NULL
           ORDER BY b.category, b.name""",
        (current_user["id"],),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/streaks/my")
async def my_streak(current_user: dict = Depends(get_current_user)):
    """Retorna streak atual e historico do usuario logado."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT current_streak, longest_streak, last_activity_date
           FROM streaks WHERE user_id=?""",
        (current_user["id"],),
    )
    row = await cursor.fetchone()
    if not row:
        return {"current_streak": 0, "longest_streak": 0, "last_activity_date": None}

    return dict(row)


@router.get("/points/history")
async def points_history(current_user: dict = Depends(get_current_user)):
    """Historico de transacoes de pontos do usuario logado (ultimas 50)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT amount, reason, description, created_at
           FROM point_transactions WHERE user_id=?
           ORDER BY created_at DESC LIMIT 50""",
        (current_user["id"],),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
