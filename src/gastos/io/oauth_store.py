"""Persistência do token OAuth (ver `oauth_token` em schema.sql)."""

from __future__ import annotations

from datetime import datetime

from psycopg import Connection


def save_token(
    conn: Connection,
    provider: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO oauth_token (provider, access_token, refresh_token, expires_at, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            updated_at = now()
        """,
        (provider, access_token, refresh_token, expires_at),
    )


def load_refresh_token(conn: Connection, provider: str) -> str | None:
    """Devolve o refresh_token mais recente salvo para o provedor, se houver.

    `None` na primeira execução — quem chama deve cair para o valor inicial
    em `MERCADOLIVRE_REFRESH_TOKEN` (.env) nesse caso.
    """
    row = conn.execute(
        "SELECT refresh_token FROM oauth_token WHERE provider = %s", (provider,)
    ).fetchone()
    return row[0] if row else None
