"""SQLite com WAL mode para leituras concorrentes — VR Academy."""

import os
import aiosqlite
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, DATA_DIR

_db: aiosqlite.Connection | None = None


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
    print(f"[DB] Inicializado em {DB_PATH}")


async def close_db():
    """Fecha a conexao com o banco de dados."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        print("[DB] Conexao encerrada")
