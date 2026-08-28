"""DAG de ingestão do Mercado Livre.

Só orquestração — toda a lógica vive em `src/gastos/` (CLAUDE.md §8).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

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

        # Passo 1: renovar e persistir o token em uma transação própria,
        # comitada imediatamente. O Mercado Livre já invalida o
        # refresh_token antigo no lado dele assim que este novo é emitido
        # (CLAUDE.md §4.1) — se essa gravação ficasse na mesma transação
        # da ingestão de pedidos abaixo e algo falhasse lá no meio (um
        # pedido malformado, um erro de rede após esgotar as tentativas),
        # o rollback perderia o token novo mas o antigo já estaria morto
        # do lado do Mercado Livre, exigindo reautorização manual.
        with get_connection() as conn:
            apply_schema(conn)
            stored_refresh_token = load_refresh_token(conn, PROVIDER)
            initial_refresh_token = stored_refresh_token or os.environ["MERCADOLIVRE_REFRESH_TOKEN"]
            token = refresh_access_token(config, initial_refresh_token)
            save_token(conn, PROVIDER, token.access_token, token.refresh_token, token.expires_in)

        # Passo 2: ingestão em si, numa transação separada. Se falhar no
        # meio, o token da renovação acima já está seguro; a próxima
        # execução (idempotente) refaz a ingestão do zero sem precisar
        # renovar o token de novo antes do fim do prazo de 6h.
        orders_processed = 0
        with get_connection() as conn:
            for order in iter_orders(token.access_token, buyer_id=token.user_id):
                purchase = map_order_to_purchase(order)
                upsert_purchase(conn, purchase)
                orders_processed += 1

        logger.info("ingest_mercadolivre.done", orders_processed=orders_processed)
        return orders_processed

    ingest_orders()


ingest_mercadolivre()
