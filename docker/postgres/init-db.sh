#!/bin/bash
# Cria a base de dados da aplicação ("gastos") além da base de metadados do
# Airflow (criada automaticamente pela imagem via POSTGRES_DB=airflow).
# Um único container Postgres hospeda as duas bases — ver docs/decisions/0001-orquestracao-e-armazenamento.md.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE gastos;
EOSQL
