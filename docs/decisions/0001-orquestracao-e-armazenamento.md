# 0001 — Orquestração com LocalExecutor e um único container Postgres

## Problema

O pipeline precisa de um orquestrador (Airflow) e de armazenamento
relacional (Postgres) para o modelo canônico. O volume real de dados é
pequeno (centenas a milhares de pedidos — ver CLAUDE.md §2), então a
infraestrutura não deveria ser dimensionada para escala que o projeto não
tem.

## Opções consideradas

1. **CeleryExecutor + Redis + workers dedicados.** Padrão em produção, mas
   adiciona Redis, um serviço de worker e complexidade operacional sem
   nenhum ganho real no volume de dados deste projeto.
2. **Dois containers Postgres** (um para metadados do Airflow, outro para a
   aplicação). Isola completamente os dois bancos, mas dobra o número de
   containers, volumes e strings de conexão para gerenciar sem necessidade.
3. **LocalExecutor + um único container Postgres com duas bases**
   (`airflow` e `gastos`), criada a segunda via script de init.

## Escolha

Opção 3: `AIRFLOW__CORE__EXECUTOR=LocalExecutor` e um container Postgres
único, com a base `gastos` criada por
`docker/postgres/init-db.sh` além da base `airflow` (default da imagem
oficial via `POSTGRES_DB`).

## Consequência

- `docker compose up` sobe em poucos containers (postgres, airflow-init,
  airflow-webserver, airflow-scheduler), coerente com o critério de
  "um comando para rodar tudo" do README.
- LocalExecutor não paraleliza entre máquinas — irrelevante aqui, já que
  não há requisito de escala (não-objetivo explícito, CLAUDE.md §2).
- As duas bases compartilham usuário/senha e o mesmo processo Postgres;
  isso é aceitável porque o projeto roda em ambiente de desenvolvimento
  pessoal, não multi-tenant.
- Se o projeto algum dia precisar de paralelismo real entre workers, a
  migração para CeleryExecutor exige apenas trocar o executor e adicionar
  um broker — a decisão não é definitiva, é a mais simples que atende o
  escopo atual.
