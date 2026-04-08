"""Rotas de dashboard por role — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException

from db.database import get_db
from auth_utils import get_current_user, require_admin, require_admin_or_gestor

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/admin")
async def dashboard_admin(current_user: dict = Depends(require_admin)):
    """
    Visao admin — todos os SDRs, semaforo de saude, metricas globais.
    Semaforo: Verde = progresso >= 70%, Amarelo = 30-70%, Vermelho = < 30% ou lead bloqueado.
    """
    db = await get_db()

    # Metricas globais
    cursor = await db.execute(
        """SELECT
            COUNT(DISTINCT u.id) AS total_sdrs,
            AVG(up.total_points) AS avg_points,
            AVG(e.progress_pct) AS avg_progress,
            SUM(CASE WHEN lb.is_active=1 THEN 1 ELSE 0 END) AS sdrs_bloqueados,
            SUM(CASE WHEN e.status='concluida' THEN 1 ELSE 0 END) AS trilhas_concluidas
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN enrollments e ON e.user_id = u.id
           LEFT JOIN lead_blocks lb ON lb.user_id = u.id AND lb.is_active=1
           WHERE u.role='colaborador' AND u.is_active=1""",
    )
    metricas = dict(await cursor.fetchone())

    # SDRs com semaforo
    cursor = await db.execute(
        """SELECT u.id, u.name, u.email,
                  up.total_points, up.week_points, up.level,
                  s.current_streak,
                  e.progress_pct, e.status AS track_status, e.due_date,
                  lb.is_active AS lead_blocked, lb.reason AS block_reason,
                  (SELECT created_at FROM access_log
                   WHERE user_id=u.id ORDER BY created_at DESC LIMIT 1) AS last_access,
                  (SELECT COUNT(*) FROM alerts
                   WHERE user_id=u.id AND resolved_at IS NULL) AS alertas_ativos
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           LEFT JOIN enrollments e ON e.user_id = u.id
           LEFT JOIN lead_blocks lb ON lb.user_id = u.id AND lb.is_active=1
           WHERE u.role='colaborador' AND u.is_active=1
           ORDER BY u.name""",
    )
    sdrs_rows = await cursor.fetchall()
    sdrs = []

    now = datetime.now(timezone.utc)
    for sdr in sdrs_rows:
        s = dict(sdr)

        # Calcular semaforo
        progress = s.get("progress_pct") or 0
        last_access_str = s.get("last_access")
        dias_sem_acesso = 999

        if last_access_str:
            try:
                last_dt = datetime.fromisoformat(last_access_str.replace("Z", "+00:00"))
                dias_sem_acesso = (now - last_dt).days
            except Exception:
                pass

        if s.get("lead_blocked") or progress < 30 or dias_sem_acesso >= 7:
            semaforo = "vermelho"
        elif progress < 70 or dias_sem_acesso >= 3:
            semaforo = "amarelo"
        else:
            semaforo = "verde"

        s["semaforo"] = semaforo
        s["dias_sem_acesso"] = dias_sem_acesso if dias_sem_acesso < 999 else None
        sdrs.append(s)

    # Resumo por semaforo
    resumo = {
        "verde": sum(1 for s in sdrs if s["semaforo"] == "verde"),
        "amarelo": sum(1 for s in sdrs if s["semaforo"] == "amarelo"),
        "vermelho": sum(1 for s in sdrs if s["semaforo"] == "vermelho"),
    }

    # Alertas abertos
    cursor = await db.execute(
        """SELECT a.id, a.user_id, u.name AS user_name, a.type, a.severity,
                  a.title, a.message, a.sent_at
           FROM alerts a JOIN users u ON u.id = a.user_id
           WHERE a.resolved_at IS NULL
           ORDER BY a.sent_at DESC LIMIT 20""",
    )
    alertas = [dict(r) for r in await cursor.fetchall()]

    return {
        "metricas_globais": metricas,
        "resumo_semaforo": resumo,
        "sdrs": sdrs,
        "alertas_recentes": alertas,
    }


@router.get("/gestor")
async def dashboard_gestor(current_user: dict = Depends(require_admin_or_gestor)):
    """
    Visao gestor — squad de colaboradores, alertas, ranking completo.
    Gestor ve apenas colaboradores. Admin ve todos.
    """
    db = await get_db()

    # Colaboradores
    cursor = await db.execute(
        """SELECT u.id, u.name,
                  up.total_points, up.week_points, up.level,
                  s.current_streak,
                  e.progress_pct, e.status AS track_status, e.due_date,
                  lb.is_active AS lead_blocked,
                  (SELECT created_at FROM access_log
                   WHERE user_id=u.id ORDER BY created_at DESC LIMIT 1) AS last_access,
                  (SELECT COUNT(*) FROM lesson_progress
                   WHERE user_id=u.id AND status='concluida') AS licoes_concluidas,
                  RANK() OVER (ORDER BY up.total_points DESC) AS rank_geral
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           LEFT JOIN enrollments e ON e.user_id = u.id
           LEFT JOIN lead_blocks lb ON lb.user_id = u.id AND lb.is_active=1
           WHERE u.role='colaborador' AND u.is_active=1
           ORDER BY up.total_points DESC""",
    )
    colaboradores = [dict(r) for r in await cursor.fetchall()]

    # Alertas do squad (nao resolvidos)
    cursor = await db.execute(
        """SELECT a.id, a.user_id, u.name AS user_name, a.type, a.severity,
                  a.title, a.message, a.sent_at, a.read_at
           FROM alerts a JOIN users u ON u.id = a.user_id
           WHERE a.resolved_at IS NULL AND u.role='colaborador'
           ORDER BY CASE a.severity WHEN 'vermelho' THEN 1 WHEN 'amarelo' THEN 2 ELSE 3 END,
                    a.sent_at DESC""",
    )
    alertas = [dict(r) for r in await cursor.fetchall()]

    # Metricas do squad
    total = len(colaboradores)
    concluiram = sum(1 for c in colaboradores if c.get("track_status") == "concluida")
    bloqueados = sum(1 for c in colaboradores if c.get("lead_blocked"))
    avg_progress = (
        sum(c.get("progress_pct") or 0 for c in colaboradores) / total if total else 0
    )

    return {
        "metricas": {
            "total_sdrs": total,
            "concluiram_trilha": concluiram,
            "bloqueados_leads": bloqueados,
            "progresso_medio": round(avg_progress, 1),
        },
        "colaboradores": colaboradores,
        "alertas": alertas,
    }


@router.get("/colaborador")
async def dashboard_colaborador(current_user: dict = Depends(get_current_user)):
    """Visao SDR — proprio desempenho, prescrições pendentes, streak, badges."""
    db = await get_db()
    user_id = current_user["id"]

    # Pontos e nivel
    cursor = await db.execute(
        "SELECT total_points, week_points, month_points, level FROM user_points WHERE user_id=?",
        (user_id,),
    )
    points = dict(await cursor.fetchone() or {})

    # Streak
    cursor = await db.execute(
        "SELECT current_streak, longest_streak, last_activity_date FROM streaks WHERE user_id=?",
        (user_id,),
    )
    streak_row = await cursor.fetchone()
    streak = dict(streak_row) if streak_row else {}

    # Matriculas
    cursor = await db.execute(
        """SELECT e.track_id, t.name, e.status, e.progress_pct, e.due_date,
                  e.started_at, e.completed_at
           FROM enrollments e JOIN tracks t ON t.id = e.track_id
           WHERE e.user_id=?""",
        (user_id,),
    )
    enrollments = [dict(r) for r in await cursor.fetchall()]

    # Proximas licoes (nao iniciadas ou em andamento)
    cursor = await db.execute(
        """SELECT l.id, l.name, l.content_type, l.duration_minutes, l.points_value,
                  m.name AS module_name, t.name AS track_name,
                  COALESCE(lp.status, 'nao_iniciada') AS status
           FROM lessons l
           JOIN modules m ON m.id = l.module_id
           JOIN tracks t ON t.id = m.track_id
           JOIN enrollments e ON e.track_id = t.id AND e.user_id=?
           LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id=?
           WHERE COALESCE(lp.status, 'nao_iniciada') != 'concluida'
           ORDER BY t."order", m."order", l."order"
           LIMIT 5""",
        (user_id, user_id),
    )
    proximas = [dict(r) for r in await cursor.fetchall()]

    # Badges conquistados (ultimos 3)
    cursor = await db.execute(
        """SELECT b.name, b.description, b.category, ub.earned_at
           FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
           WHERE ub.user_id=? ORDER BY ub.earned_at DESC LIMIT 3""",
        (user_id,),
    )
    badges_recentes = [dict(r) for r in await cursor.fetchall()]

    # Prescrições pendentes
    cursor = await db.execute(
        """SELECT lp.id, m.name AS modulo, lp.reason, lp.priority, lp.created_at
           FROM learning_prescriptions lp JOIN modules m ON m.id = lp.module_id
           WHERE lp.user_id=? AND lp.status='pendente'
           ORDER BY lp.priority, lp.created_at DESC LIMIT 5""",
        (user_id,),
    )
    prescricoes = [dict(r) for r in await cursor.fetchall()]

    # Bloqueio de leads
    cursor = await db.execute(
        "SELECT reason, blocked_at FROM lead_blocks WHERE user_id=? AND is_active=1",
        (user_id,),
    )
    bloqueio = await cursor.fetchone()

    # Rank geral (posicao propria)
    cursor = await db.execute(
        """SELECT COUNT(*) + 1 AS minha_posicao
           FROM user_points up2
           WHERE up2.total_points > (
               SELECT total_points FROM user_points WHERE user_id=?
           ) AND up2.user_id IN (
               SELECT id FROM users WHERE role='colaborador' AND is_active=1
           )""",
        (user_id,),
    )
    rank_row = await cursor.fetchone()
    minha_posicao = rank_row[0] if rank_row else None

    return {
        "pontos": points,
        "streak": streak,
        "rank_geral": minha_posicao,
        "enrollments": enrollments,
        "proximas_licoes": proximas,
        "badges_recentes": badges_recentes,
        "prescricoes_pendentes": prescricoes,
        "lead_bloqueado": dict(bloqueio) if bloqueio else None,
    }


@router.get("/alerts")
async def dashboard_alerts(current_user: dict = Depends(get_current_user)):
    """
    Alertas ativos por role:
    - Admin/Gestor: todos os alertas nao resolvidos do squad
    - Colaborador: apenas os proprios alertas
    """
    db = await get_db()

    if current_user["role"] in ("admin", "gestor"):
        cursor = await db.execute(
            """SELECT a.id, a.user_id, u.name AS user_name, a.type, a.severity,
                      a.title, a.message, a.sent_at, a.read_at
               FROM alerts a JOIN users u ON u.id = a.user_id
               WHERE a.resolved_at IS NULL
               ORDER BY CASE a.severity WHEN 'vermelho' THEN 1 WHEN 'amarelo' THEN 2 ELSE 3 END,
                        a.sent_at DESC
               LIMIT 50""",
        )
    else:
        cursor = await db.execute(
            """SELECT id, type, severity, title, message, sent_at, read_at
               FROM alerts WHERE user_id=? AND resolved_at IS NULL
               ORDER BY sent_at DESC LIMIT 20""",
            (current_user["id"],),
        )

    rows = await cursor.fetchall()

    # Marca como lido
    if current_user["role"] == "colaborador":
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE alerts SET read_at=? WHERE user_id=? AND read_at IS NULL",
            (now, current_user["id"]),
        )
        await db.commit()

    return [dict(r) for r in rows]
