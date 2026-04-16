"""Seed data inicial — VR Academy."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from db.database import get_db
from config import DEFAULT_PASSWORD


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

USERS = [
    # Admins
    {"name": "Valdecir Rabelo", "email": "valdecir@vradvogados.com.br", "role": "admin",
     "phone": "", "hire_date": "2020-01-01"},
    {"name": "Juliana Rozembergue", "email": "juliana@vradvogados.com.br", "role": "admin",
     "phone": "", "hire_date": "2021-03-01"},
    # Gestoras (Coordenadoras Pre-Vendas)
    {"name": "Raysa Bino", "email": "rayssa.bino@vradvogados.com.br", "role": "gestor",
     "phone": "", "hire_date": "2023-01-01"},
    {"name": "Sintya Babilon", "email": "sintya.babilon@vradvogados.com.br", "role": "gestor",
     "phone": "", "hire_date": "2023-01-01"},
    # 10 SDRs ativos (colaboradores) — emails corporativos reais
    {"name": "Amanda Freitas", "email": "amanda.silva@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Jesse Janes", "email": "jesse.janes@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Jhon Borges", "email": "jhon.borges@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Jognei Santos", "email": "jognei.silva@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Josy Silva", "email": "josineia.silva@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Ketuly Silva", "email": "ketuly.silva@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Miguel Bernardez", "email": "luis.bernardez@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Nicolly do Carmo", "email": "nicolly.carmo@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Rosane Carmo", "email": "rosane.carmo@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Thays Sant'Ana", "email": "thays.santana@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2024-01-01"},
    {"name": "Pamella Franklin", "email": "pamella.franklin@vradvogados.com.br", "role": "colaborador",
     "phone": "", "hire_date": "2026-04-16"},
]

# ---------------------------------------------------------------------------
# Trilha e modulos
# ---------------------------------------------------------------------------

TRACK = {
    "name": "Onboarding SDR — Fundamentos",
    "description": "Trilha obrigatoria de certificacao para todos os SDRs. Cobre os 6 blocos do Crivo + bases de produto e cultura VR.",
    "is_required": 1,
    "due_in_days": 30,
    "order": 1,
}

MODULES = [
    {
        "name": "Abertura de Alta Conversao",
        "description": "Como quebrar o gelo, gerar rapport e capturar atencao nos primeiros 30 segundos.",
        "order": 1, "points_value": 50, "estimated_minutes": 45,
        "crivo_area": "abertura",
        "lessons": [
            {"name": "O Script de Abertura VR", "content_type": "video",
             "duration_minutes": 12, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Os 3 erros mais comuns na abertura", "content_type": "video",
             "duration_minutes": 8, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Quiz — Abertura", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 3, "passing_score": 70},
            {"name": "Game Tape — Melhores aberturas do mes", "content_type": "video",
             "duration_minutes": 15, "points_value": 10, "order": 4, "passing_score": 0},
        ],
    },
    {
        "name": "Qualificacao BANT",
        "description": "Metodologia BANT adaptada para o mercado juridico. Como qualificar sem soar robotico.",
        "order": 2, "points_value": 50, "estimated_minutes": 50,
        "crivo_area": "qualificacao",
        "lessons": [
            {"name": "BANT para Revisional — O que muda", "content_type": "video",
             "duration_minutes": 15, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Perguntas de ouro para qualificar divida", "content_type": "texto",
             "duration_minutes": 10, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Role-play — Qualificacao em 5 perguntas", "content_type": "audio",
             "duration_minutes": 15, "points_value": 10, "order": 3, "passing_score": 0},
            {"name": "Quiz — BANT", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 4, "passing_score": 70},
        ],
    },
    {
        "name": "Produtos VR Advogados",
        "description": "Catalogo completo de servicos, casos de sucesso e diferenciais competitivos.",
        "order": 3, "points_value": 50, "estimated_minutes": 40,
        "crivo_area": None,
        "lessons": [
            {"name": "Servicos e areas de atuacao", "content_type": "pdf",
             "duration_minutes": 15, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Cases de sucesso — Revisional Bancario", "content_type": "video",
             "duration_minutes": 10, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Diferenciais vs concorrentes", "content_type": "texto",
             "duration_minutes": 5, "points_value": 10, "order": 3, "passing_score": 0},
            {"name": "Quiz — Produtos", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 4, "passing_score": 70},
        ],
    },
    {
        "name": "Investigacao e Diagnostico",
        "description": "Tecnicas de investigacao profunda para descobrir a dor real do lead e prescrever a solucao certa.",
        "order": 4, "points_value": 50, "estimated_minutes": 45,
        "crivo_area": "qualificacao",
        "lessons": [
            {"name": "A metodologia de diagnostico VR", "content_type": "video",
             "duration_minutes": 18, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Perguntas de impacto — Como aprofundar", "content_type": "texto",
             "duration_minutes": 12, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Quiz — Investigacao", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 3, "passing_score": 70},
        ],
    },
    {
        "name": "Gestao de Objecoes",
        "description": "As 10 objecoes mais frequentes e como reversao. Pratica com role-plays reais.",
        "order": 5, "points_value": 50, "estimated_minutes": 60,
        "crivo_area": "objecoes",
        "lessons": [
            {"name": "As 10 objecoes do mercado juridico", "content_type": "video",
             "duration_minutes": 20, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Framework ACCA para contornar objecoes", "content_type": "texto",
             "duration_minutes": 10, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Role-play — Objecao de preco e urgencia", "content_type": "audio",
             "duration_minutes": 20, "points_value": 10, "order": 3, "passing_score": 0},
            {"name": "Quiz — Objecoes", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 4, "passing_score": 70},
        ],
    },
    {
        "name": "Fechamento e Agendamento",
        "description": "Tecnicas de fechamento para confirmacao de reuniao de diagnostico. Reducao de no-show.",
        "order": 6, "points_value": 50, "estimated_minutes": 45,
        "crivo_area": "fechamento",
        "lessons": [
            {"name": "Os 5 fechamentos que mais convertem", "content_type": "video",
             "duration_minutes": 15, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Script de confirmacao e reducao de no-show", "content_type": "texto",
             "duration_minutes": 10, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Quiz — Fechamento", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 15, "order": 3, "passing_score": 70},
        ],
    },
    {
        "name": "Game Tapes — Analise de Ligacoes Reais",
        "description": "Analise de ligacoes reais dos melhores e piores momentos. Aprendizado por observacao.",
        "order": 7, "points_value": 75, "estimated_minutes": 60,
        "crivo_area": None,
        "lessons": [
            {"name": "Como analisar uma ligacao — O Crivo", "content_type": "video",
             "duration_minutes": 10, "points_value": 10, "order": 1, "passing_score": 0},
            {"name": "Game Tape #1 — Abertura nota 10", "content_type": "video",
             "duration_minutes": 15, "points_value": 10, "order": 2, "passing_score": 0},
            {"name": "Game Tape #2 — Gestao de objecao dificil", "content_type": "video",
             "duration_minutes": 15, "points_value": 10, "order": 3, "passing_score": 0},
            {"name": "Game Tape #3 — O que NAO fazer", "content_type": "video",
             "duration_minutes": 10, "points_value": 10, "order": 4, "passing_score": 0},
            {"name": "Avaliacao — Analisar ligacao desafio", "content_type": "quiz",
             "duration_minutes": 10, "points_value": 30, "order": 5, "passing_score": 60},
        ],
    },
    {
        "name": "Certificacao Final — SDR Fundamentos",
        "description": "Prova final de certificacao. Nota minima 80. Valida por 12 meses.",
        "order": 8, "points_value": 200, "estimated_minutes": 60,
        "crivo_area": None,
        "lessons": [
            {"name": "Revisao Geral — Todos os modulos", "content_type": "texto",
             "duration_minutes": 20, "points_value": 0, "order": 1, "passing_score": 0},
            {"name": "Simulado Pre-Certificacao (40 questoes)", "content_type": "quiz",
             "duration_minutes": 30, "points_value": 50, "order": 2, "passing_score": 60},
            {"name": "Prova Final de Certificacao (50 questoes)", "content_type": "quiz",
             "duration_minutes": 45, "points_value": 150, "order": 3, "passing_score": 80},
        ],
    },
]

# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

BADGES = [
    {
        "name": "Maratonista",
        "description": "Estudou 7 dias seguidos sem parar. Consistencia e o segredo.",
        "category": "streak",
        "condition_json": json.dumps({"type": "streak", "value": 7}),
        "points_value": 50,
        "is_secret": 0,
    },
    {
        "name": "Primeiro Modulo",
        "description": "Completou o primeiro modulo da trilha. O inicio de uma grande jornada!",
        "category": "modulo",
        "condition_json": json.dumps({"type": "modules_completed", "value": 1}),
        "points_value": 25,
        "is_secret": 0,
    },
    {
        "name": "Mestre em Objecoes",
        "description": "Completou o modulo de Gestao de Objecoes com nota maxima.",
        "category": "performance",
        "condition_json": json.dumps({"type": "module_perfect", "module_order": 5}),
        "points_value": 75,
        "is_secret": 0,
    },
    {
        "name": "Estudante da Semana",
        "description": "Maior pontuacao semanal do squad. Voce e o MVP desta semana!",
        "category": "especial",
        "condition_json": json.dumps({"type": "weekly_top1"}),
        "points_value": 100,
        "is_secret": 0,
    },
    {
        "name": "Pitch Perfeito",
        "description": "Nota maxima no modulo de Abertura. Abre com classe!",
        "category": "performance",
        "condition_json": json.dumps({"type": "module_perfect", "module_order": 1}),
        "points_value": 50,
        "is_secret": 0,
    },
    {
        "name": "SDR Certificado",
        "description": "Completou a trilha de Onboarding com aprovacao na Certificacao Final.",
        "category": "trilha",
        "condition_json": json.dumps({"type": "track_completed", "track_order": 1}),
        "points_value": 200,
        "is_secret": 0,
    },
    {
        "name": "30 Dias de Fogo",
        "description": "Streaks de 30 dias. Lendario.",
        "category": "streak",
        "condition_json": json.dumps({"type": "streak", "value": 30}),
        "points_value": 150,
        "is_secret": 1,
    },
    {
        "name": "Speed Learner",
        "description": "Completou um modulo em menos de 1 hora do inicio ao fim.",
        "category": "especial",
        "condition_json": json.dumps({"type": "module_speed", "max_minutes": 60}),
        "points_value": 30,
        "is_secret": 1,
    },
]


# ---------------------------------------------------------------------------
# Funcao principal de seed
# ---------------------------------------------------------------------------

async def run_seed():
    """Executa o seed de dados iniciais. Idempotente — nao duplica dados."""
    db = await get_db()

    # Verifica se ja foi executado (checa pela trilha, nao por users — migrations podem criar users antes)
    cursor = await db.execute("SELECT COUNT(*) FROM tracks")
    track_count = (await cursor.fetchone())[0]
    if track_count > 0:
        print("[SEED] Dados ja existem. Pulando seed.")
        return

    print("[SEED] Inserindo dados iniciais...")

    pwd_hash = _hash(DEFAULT_PASSWORD)

    # Usuarios
    for u in USERS:
        await db.execute(
            """INSERT OR IGNORE INTO users (name, email, password_hash, role, phone, hire_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (u["name"], u["email"], pwd_hash, u["role"], u["phone"], u["hire_date"]),
        )

    # Trilha
    cursor = await db.execute(
        """INSERT INTO tracks (name, description, is_required, due_in_days, "order")
           VALUES (?, ?, ?, ?, ?)""",
        (TRACK["name"], TRACK["description"], TRACK["is_required"],
         TRACK["due_in_days"], TRACK["order"]),
    )
    track_id = cursor.lastrowid

    # Modulos e licoes
    module_ids = []
    for mod in MODULES:
        lessons = mod.pop("lessons")
        cursor = await db.execute(
            """INSERT INTO modules (track_id, name, description, "order", points_value,
                                   estimated_minutes, crivo_area)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (track_id, mod["name"], mod["description"], mod["order"],
             mod["points_value"], mod["estimated_minutes"], mod["crivo_area"]),
        )
        module_id = cursor.lastrowid
        module_ids.append(module_id)

        for les in lessons:
            await db.execute(
                """INSERT INTO lessons (module_id, name, content_type, duration_minutes,
                                       points_value, "order", passing_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (module_id, les["name"], les["content_type"], les["duration_minutes"],
                 les["points_value"], les["order"], les["passing_score"]),
            )

    # Set prerequisite chain: M2 needs M1, M3 needs M2, etc.
    for i in range(1, len(module_ids)):
        await db.execute(
            "UPDATE modules SET prerequisite_module_id=? WHERE id=?",
            (module_ids[i - 1], module_ids[i]),
        )

    # Badges
    for b in BADGES:
        await db.execute(
            """INSERT INTO badges (name, description, category, condition_json, points_value, is_secret)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (b["name"], b["description"], b["category"], b["condition_json"],
             b["points_value"], b["is_secret"]),
        )

    # Matricular todos os colaboradores na trilha obrigatoria
    cursor = await db.execute("SELECT id FROM users WHERE role='colaborador'")
    sdrs = await cursor.fetchall()
    from datetime import datetime, timedelta
    due_date = (datetime.now() + timedelta(days=TRACK["due_in_days"])).strftime("%Y-%m-%d")

    for sdr in sdrs:
        await db.execute(
            """INSERT OR IGNORE INTO enrollments (user_id, track_id, status, due_date)
               VALUES (?, ?, 'pendente', ?)""",
            (sdr[0], track_id, due_date),
        )
        # Criar user_points e streaks zerados
        await db.execute(
            "INSERT OR IGNORE INTO user_points (user_id) VALUES (?)", (sdr[0],)
        )
        await db.execute(
            "INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (sdr[0],)
        )

    await db.commit()
    print(f"[SEED] {len(USERS)} usuarios, 1 trilha, {len(MODULES)} modulos, {len(BADGES)} badges inseridos.")
