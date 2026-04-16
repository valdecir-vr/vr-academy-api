"""Rotas de usuarios — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from db.database import get_db
from auth_utils import get_current_user, require_admin_or_gestor, require_admin, hash_password

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    name: str
    email: str
    role: str = "colaborador"
    phone: Optional[str] = ""
    hire_date: Optional[str] = None
    password: Optional[str] = None  # defaults to vr2026


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    discord_id: Optional[str] = None
    pipedrive_user_id: Optional[int] = None
    hire_date: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    new_password: Optional[str] = None


@router.post("")
async def create_user(
    body: UserCreate,
    current_user: dict = Depends(require_admin),
):
    """Cria novo usuario. Somente admin. Auto-matricula em trilhas obrigatorias."""
    db = await get_db()

    if body.role not in ("admin", "gestor", "colaborador"):
        raise HTTPException(status_code=400, detail="Role invalido")

    # Check duplicate
    cursor = await db.execute("SELECT id FROM users WHERE email=?", (body.email.lower().strip(),))
    if await cursor.fetchone():
        raise HTTPException(status_code=409, detail="Email ja cadastrado")

    from config import DEFAULT_PASSWORD
    pwd = body.password or DEFAULT_PASSWORD
    pwd_hash = hash_password(pwd)

    cursor = await db.execute(
        """INSERT INTO users (name, email, password_hash, role, phone, hire_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (body.name.strip(), body.email.lower().strip(), pwd_hash, body.role,
         body.phone or "", body.hire_date or ""),
    )
    new_id = cursor.lastrowid

    # Auto-enroll in required tracks
    if body.role == "colaborador":
        from datetime import datetime, timedelta
        cursor2 = await db.execute("SELECT id, due_in_days FROM tracks WHERE is_required=1 AND is_active=1")
        tracks = await cursor2.fetchall()
        for t in tracks:
            due = (datetime.now() + timedelta(days=t["due_in_days"])).strftime("%Y-%m-%d")
            await db.execute(
                "INSERT OR IGNORE INTO enrollments (user_id, track_id, status, due_date) VALUES (?, ?, 'pendente', ?)",
                (new_id, t["id"], due),
            )
        await db.execute("INSERT OR IGNORE INTO user_points (user_id) VALUES (?)", (new_id,))
        await db.execute("INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (new_id,))

    await db.commit()
    return {"message": "Usuario criado com sucesso", "id": new_id, "email": body.email.lower().strip()}


@router.get("")
async def list_users(
    role: Optional[str] = Query(None, description="Filtrar por role: admin|gestor|colaborador"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Busca por nome ou email"),
    current_user: dict = Depends(require_admin_or_gestor),
):
    """Lista usuarios com filtros opcionais. Admin ve todos; gestor ve apenas colaboradores."""
    db = await get_db()

    conditions = []
    params: list = []

    # Gestor so ve colaboradores
    if current_user["role"] == "gestor":
        conditions.append("u.role = 'colaborador'")

    if role:
        conditions.append("u.role = ?")
        params.append(role)

    if is_active is not None:
        conditions.append("u.is_active = ?")
        params.append(1 if is_active else 0)

    if search:
        conditions.append("(u.name LIKE ? OR u.email LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    cursor = await db.execute(
        f"""SELECT u.id, u.name, u.email, u.role, u.is_active, u.phone,
                   u.hire_date, u.pipedrive_user_id,
                   up.total_points, up.week_points, up.level,
                   s.current_streak,
                   e.status AS track_status, e.progress_pct,
                   lb.is_active AS lead_blocked
            FROM users u
            LEFT JOIN user_points up ON up.user_id = u.id
            LEFT JOIN streaks s ON s.user_id = u.id
            LEFT JOIN enrollments e ON e.user_id = u.id
            LEFT JOIN lead_blocks lb ON lb.user_id = u.id AND lb.is_active = 1
            {where}
            ORDER BY u.name""",
        params,
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/{id}")
async def get_user(id: int, current_user: dict = Depends(get_current_user)):
    """Retorna dados de um usuario. Admin/gestor ve qualquer um; colaborador ve apenas a si mesmo."""
    if current_user["role"] == "colaborador" and current_user["id"] != id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    db = await get_db()
    cursor = await db.execute(
        """SELECT u.id, u.name, u.email, u.role, u.is_active, u.phone,
                  u.hire_date, u.pipedrive_user_id, u.discord_id, u.created_at,
                  up.total_points, up.week_points, up.month_points, up.level,
                  s.current_streak, s.longest_streak, s.last_activity_date
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           WHERE u.id=?""",
        (id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return dict(row)


@router.get("/{id}/stats")
async def get_user_stats(id: int, current_user: dict = Depends(get_current_user)):
    """Retorna estatisticas consolidadas de um usuario."""
    if current_user["role"] == "colaborador" and current_user["id"] != id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    db = await get_db()

    # Dados basicos
    cursor = await db.execute(
        """SELECT u.id, u.name, u.role,
                  up.total_points, up.week_points, up.month_points, up.level,
                  s.current_streak, s.longest_streak
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           WHERE u.id=?""",
        (id,),
    )
    user = await cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    # Matriculas e progresso
    cursor = await db.execute(
        """SELECT e.track_id, t.name AS track_name, e.status, e.progress_pct,
                  e.started_at, e.due_date, e.completed_at, e.points_earned
           FROM enrollments e JOIN tracks t ON t.id = e.track_id
           WHERE e.user_id=?""",
        (id,),
    )
    enrollments = [dict(r) for r in await cursor.fetchall()]

    # Licoes concluidas
    cursor = await db.execute(
        "SELECT COUNT(*) FROM lesson_progress WHERE user_id=? AND status='concluida'", (id,)
    )
    lessons_done = (await cursor.fetchone())[0]

    # Badges
    cursor = await db.execute(
        """SELECT b.name, b.category, b.points_value, ub.earned_at
           FROM user_badges ub JOIN badges b ON b.id = ub.badge_id
           WHERE ub.user_id=? ORDER BY ub.earned_at DESC""",
        (id,),
    )
    badges = [dict(r) for r in await cursor.fetchall()]

    # Ultimo acesso
    cursor = await db.execute(
        "SELECT created_at FROM access_log WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
        (id,),
    )
    last_access_row = await cursor.fetchone()
    last_access = last_access_row[0] if last_access_row else None

    # Crivo — media dos scores
    cursor = await db.execute(
        """SELECT AVG(total_score) as avg_total, AVG(abertura) as avg_abertura,
                  AVG(qualificacao) as avg_qualificacao, AVG(objecoes) as avg_objecoes,
                  AVG(fechamento) as avg_fechamento, COUNT(*) as calls_audited
           FROM crivo_scores WHERE user_id=?""",
        (id,),
    )
    crivo = dict(await cursor.fetchone())

    # Bloqueio de leads
    cursor = await db.execute(
        "SELECT is_active, reason, blocked_at FROM lead_blocks WHERE user_id=? AND is_active=1",
        (id,),
    )
    block = await cursor.fetchone()

    return {
        "user": dict(user),
        "enrollments": enrollments,
        "lessons_completed": lessons_done,
        "badges": badges,
        "last_access": last_access,
        "crivo_avg": crivo,
        "lead_blocked": dict(block) if block else None,
    }


@router.put("/{id}")
async def update_user(
    id: int,
    body: UserUpdate,
    current_user: dict = Depends(require_admin),
):
    """Atualiza dados de um usuario. Somente admin."""
    db = await get_db()
    cursor = await db.execute("SELECT id FROM users WHERE id=?", (id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    fields = []
    params = []

    if body.name is not None:
        fields.append("name=?")
        params.append(body.name)
    if body.email is not None:
        fields.append("email=?")
        params.append(body.email.lower().strip())
    if body.phone is not None:
        fields.append("phone=?")
        params.append(body.phone)
    if body.discord_id is not None:
        fields.append("discord_id=?")
        params.append(body.discord_id)
    if body.pipedrive_user_id is not None:
        fields.append("pipedrive_user_id=?")
        params.append(body.pipedrive_user_id)
    if body.hire_date is not None:
        fields.append("hire_date=?")
        params.append(body.hire_date)
    if body.is_active is not None:
        fields.append("is_active=?")
        params.append(1 if body.is_active else 0)
    if body.role is not None:
        if body.role not in ("admin", "gestor", "colaborador"):
            raise HTTPException(status_code=400, detail="Role invalido")
        fields.append("role=?")
        params.append(body.role)
    if body.new_password is not None:
        fields.append("password_hash=?")
        params.append(hash_password(body.new_password))

    if not fields:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    params.append(id)
    await db.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id=?", params
    )
    await db.commit()
    return {"message": "Usuario atualizado com sucesso", "id": id}
