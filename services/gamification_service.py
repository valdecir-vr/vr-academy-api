"""Servico de gamificacao — pontos, badges, streaks, ranking — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, date, timedelta, timezone
from typing import List

from db.database import get_db
from config import (
    POINTS_LESSON_COMPLETE,
    POINTS_MODULE_COMPLETE,
    POINTS_TRACK_COMPLETE,
    POINTS_PERFECT_SCORE,
    STREAK_BONUS_POINTS,
)


# ---------------------------------------------------------------------------
# Pontos
# ---------------------------------------------------------------------------

async def award_lesson_points(
    user_id: int,
    points: int,
    reference_id: int,
    reason: str,
    description: str = "",
) -> int:
    """Adiciona pontos ao usuario e registra a transacao."""
    if points <= 0:
        return 0

    db = await get_db()

    # Garante que user_points existe
    await db.execute(
        "INSERT OR IGNORE INTO user_points (user_id) VALUES (?)", (user_id,)
    )

    # Atualiza pontos
    await db.execute(
        """UPDATE user_points
           SET total_points = total_points + ?,
               week_points  = week_points  + ?,
               month_points = month_points + ?,
               level        = MAX(1, (total_points + ?) / 100 + 1)
           WHERE user_id=?""",
        (points, points, points, points, user_id),
    )

    # Transacao
    await db.execute(
        """INSERT INTO point_transactions (user_id, amount, reason, reference_id, description)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, points, reason, reference_id, description),
    )

    await db.commit()
    return points


# ---------------------------------------------------------------------------
# Modulo concluido
# ---------------------------------------------------------------------------

async def check_module_completion(user_id: int, module_id: int) -> List[str]:
    """
    Verifica se o modulo foi concluido (todas as licoes obrigatorias aprovadas).
    Se sim, concede pontos do modulo e verifica badges relacionados.
    Retorna lista de nomes de badges conquistados.
    """
    db = await get_db()
    new_badges = []

    # Total de licoes obrigatorias do modulo
    cursor = await db.execute(
        "SELECT COUNT(*) FROM lessons WHERE module_id=? AND is_required=1", (module_id,)
    )
    total_required = (await cursor.fetchone())[0]
    if total_required == 0:
        return []

    # Licoes obrigatorias concluidas
    cursor = await db.execute(
        """SELECT COUNT(*) FROM lesson_progress lp
           JOIN lessons l ON l.id = lp.lesson_id
           WHERE lp.user_id=? AND lp.module_id=? AND l.is_required=1 AND lp.status='concluida'""",
        (user_id, module_id),
    )
    done = (await cursor.fetchone())[0]

    if done < total_required:
        return []

    # Busca dados do modulo
    cursor = await db.execute(
        "SELECT id, track_id, points_value, name, \"order\" FROM modules WHERE id=?",
        (module_id,),
    )
    mod = await cursor.fetchone()
    if not mod:
        return []

    # Concede pontos do modulo (apenas se ainda nao concedeu — verifica via transacao)
    cursor = await db.execute(
        "SELECT id FROM point_transactions WHERE user_id=? AND reason='conclusao_modulo' AND reference_id=?",
        (user_id, module_id),
    )
    if not await cursor.fetchone():
        await award_lesson_points(
            user_id, mod["points_value"], module_id,
            "conclusao_modulo", f"Modulo concluido: {mod['name']}"
        )

    # Badge: Primeiro Modulo
    cursor = await db.execute(
        """SELECT COUNT(*) FROM point_transactions
           WHERE user_id=? AND reason='conclusao_modulo'""",
        (user_id,),
    )
    modules_done = (await cursor.fetchone())[0]
    if modules_done >= 1:
        earned = await _award_badge_if_not_earned(user_id, "Primeiro Modulo")
        if earned:
            new_badges.append("Primeiro Modulo")

    # Badge: Pitch Perfeito (modulo Abertura — order 1 — nota media >= 90)
    if mod["order"] == 1:
        cursor = await db.execute(
            """SELECT AVG(score) FROM lesson_progress
               WHERE user_id=? AND module_id=? AND status='concluida'""",
            (user_id, module_id),
        )
        avg_score = (await cursor.fetchone())[0] or 0
        if avg_score >= 90:
            earned = await _award_badge_if_not_earned(user_id, "Pitch Perfeito")
            if earned:
                new_badges.append("Pitch Perfeito")

    # Badge: Mestre em Objecoes (modulo Objecoes — order 5 — nota media >= 90)
    if mod["order"] == 5:
        cursor = await db.execute(
            """SELECT AVG(score) FROM lesson_progress
               WHERE user_id=? AND module_id=? AND status='concluida'""",
            (user_id, module_id),
        )
        avg_score = (await cursor.fetchone())[0] or 0
        if avg_score >= 90:
            earned = await _award_badge_if_not_earned(user_id, "Mestre em Objecoes")
            if earned:
                new_badges.append("Mestre em Objecoes")

    return new_badges


# ---------------------------------------------------------------------------
# Trilha concluida
# ---------------------------------------------------------------------------

async def check_track_completion(user_id: int, module_id: int) -> List[str]:
    """
    Verifica se a trilha foi concluida apos conclusao de um modulo.
    Retorna lista de badges conquistados.
    """
    db = await get_db()
    new_badges = []

    # Encontra a trilha
    cursor = await db.execute(
        "SELECT track_id FROM modules WHERE id=?", (module_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return []
    track_id = row[0]

    # Total de modulos obrigatorios
    cursor = await db.execute(
        "SELECT COUNT(*) FROM modules WHERE track_id=? AND is_required=1 AND is_active=1",
        (track_id,),
    )
    total = (await cursor.fetchone())[0]
    if total == 0:
        return []

    # Modulos concluidos (todos os obrigatorios do modulo com licoes todas concluidas)
    cursor = await db.execute(
        """SELECT m.id FROM modules m
           WHERE m.track_id=? AND m.is_required=1 AND m.is_active=1
             AND (
               SELECT COUNT(*) FROM lessons l WHERE l.module_id=m.id AND l.is_required=1
             ) > 0
             AND (
               SELECT COUNT(*) FROM lesson_progress lp
               JOIN lessons l ON l.id=lp.lesson_id
               WHERE lp.user_id=? AND lp.module_id=m.id AND l.is_required=1 AND lp.status='concluida'
             ) >= (
               SELECT COUNT(*) FROM lessons l WHERE l.module_id=m.id AND l.is_required=1
             )""",
        (track_id, user_id),
    )
    done_modules = await cursor.fetchall()

    if len(done_modules) < total:
        return []

    # Trilha concluida! Atualizar enrollment
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """UPDATE enrollments SET status='concluida', completed_at=?, progress_pct=100
           WHERE user_id=? AND track_id=? AND status != 'concluida'""",
        (now, user_id, track_id),
    )

    # Pontos da trilha
    cursor = await db.execute("SELECT points_value FROM tracks WHERE id=?", (track_id,))
    # tracks nao tem points_value, usa POINTS_TRACK_COMPLETE
    cursor = await db.execute(
        "SELECT id FROM point_transactions WHERE user_id=? AND reason='conclusao_trilha' AND reference_id=?",
        (user_id, track_id),
    )
    if not await cursor.fetchone():
        await award_lesson_points(
            user_id, POINTS_TRACK_COMPLETE, track_id,
            "conclusao_trilha", "Trilha de Onboarding concluida!"
        )

        # Emitir certificacao
        cursor = await db.execute(
            "SELECT name FROM tracks WHERE id=?", (track_id,)
        )
        track_row = await cursor.fetchone()
        from datetime import date
        expires = (date.today() + timedelta(days=365)).isoformat()
        await db.execute(
            """INSERT INTO certifications (user_id, name, score, expires_at)
               VALUES (?, ?, 100, ?)""",
            (user_id, f"Certificacao — {track_row['name']}", expires),
        )
        await db.commit()

        # Badge SDR Certificado
        earned = await _award_badge_if_not_earned(user_id, "SDR Certificado")
        if earned:
            new_badges.append("SDR Certificado")

    # Desbloquear leads (remover bloqueio por esta trilha)
    await db.execute(
        """UPDATE lead_blocks SET is_active=0, unlocked_at=?
           WHERE user_id=? AND track_id=? AND is_active=1""",
        (now, user_id, track_id),
    )
    await db.commit()

    return new_badges


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------

async def update_streak(user_id: int) -> dict:
    """
    Atualiza streak do usuario. Incrementa se ultima atividade foi ontem ou hoje,
    reseta se mais de 1 dia de lacuna.
    Concede pontos de bonus e verifica badges de streak.
    """
    db = await get_db()

    await db.execute(
        "INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (user_id,)
    )
    await db.execute(
        "INSERT OR IGNORE INTO user_points (user_id) VALUES (?)", (user_id,)
    )

    cursor = await db.execute(
        "SELECT current_streak, longest_streak, last_activity_date FROM streaks WHERE user_id=?",
        (user_id,),
    )
    row = await cursor.fetchone()

    today = date.today()
    today_str = today.isoformat()

    current = row["current_streak"] if row else 0
    longest = row["longest_streak"] if row else 0
    last_str = row["last_activity_date"] if row else None

    if last_str == today_str:
        # Ja estudou hoje, nao incrementa
        return {"current_streak": current, "longest_streak": longest}

    if last_str:
        try:
            last_date = date.fromisoformat(last_str)
            delta = (today - last_date).days
        except ValueError:
            delta = 999
    else:
        delta = 0

    if delta <= 1:
        current += 1
    else:
        current = 1  # reset

    longest = max(longest, current)

    await db.execute(
        """UPDATE streaks SET current_streak=?, longest_streak=?, last_activity_date=?
           WHERE user_id=?""",
        (current, longest, today_str, user_id),
    )

    # Bonus de streak
    if delta <= 1:  # so se continua o streak (nao no reset)
        bonus = STREAK_BONUS_POINTS
        await db.execute(
            """UPDATE user_points
               SET total_points=total_points+?, week_points=week_points+?, month_points=month_points+?
               WHERE user_id=?""",
            (bonus, bonus, bonus, user_id),
        )
        await db.execute(
            """INSERT INTO point_transactions (user_id, amount, reason, description)
               VALUES (?, ?, 'bonus_streak', ?)""",
            (user_id, bonus, f"Bonus de streak dia {current}"),
        )

    await db.commit()

    # Badges de streak
    new_badges = []
    if current >= 7:
        earned = await _award_badge_if_not_earned(user_id, "Maratonista")
        if earned:
            new_badges.append("Maratonista")
    if current >= 30:
        earned = await _award_badge_if_not_earned(user_id, "30 Dias de Fogo")
        if earned:
            new_badges.append("30 Dias de Fogo")

    return {"current_streak": current, "longest_streak": longest, "new_badges": new_badges}


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

async def update_weekly_ranking():
    """
    Chamado pelo scheduler semanal.
    Atribui badge 'Estudante da Semana' ao usuario com mais week_points.
    Zera week_points de todos ao fim da semana.
    """
    db = await get_db()

    cursor = await db.execute(
        """SELECT user_id, week_points FROM user_points
           WHERE user_id IN (SELECT id FROM users WHERE role='colaborador' AND is_active=1)
           ORDER BY week_points DESC LIMIT 1""",
    )
    top = await cursor.fetchone()
    if top and top["week_points"] > 0:
        earned = await _award_badge_if_not_earned(top["user_id"], "Estudante da Semana")
        if earned:
            # Bonus de pontos pelo badge
            await db.execute(
                """UPDATE user_points SET total_points=total_points+100, month_points=month_points+100
                   WHERE user_id=?""",
                (top["user_id"],),
            )
            await db.execute(
                """INSERT INTO point_transactions (user_id, amount, reason, description)
                   VALUES (?, 100, 'badge_earned', 'Badge Estudante da Semana conquistado')""",
                (top["user_id"],),
            )

    # Zera week_points
    await db.execute("UPDATE user_points SET week_points=0")
    await db.commit()
    print("[GAMIFICATION] Ranking semanal atualizado. week_points zerados.")


async def update_monthly_points():
    """Zera month_points mensalmente."""
    db = await get_db()
    await db.execute("UPDATE user_points SET month_points=0")
    await db.commit()
    print("[GAMIFICATION] month_points zerados.")


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

async def _award_badge_if_not_earned(user_id: int, badge_name: str) -> bool:
    """Concede badge se o usuario ainda nao tem. Retorna True se foi concedido agora."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM badges WHERE name=?", (badge_name,))
    badge = await cursor.fetchone()
    if not badge:
        return False

    badge_id = badge[0]
    cursor = await db.execute(
        "SELECT id FROM user_badges WHERE user_id=? AND badge_id=?", (user_id, badge_id)
    )
    if await cursor.fetchone():
        return False  # ja tem

    await db.execute(
        "INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)", (user_id, badge_id)
    )

    # Pontos do badge
    cursor = await db.execute("SELECT points_value FROM badges WHERE id=?", (badge_id,))
    badge_points = (await cursor.fetchone())[0]
    if badge_points > 0:
        await db.execute(
            """UPDATE user_points
               SET total_points=total_points+?, week_points=week_points+?, month_points=month_points+?
               WHERE user_id=?""",
            (badge_points, badge_points, badge_points, user_id),
        )
        await db.execute(
            """INSERT INTO point_transactions (user_id, amount, reason, description)
               VALUES (?, ?, 'badge_earned', ?)""",
            (user_id, badge_points, f"Badge conquistado: {badge_name}"),
        )

    await db.commit()
    print(f"[GAMIFICATION] Badge '{badge_name}' concedido ao usuario {user_id}")
    return True
