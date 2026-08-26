"""DAG de ingestão do Mercado Livre.

Só orquestração — toda a lógica vive em `src/gastos/` (CLAUDE.md §8).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import structlog
from airflow.decorators import dag, task

from gastos.domain.mercadolivre import map_order_to_purchase
from gastos.io.db import apply_schema, get_connection
from gastos.io.oauth_store import load_refresh_token, save_token
from gastos.io.purchases import upsert_purchase
from gastos.sources.mercadolivre import MercadoLivreConfig, iter_orders, refresh_access_token

logger = structlog.get_logger(__name__)

PROVIDER = "mercadolivre"


@dag(
    dag_id="ingest_mercadolivre",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 3, "retry_delay": timedelta(minutes=5)},
    tags=["ingestion", "mercadolivre"],
)
def ingest_mercadolivre() -> None:
    @task
    def ingest_orders() -> int:
        config = MercadoLivreConfig.from_env()

        with get_connection() as conn:
            apply_schema(conn)

            stored_refresh_token = load_refresh_token(conn, PROVIDER)
            initial_refresh_token = stored_refresh_token or os.environ["MERCADOLIVRE_REFRESH_TOKEN"]

            token = refresh_access_token(config, initial_refresh_token)
            expires_at = datetime.now(UTC) + timedelta(seconds=token.expires_in)
            save_token(conn, PROVIDER, token.access_token, token.refresh_token, expires_at)

            orders_processed = 0
            for order in iter_orders(token.access_token, buyer_id=token.user_id):
                purchase = map_order_to_purchase(order)
                upsert_purchase(conn, purchase)
                orders_processed += 1

        logger.info("ingest_mercadolivre.done", orders_processed=orders_processed)
        return orders_processed

    ingest_orders()


ingest_mercadolivre()
