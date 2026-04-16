"""Gate service — logica de desbloqueio sequencial de modulos — VR Academy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_db


async def is_module_unlocked(user_id: int, module_id: int) -> dict:
    """
    Verifica se um modulo esta desbloqueado para o usuario.
    Regra: o modulo so desbloqueia se TODOS os quizzes do modulo prerequisito
    foram aprovados (score >= passing_score).
    Se o modulo nao tem prerequisito, esta sempre desbloqueado.
    """
    db = await get_db()

    cursor = await db.execute(
        "SELECT id, prerequisite_module_id FROM modules WHERE id=?", (module_id,)
    )
    mod = await cursor.fetchone()
    if not mod:
        return {"unlocked": False, "reason": "Modulo nao encontrado"}

    prereq_id = mod["prerequisite_module_id"]
    if prereq_id is None:
        return {"unlocked": True, "reason": None}

    # Check if prerequisite module's quizzes are all passed
    cursor = await db.execute(
        """SELECT l.id, l.passing_score,
                  lp.status, lp.score
           FROM lessons l
           LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id = ?
           WHERE l.module_id = ? AND l.content_type = 'quiz' AND l.is_required = 1""",
        (user_id, prereq_id),
    )
    quizzes = await cursor.fetchall()

    if not quizzes:
        # No quizzes in prerequisite — check all required lessons are completed
        cursor = await db.execute(
            """SELECT COUNT(*) FROM lessons l
               WHERE l.module_id = ? AND l.is_required = 1""",
            (prereq_id,),
        )
        total_req = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM lesson_progress lp
               JOIN lessons l ON l.id = lp.lesson_id
               WHERE lp.user_id = ? AND l.module_id = ? AND l.is_required = 1
                 AND lp.status = 'concluida'""",
            (user_id, prereq_id),
        )
        done = (await cursor.fetchone())[0]

        if done >= total_req and total_req > 0:
            return {"unlocked": True, "reason": None}
        else:
            return {
                "unlocked": False,
                "reason": f"Complete todas as licoes obrigatorias do modulo anterior ({done}/{total_req})",
            }

    # Check each quiz
    for quiz in quizzes:
        status = quiz["status"]
        score = quiz["score"]
        passing = quiz["passing_score"]
        if status != "concluida" or score is None or score < passing:
            return {
                "unlocked": False,
                "reason": f"Aprove o quiz do modulo anterior (nota minima: {passing}%)",
            }

    return {"unlocked": True, "reason": None}


async def get_modules_lock_status(user_id: int, track_id: int) -> dict:
    """
    Retorna o status de desbloqueio de todos os modulos de uma trilha.
    Otimizado para buscar tudo em poucas queries.
    Returns: {module_id: {"unlocked": bool, "reason": str|None, "prerequisite_module_id": int|None}}
    """
    db = await get_db()

    # All modules of the track
    cursor = await db.execute(
        """SELECT id, "order", prerequisite_module_id
           FROM modules WHERE track_id = ? AND is_active = 1
           ORDER BY "order" """,
        (track_id,),
    )
    modules = await cursor.fetchall()

    if not modules:
        return {}

    module_ids = [m["id"] for m in modules]
    placeholders = ",".join("?" * len(module_ids))

    # All quiz lessons for these modules
    cursor = await db.execute(
        f"""SELECT l.id, l.module_id, l.passing_score, l.is_required,
                   lp.status, lp.score
            FROM lessons l
            LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id = ?
            WHERE l.module_id IN ({placeholders}) AND l.content_type = 'quiz' AND l.is_required = 1""",
        [user_id] + module_ids,
    )
    quiz_rows = await cursor.fetchall()

    # All required lessons completion status
    cursor = await db.execute(
        f"""SELECT l.module_id,
                   COUNT(*) AS total_required,
                   SUM(CASE WHEN lp.status = 'concluida' THEN 1 ELSE 0 END) AS done
            FROM lessons l
            LEFT JOIN lesson_progress lp ON lp.lesson_id = l.id AND lp.user_id = ?
            WHERE l.module_id IN ({placeholders}) AND l.is_required = 1
            GROUP BY l.module_id""",
        [user_id] + module_ids,
    )
    completion_rows = await cursor.fetchall()

    # Build lookup: module_id -> quizzes
    quizzes_by_mod = {}
    for q in quiz_rows:
        quizzes_by_mod.setdefault(q["module_id"], []).append(q)

    # Build lookup: module_id -> completion stats
    completion_by_mod = {}
    for c in completion_rows:
        completion_by_mod[c["module_id"]] = {
            "total": c["total_required"],
            "done": c["done"],
        }

    def _is_prereq_passed(prereq_id: int) -> tuple[bool, str | None]:
        """Check if a prerequisite module is passed."""
        quizzes = quizzes_by_mod.get(prereq_id, [])
        if quizzes:
            for q in quizzes:
                if q["status"] != "concluida" or q["score"] is None or q["score"] < q["passing_score"]:
                    return False, f"Aprove o quiz do modulo anterior (nota minima: {q['passing_score']}%)"
            return True, None
        else:
            comp = completion_by_mod.get(prereq_id, {"total": 0, "done": 0})
            if comp["total"] > 0 and comp["done"] >= comp["total"]:
                return True, None
            return False, f"Complete todas as licoes obrigatorias do modulo anterior ({comp['done']}/{comp['total']})"

    result = {}
    for mod in modules:
        prereq_id = mod["prerequisite_module_id"]
        if prereq_id is None:
            result[mod["id"]] = {"unlocked": True, "reason": None, "prerequisite_module_id": None}
        else:
            passed, reason = _is_prereq_passed(prereq_id)
            result[mod["id"]] = {"unlocked": passed, "reason": reason, "prerequisite_module_id": prereq_id}

    return result
