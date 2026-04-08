"""Servico de alertas e monitoramento — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.database import get_db
from config import (
    ALERT_INACTIVE_DAYS,
    ALERT_CERT_EXPIRY_DAYS,
    ALERT_TRACK_OVERDUE_DAYS,
    DISCORD_WEBHOOK_ACADEMY,
)


# ---------------------------------------------------------------------------
# Verificacoes de alerta
# ---------------------------------------------------------------------------

async def check_inactive_users():
    """
    Verifica SDRs sem acesso ha ALERT_INACTIVE_DAYS dias.
    Cria alerta vermelho e notifica via Discord.
    """
    db = await get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ALERT_INACTIVE_DAYS)).isoformat()

    cursor = await db.execute(
        """SELECT u.id, u.name
           FROM users u
           WHERE u.role='colaborador' AND u.is_active=1
             AND (
               SELECT MAX(created_at) FROM access_log WHERE user_id=u.id
             ) < ? OR (
               SELECT COUNT(*) FROM access_log WHERE user_id=u.id
             ) = 0""",
        (cutoff,),
    )
    inativos = await cursor.fetchall()

    for user in inativos:
        # Verifica se ja existe alerta nao resolvido igual
        cursor = await db.execute(
            """SELECT id FROM alerts
               WHERE user_id=? AND type='inatividade' AND resolved_at IS NULL""",
            (user["id"],),
        )
        if await cursor.fetchone():
            continue

        msg = (
            f"SDR {user['name']} sem acesso ha mais de {ALERT_INACTIVE_DAYS} dias. "
            f"Acionar gestor para verificar o que aconteceu."
        )
        await _create_alert(
            user_id=user["id"],
            alert_type="inatividade",
            severity="vermelho",
            title=f"Inatividade Critica — {user['name']}",
            message=msg,
        )
        await _send_discord(
            f":red_circle: **Inatividade VR Academy** — {user['name']} sem acesso ha {ALERT_INACTIVE_DAYS}+ dias."
        )

    if inativos:
        print(f"[ALERT] {len(inativos)} SDRs inativos identificados.")


async def check_expiring_certifications():
    """
    Verifica certificacoes vencendo nos proximos ALERT_CERT_EXPIRY_DAYS dias.
    Cria alerta amarelo.
    """
    db = await get_db()
    soon = (datetime.now(timezone.utc) + timedelta(days=ALERT_CERT_EXPIRY_DAYS)).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        """SELECT c.id, c.user_id, u.name, c.name AS cert_name, c.expires_at
           FROM certifications c JOIN users u ON u.id = c.user_id
           WHERE c.expires_at IS NOT NULL AND c.expires_at <= ?
             AND c.expires_at > ? AND c.revoked_at IS NULL""",
        (soon, now),
    )
    certs = await cursor.fetchall()

    for cert in certs:
        cursor = await db.execute(
            """SELECT id FROM alerts
               WHERE user_id=? AND type='certificacao_vencendo' AND resolved_at IS NULL""",
            (cert["user_id"],),
        )
        if await cursor.fetchone():
            continue

        dias = (
            datetime.fromisoformat(cert["expires_at"].replace("Z", "+00:00")) -
            datetime.now(timezone.utc)
        ).days

        msg = (
            f"Certificacao '{cert['cert_name']}' vence em {dias} dias. "
            f"Renovar antes de {cert['expires_at'][:10]}."
        )
        await _create_alert(
            user_id=cert["user_id"],
            alert_type="certificacao_vencendo",
            severity="amarelo",
            title=f"Certificacao Vencendo — {cert['name']}",
            message=msg,
        )

    if certs:
        print(f"[ALERT] {len(certs)} certificacoes vencendo em breve.")


async def check_overdue_tracks():
    """
    Verifica trilhas obrigatorias atrasadas.
    Bloqueia recebimento de leads apos ALERT_TRACK_OVERDUE_DAYS dias de atraso.
    """
    db = await get_db()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cursor = await db.execute(
        """SELECT e.user_id, e.track_id, e.due_date, u.name,
                  t.name AS track_name, t.is_required
           FROM enrollments e
           JOIN users u ON u.id = e.user_id
           JOIN tracks t ON t.id = e.track_id
           WHERE e.status NOT IN ('concluida')
             AND e.due_date < ?
             AND t.is_required=1
             AND u.role='colaborador' AND u.is_active=1""",
        (now_str,),
    )
    atrasados = await cursor.fetchall()

    for row in atrasados:
        try:
            due = datetime.strptime(row["due_date"], "%Y-%m-%d")
            hoje = datetime.now()
            dias_atraso = (hoje - due).days
        except Exception:
            dias_atraso = 0

        # Alerta de atraso
        cursor = await db.execute(
            """SELECT id FROM alerts
               WHERE user_id=? AND type='trilha_atrasada' AND resolved_at IS NULL""",
            (row["user_id"],),
        )
        if not await cursor.fetchone():
            await _create_alert(
                user_id=row["user_id"],
                alert_type="trilha_atrasada",
                severity="amarelo" if dias_atraso < ALERT_TRACK_OVERDUE_DAYS else "vermelho",
                title=f"Trilha Atrasada — {row['name']}",
                message=f"Trilha '{row['track_name']}' venceu ha {dias_atraso} dia(s). Prazo: {row['due_date']}.",
            )

        # Bloqueio de leads apos ALERT_TRACK_OVERDUE_DAYS
        if dias_atraso >= ALERT_TRACK_OVERDUE_DAYS:
            cursor = await db.execute(
                "SELECT id FROM lead_blocks WHERE user_id=? AND track_id=? AND is_active=1",
                (row["user_id"], row["track_id"]),
            )
            if not await cursor.fetchone():
                await db.execute(
                    """INSERT INTO lead_blocks (user_id, reason, track_id)
                       VALUES (?, ?, ?)""",
                    (
                        row["user_id"],
                        f"Trilha obrigatoria '{row['track_name']}' nao concluida apos {dias_atraso} dias",
                        row["track_id"],
                    ),
                )
                await _create_alert(
                    user_id=row["user_id"],
                    alert_type="bloqueio_leads",
                    severity="vermelho",
                    title=f"BLOQUEIO DE LEADS — {row['name']}",
                    message=(
                        f"SDR {row['name']} bloqueado para receber leads. "
                        f"Trilha '{row['track_name']}' atrasada {dias_atraso} dias."
                    ),
                )
                await _send_discord(
                    f":no_entry: **BLOQUEIO DE LEADS — VR Academy** — {row['name']} bloqueado. "
                    f"Trilha '{row['track_name']}' atrasada {dias_atraso} dias."
                )

    if atrasados:
        await db.commit()
        print(f"[ALERT] {len(atrasados)} SDRs com trilha atrasada.")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

async def _create_alert(
    user_id: int,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    channels: str = "discord",
):
    db = await get_db()
    await db.execute(
        """INSERT INTO alerts (user_id, type, severity, title, message, channels)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, alert_type, severity, title, message, channels),
    )
    await db.commit()


async def _send_discord(message: str):
    """Envia mensagem via Discord webhook."""
    if not DISCORD_WEBHOOK_ACADEMY:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                DISCORD_WEBHOOK_ACADEMY,
                json={"content": message, "username": "VR Academy"},
            )
    except Exception as e:
        print(f"[ALERT] Erro ao enviar Discord: {e}")


# ---------------------------------------------------------------------------
# Runner completo — chamado pelo scheduler
# ---------------------------------------------------------------------------

async def run_all_checks():
    """Executa todas as verificacoes de alerta."""
    print("[ALERT] Iniciando verificacao de alertas...")
    try:
        await check_inactive_users()
    except Exception as e:
        print(f"[ALERT] Erro em check_inactive_users: {e}")
    try:
        await check_expiring_certifications()
    except Exception as e:
        print(f"[ALERT] Erro em check_expiring_certifications: {e}")
    try:
        await check_overdue_tracks()
    except Exception as e:
        print(f"[ALERT] Erro em check_overdue_tracks: {e}")
    print("[ALERT] Verificacao concluida.")
