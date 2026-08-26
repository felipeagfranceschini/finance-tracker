"""Persistência de `Purchase`/`PurchaseItem` — upsert idempotente por natural key."""

from __future__ import annotations

from psycopg import Connection
from psycopg.types.json import Jsonb

from gastos.domain.models import Purchase


def upsert_purchase(conn: Connection, purchase: Purchase) -> None:
    """Insere ou atualiza uma compra e seus itens.

    Idempotente: rodar duas vezes com o mesmo `purchase_id` não duplica
    nada (CLAUDE.md §6, "idempotência"). `raw` é sempre substituído pelo
    valor mais recente da fonte — não há normalização in-place aqui, só
    ressincronização de campos brutos.

    Também remove linhas de `purchase_item` que sobraram de uma versão
    anterior do pedido com mais itens (ex.: frete/desconto que existia
    antes e não existe mais) — sem isso, `line_no`s antigos ficariam
    "órfãos" e contados em dobro para sempre.
    """
    conn.execute(
        """
        INSERT INTO purchase
            (purchase_id, source, purchased_at, merchant, gross_amount, raw, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (purchase_id) DO UPDATE SET
            source = EXCLUDED.source,
            purchased_at = EXCLUDED.purchased_at,
            merchant = EXCLUDED.merchant,
            gross_amount = EXCLUDED.gross_amount,
            raw = EXCLUDED.raw,
            updated_at = now()
        """,
        (
            purchase.purchase_id,
            purchase.source.value,
            purchase.purchased_at,
            purchase.merchant,
            purchase.gross_amount,
            Jsonb(purchase.raw),
        ),
    )
    for item in purchase.items:
        conn.execute(
            """
            INSERT INTO purchase_item
                (purchase_id, line_no, description, quantity, unit_amount, line_amount, kind)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (purchase_id, line_no) DO UPDATE SET
                description = EXCLUDED.description,
                quantity = EXCLUDED.quantity,
                unit_amount = EXCLUDED.unit_amount,
                line_amount = EXCLUDED.line_amount,
                kind = EXCLUDED.kind
            """,
            (
                item.purchase_id,
                item.line_no,
                item.description,
                item.quantity,
                item.unit_amount,
                item.line_amount,
                item.kind.value,
            ),
        )
    conn.execute(
        "DELETE FROM purchase_item WHERE purchase_id = %s AND line_no > %s",
        (purchase.purchase_id, len(purchase.items)),
    )
