"""Helpers for seeding the SQLite DB in Vercel runtime.

Seeding logic is now centralized in database.init_db().
This module is kept for backwards compatibility.
"""

from __future__ import annotations

import os


def ensure_seed_db() -> None:
    """database.init_db()가 시드 복사를 처리하므로 여기선 no-op."""
    if not os.environ.get("VERCEL"):
        return
    # 실제 복사는 database.init_db() 에서 수행됨
