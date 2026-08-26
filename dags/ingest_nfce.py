"""DAG de ingestão de NFC-e.

Só orquestração — toda a lógica vive em `src/gastos/` (CLAUDE.md §8). Sem
API: lê arquivos XML colocados manualmente em `data/inbox/` (CLAUDE.md §4.2).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import structlog
from airflow.decorators import dag, task

from gastos.domain.nfce import map_nota_to_purchase
from gastos.io.db import apply_schema, get_connection
from gastos.io.purchases import upsert_purchase
from gastos.sources.nfce import read_nfce_file

logger = structlog.get_logger(__name__)

NFCE_INBOX = Path("/opt/airflow/data/inbox")


@dag(
    dag_id="ingest_nfce",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ingestion", "nfce"],
)
def ingest_nfce() -> None:
    @task
    def ingest_files() -> int:
        with get_connection() as conn:
            apply_schema(conn)
            notas_processadas = 0
            for xml_path in sorted(NFCE_INBOX.glob("*.xml")):
                nota = read_nfce_file(xml_path)
                purchase = map_nota_to_purchase(nota)
                upsert_purchase(conn, purchase)
                notas_processadas += 1

        logger.info("ingest_nfce.done", notas_processadas=notas_processadas)
        return notas_processadas

    ingest_files()


ingest_nfce()
