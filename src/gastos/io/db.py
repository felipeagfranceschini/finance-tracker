"""Conexão com o Postgres da aplicação e aplicação do schema."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import Connection

from gastos.config import require_env

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Abre uma conexão e comita ao final do bloco `with`, ou reverte em caso de erro."""
    conn = psycopg.connect(require_env("GASTOS_DATABASE_URL"))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema(conn: Connection) -> None:
    """Aplica `schema.sql`. Idempotente (usa `CREATE TABLE IF NOT EXISTS`)."""
    conn.execute(SCHEMA_PATH.read_text())
