"""Rotas de prescricoes de aprendizado — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db.database import get_db
from auth_utils import get_current_user, require_admin_or_gestor

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


class PrescriptionCreate(BaseModel):
    user_id: int
    module_id: int
    reason: str
    priority: int = 1  # 1=alta, 2=media, 3=baixa
    crivo_id: Optional[int] = None


class PrescriptionStatusUpdate(BaseModel):
    status: str  # pendente | visualizada | concluida


@router.get("/my")
async def my_prescriptions(current_user: dict = Depends(get_current_user)):
    """Retorna prescricoes pendentes do usuario logado."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT lp.id, lp.module_id, m.name AS module_name,
                  m.crivo_area, lp.reason, lp.priority, lp.status,
                  lp.viewed_at, lp.created_at,
                  cs.total_score AS crivo_score, cs.call_date
           FROM learning_prescriptions lp
           JOIN modules m ON m.id = lp.module_id
           LEFT JOIN crivo_scores cs ON cs.id = lp.crivo_id
           WHERE lp.user_id=?
           ORDER BY lp.priority, lp.created_at DESC""",
        (current_user["id"],),
    )
    prescricoes = [dict(r) for r in await cursor.fetchall()]

    # Marcar como visualizadas
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """UPDATE learning_prescriptions SET viewed_at=?, status='visualizada'
           WHERE user_id=? AND status='pendente'""",
        (now, current_user["id"]),
    )
    await db.commit()

    return prescricoes


@router.post("")
async def create_prescription(
    body: PrescriptionCreate,
    current_user: dict = Depends(require_admin_or_gestor),
):
    """Cria prescrição de modulo para um SDR. Admin/gestor."""
    db = await get_db()

    # Verifica usuario
    cursor = await db.execute("SELECT id, role FROM users WHERE id=?", (body.user_id,))
    target = await cursor.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    # Gestor nao pode prescrever para admin/gestor
    if current_user["role"] == "gestor" and target["role"] != "colaborador":
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Verifica modulo
    cursor = await db.execute("SELECT id FROM modules WHERE id=?", (body.module_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Modulo nao encontrado")

    if body.priority not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Priority deve ser 1, 2 ou 3")

    cursor = await db.execute(
        """INSERT INTO learning_prescriptions
               (user_id, crivo_id, module_id, reason, priority)
           VALUES (?, ?, ?, ?, ?)""",
        (body.user_id, body.crivo_id, body.module_id, body.reason, body.priority),
    )
    await db.commit()

    return {"message": "Prescricao criada com sucesso", "id": cursor.lastrowid}


@router.put("/{id}/status")
async def update_prescription_status(
    id: int,
    body: PrescriptionStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Atualiza status de uma prescricao."""
    db = await get_db()

    cursor = await db.execute(
        "SELECT id, user_id FROM learning_prescriptions WHERE id=?", (id,)
    )
    presc = await cursor.fetchone()
    if not presc:
        raise HTTPException(status_code=404, detail="Prescricao nao encontrada")

    # Colaborador so pode atualizar as proprias
    if current_user["role"] == "colaborador" and presc["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Acesso negado")

    if body.status not in ("pendente", "visualizada", "concluida"):
        raise HTTPException(status_code=400, detail="Status invalido")

    now = datetime.now(timezone.utc).isoformat()
    extra = ""
    if body.status == "concluida":
        extra = f", completed_at='{now}'"

    await db.execute(
        f"UPDATE learning_prescriptions SET status=?{extra} WHERE id=?",
        (body.status, id),
    )
    await db.commit()

    return {"message": "Status atualizado", "id": id, "status": body.status}


@router.get("/user/{user_id}")
async def user_prescriptions(
    user_id: int,
    current_user: dict = Depends(require_admin_or_gestor),
):
    """Lista prescricoes de um SDR especifico (admin/gestor)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT lp.id, lp.module_id, m.name AS module_name,
                  lp.reason, lp.priority, lp.status,
                  lp.viewed_at, lp.completed_at, lp.created_at
           FROM learning_prescriptions lp
           JOIN modules m ON m.id = lp.module_id
           WHERE lp.user_id=?
           ORDER BY lp.priority, lp.created_at DESC""",
        (user_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]
