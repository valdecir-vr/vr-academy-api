"""SQLite com WAL mode para leituras concorrentes — VR Academy."""

import os
import aiosqlite
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, DATA_DIR

_db = None  # type: aiosqlite.Connection | None


async def get_db() -> aiosqlite.Connection:
    """Retorna (ou cria) a conexao com o banco de dados."""
    global _db
    if _db is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.execute("PRAGMA busy_timeout=5000")
        await _db.execute("PRAGMA synchronous=NORMAL")
    return _db


async def init_db():
    """Inicializa o schema do banco a partir do schema.sql."""
    db = await get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    await db.executescript(schema)
    await db.commit()

    # ── Migrations ──────────────────────────────────────────────────────────
    # M001: Add prerequisite_module_id to modules (gate system)
    try:
        await db.execute("SELECT prerequisite_module_id FROM modules LIMIT 1")
    except Exception:
        await db.execute(
            "ALTER TABLE modules ADD COLUMN prerequisite_module_id INTEGER REFERENCES modules(id)"
        )
        # Set prerequisite chain: M2 needs M1, M3 needs M2, etc.
        cursor = await db.execute(
            'SELECT id, "order" FROM modules WHERE is_active=1 ORDER BY "order"'
        )
        mods = await cursor.fetchall()
        for i in range(1, len(mods)):
            await db.execute(
                "UPDATE modules SET prerequisite_module_id=? WHERE id=?",
                (mods[i - 1]["id"], mods[i]["id"]),
            )
        await db.commit()
        print("[DB] Migration M001: prerequisite_module_id added + chain set")

    # M002: Add Pamella Franklin if not exists
    cursor = await db.execute(
        "SELECT id FROM users WHERE email='pamella.franklin@vradvogados.com.br'"
    )
    if not await cursor.fetchone():
        import bcrypt
        pwd_hash = bcrypt.hashpw("vr2026".encode(), bcrypt.gensalt()).decode()
        await db.execute(
            """INSERT INTO users (name, email, password_hash, role, phone, hire_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("Pamella Franklin", "pamella.franklin@vradvogados.com.br", pwd_hash,
             "colaborador", "", "2026-04-16"),
        )
        cursor = await db.execute("SELECT last_insert_rowid()")
        new_id = (await cursor.fetchone())[0]
        # Enroll in all required tracks
        cursor = await db.execute("SELECT id, due_in_days FROM tracks WHERE is_required=1 AND is_active=1")
        tracks = await cursor.fetchall()
        from datetime import datetime, timedelta
        for t in tracks:
            due = (datetime.now() + timedelta(days=t["due_in_days"])).strftime("%Y-%m-%d")
            await db.execute(
                "INSERT OR IGNORE INTO enrollments (user_id, track_id, status, due_date) VALUES (?, ?, 'pendente', ?)",
                (new_id, t["id"], due),
            )
        await db.execute("INSERT OR IGNORE INTO user_points (user_id) VALUES (?)", (new_id,))
        await db.execute("INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (new_id,))
        await db.commit()
        print("[DB] Migration M002: Pamella Franklin created + enrolled")

    # M003: Ensure prerequisite chain is set (for existing DBs that ran M001 but seeded without chain)
    cursor = await db.execute(
        'SELECT COUNT(*) FROM modules WHERE prerequisite_module_id IS NOT NULL'
    )
    chain_count = (await cursor.fetchone())[0]
    cursor = await db.execute('SELECT COUNT(*) FROM modules WHERE is_active=1')
    total_mods = (await cursor.fetchone())[0]
    if total_mods > 1 and chain_count == 0:
        cursor = await db.execute(
            'SELECT id, "order" FROM modules WHERE is_active=1 ORDER BY "order"'
        )
        mods = await cursor.fetchall()
        for i in range(1, len(mods)):
            await db.execute(
                "UPDATE modules SET prerequisite_module_id=? WHERE id=?",
                (mods[i - 1]["id"], mods[i]["id"]),
            )
        await db.commit()
        print("[DB] Migration M003: prerequisite chain set on existing modules")

    print(f"[DB] Inicializado em {DB_PATH}")


async def close_db():
    """Fecha a conexao com o banco de dados."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        print("[DB] Conexao encerrada")
