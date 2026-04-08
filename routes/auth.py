"""Rotas de autenticacao — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from db.database import get_db
from auth_utils import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Login com email + senha. Retorna access token (15min) e refresh token (7d)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, name, email, password_hash, role, is_active FROM users WHERE email=?",
        (req.email.lower().strip(),),
    )
    user = await cursor.fetchone()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha invalidos")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Conta inativa. Contate o administrador.")

    # Log de acesso
    await db.execute(
        "INSERT INTO access_log (user_id, action, metadata) VALUES (?, 'login', '{}')",
        (user["id"],),
    )
    await db.commit()

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"], user["role"])

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    """Renova o access token usando o refresh token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de refresh invalido")

    user_id = int(payload["sub"])
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, role, is_active FROM users WHERE id=?", (user_id,)
    )
    user = await cursor.fetchone()
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Usuario invalido ou inativo")

    new_access = create_access_token(user["id"], user["role"])
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Retorna dados do usuario autenticado."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT u.id, u.name, u.email, u.role, u.phone, u.hire_date, u.discord_id,
                  COALESCE(up.total_points, 0) AS total_points,
                  COALESCE(up.week_points, 0) AS week_points,
                  COALESCE(up.month_points, 0) AS month_points,
                  COALESCE(up.level, 1) AS level,
                  COALESCE(s.current_streak, 0) AS current_streak,
                  COALESCE(s.longest_streak, 0) AS longest_streak
           FROM users u
           LEFT JOIN user_points up ON up.user_id = u.id
           LEFT JOIN streaks s ON s.user_id = u.id
           WHERE u.id=?""",
        (current_user["id"],),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return dict(row)


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Altera a senha do usuario logado."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT password_hash FROM users WHERE id=?", (current_user["id"],)
    )
    row = await cursor.fetchone()

    if not verify_password(req.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    new_hash = hash_password(req.new_password)
    await db.execute(
        "UPDATE users SET password_hash=? WHERE id=?", (new_hash, current_user["id"])
    )
    await db.commit()
    return {"message": "Senha alterada com sucesso"}
