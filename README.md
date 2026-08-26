# finance-tracker

> Status: em desenvolvimento (Etapa 1 — Fundação, ver `CLAUDE.md §11`).

## O problema

O extrato bancário registra **onde** o dinheiro foi gasto, mas não **em
quê**. Uma cobrança de R$ 189,40 do iFood pode conter uma compra de
mercado, um jantar e taxas de entrega — três decisões financeiras
diferentes colapsadas numa única linha.

Este pipeline captura o detalhe item a item na origem (marketplace,
documento fiscal), reconcilia com o lançamento bancário correspondente e
classifica cada item pela sua finalidade real na vida do usuário.

Este é um artefato de portfólio de engenharia de dados: as decisões de
escopo, arquitetura e os trade-offs assumidos estão documentados em
`CLAUDE.md` e em `docs/decisions/`.

## Arquitetura

Diagrama completo em `docs/architecture.md` (adicionado na etapa de
documentação). Visão resumida do fluxo:

```
Mercado Livre (API) ──┐
NFC-e (XML)          ─┼──> purchase / purchase_item ──┐
Extrato (OFX/CSV)    ─┘──> bank_transaction            ├──> reconciliation ──> classificação ──> dbt (marts)
```

## Stack

Python 3.12 · `uv` · Apache Airflow 2.x (LocalExecutor) · PostgreSQL 16 ·
dbt-core · pytest · ruff · Docker Compose. Detalhes em `CLAUDE.md §3`.

## Como rodar

```bash
cp .env.example .env        # preencha as credenciais necessárias
mkdir -p data/inbox         # ignorado pelo git; precisa existir antes do up
                             # para não ser criado como root pelo Docker
uv sync                     # instalar dependências
docker compose up -d        # Airflow + Postgres
uv run pytest                          # testes unitários
uv run ruff check . && uv run ruff format .
cd dbt && uv run dbt build             # modelos + testes (a partir da Etapa 7)
```

O Airflow fica disponível em `http://localhost:8080` (usuário/senha em
`AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` no `.env`).

## Trade-offs e limitações

Esta seção será expandida na Etapa 8 (Documentação), após a reconciliação e
a classificação estarem implementadas. Decisões de fundação já tomadas
estão em `docs/decisions/0001-orquestracao-e-armazenamento.md`.

## Não-objetivos

Frontend, autenticação/multi-tenancy, integração com Open Finance,
scraping sem API pública e otimização para grande volume estão **fora de
escopo** deliberadamente — ver `CLAUDE.md §2`.
