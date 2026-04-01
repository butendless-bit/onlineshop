"""Helpers for seeding the SQLite DB in Vercel runtime."""

from __future__ import annotations

import os
import shutil
import sqlite3

from config import DB_PATH, DB_SEED


def _db_has_products(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False

    conn = None
    try:
        conn = sqlite3.connect(path)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
        ).fetchone()
        if not row:
            return False
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        return int(count) > 0
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def ensure_seed_db() -> None:
    if not os.environ.get("VERCEL"):
        return

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    seed_ready = _db_has_products(DB_SEED)
    target_ready = _db_has_products(DB_PATH)

    if seed_ready and not target_ready:
        shutil.copy2(DB_SEED, DB_PATH)
