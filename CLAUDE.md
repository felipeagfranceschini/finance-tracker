# CLAUDE.md

Contexto de projeto para agentes trabalhando neste repositório. Leia antes de qualquer alteração.

---

## 1. O que é este projeto

Pipeline de dados pessoal que resolve um problema real: **o extrato bancário registra onde o dinheiro foi gasto, mas não em quê.** Uma cobrança de R$ 189,40 do iFood pode conter compra de mercado, um jantar e taxas — três decisões financeiras diferentes colapsadas numa linha só.

O sistema captura o detalhe item a item na origem (marketplace, documento fiscal), reconcilia com o lançamento bancário e classifica cada item por finalidade.

**O objetivo primário deste repositório é ser um artefato de portfólio de engenharia de dados**, usado em processos seletivos internacionais. Isso governa todas as decisões: o que é construído, como é documentado e — principalmente — o que é deliberadamente deixado de fora.

### O que "pronto" significa aqui

Um revisor técnico (hiring manager / staff engineer) consegue, em 10 minutos de leitura do README:

1. Entender o problema de negócio sem contexto prévio.
2. Ver o diagrama de arquitetura e saber por onde o dado entra e sai.
3. Encontrar uma seção de **trade-offs e limitações** escrita com honestidade.
4. Rodar `docker compose up` e ver o pipeline funcionar com dados de exemplo.

Se qualquer um dos quatro falhar, o projeto não está pronto — independentemente de quanto código exista.

---

## 2. Não-objetivos (guardrails de escopo)

Esta seção existe porque o modo de falha mais provável deste projeto é ele virar um produto pela metade em vez de um pipeline bem-feito. **Não implemente nada abaixo. Se for pedido, avise que está fora de escopo e pergunte antes.**

- Frontend, dashboard interativo ou aplicativo. A saída é banco + CSV + um notebook/relatório estático.
- Autenticação de usuários, multi-tenancy, cobrança, planos.
- Suporte a "outros usuários". Este pipeline processa **os dados do dono do repositório**. Multi-usuário é uma decisão de produto que não foi tomada.
- Integração com Open Finance / agregadores pagos. O lado bancário entra por arquivo (OFX/CSV exportado do banco).
- Scraping de plataformas que não expõem API ao consumidor. Se uma fonte não tem porta legítima, ela não entra — documente a ausência como decisão, não como pendência.
- Otimização para volume. O dataset real tem centenas a milhares de pedidos. **Não justifique escolhas por escala** — justifique por corretude, reprocessabilidade e clareza.

---

## 3. Stack

| Camada | Escolha | Observação |
|---|---|---|
| Linguagem | Python 3.12 | Tipagem obrigatória em funções públicas |
| Gerenciador | `uv` | `uv sync`, `uv run` — não usar pip/poetry |
| Orquestração | Apache Airflow 2.x | Docker Compose, LocalExecutor |
| Armazenamento | PostgreSQL 16 | Container próprio, volume persistente |
| Transformação | dbt-core + dbt-postgres | Camadas `staging` → `intermediate` → `marts` |
| Testes | pytest | Unitário na lógica de domínio; dbt tests no modelo |
| Lint/format | ruff | `ruff check` + `ruff format`, sem black/flake8 |
| Contêineres | Docker Compose | Um comando para subir tudo |
| LLM (classificação) | Claude via API, saída estruturada | Ver §7 |

### Layout do repositório

```
.
├── dags/                     # Airflow DAGs — apenas orquestração, sem lógica
├── src/gastos/
│   ├── sources/              # Um módulo por fonte (mercadolivre.py, nfce.py, bank.py)
│   ├── domain/               # Lógica pura: matching, rateio, normalização
│   ├── classify/             # Dicionário + cliente LLM
│   └── io/                   # Persistência, migrações
├── dbt/                      # Projeto dbt
├── docker/                   # Dockerfile do Airflow, scripts de init do Postgres
├── tests/
│   ├── unit/                 # Lógica de domínio, sem I/O
│   └── fixtures/             # Payloads ANONIMIZADOS (ver §9)
├── docs/
│   ├── architecture.md       # Diagrama + fluxo
│   └── decisions/            # ADRs numerados (0001-....md)
└── docker-compose.yml
```

**Regra de camadas:** `dags/` chama `src/`, nunca o contrário. `domain/` não importa nada de `sources/` nem de `io/` — é lógica pura, testável sem banco e sem rede. Essa fronteira é o que torna o núcleo do projeto demonstrável em entrevista; não a quebre por conveniência.

---

## 4. Fontes de dados

### 4.1 Mercado Livre — API de pedidos

- OAuth 2.0 com `refresh_token`. O access token é curto; o refresh precisa ser persistido e rotacionado.
- Endpoint de ordens do comprador. Paginação obrigatória.
- **Rate limit e bloqueio de aplicações são reais.** Implementar backoff exponencial e respeitar `Retry-After`. Nunca fazer polling agressivo.
- Um pedido pode ter múltiplos itens (`order_items[]`), cada um com `quantity`, `unit_price`, título e categoria do vendedor (que **não** é a categoria de despesa — ver §7).

### 4.2 NFC-e — XML do documento fiscal

- Entrada: XML da nota (via chave de acesso ou arquivo). O QR Code da nota carrega a chave.
- Estrutura relevante: emitente (`emit`), itens (`det/prod` — descrição, quantidade, valor unitário, valor total), totais (`ICMSTot`), e a chave de acesso como identificador natural.
- Parsear com `lxml`. **Não** montar o modelo com regex sobre XML.
- Esta fonte existe no projeto por um motivo de design explícito: ela tem um contrato radicalmente diferente do REST/JSON do Mercado Livre. Se o modelo canônico acomodar as duas sem gambiarra, o desenho está certo.

### 4.3 Extrato bancário — OFX/CSV

- Não é fonte de pedidos: é o lado "transação" da reconciliação.
- Importação por arquivo, colocado em `data/inbox/`. Sem integração automática.
- Normalizar para: `data`, `valor`, `descricao_bruta`, `conta`, `id_externo` (quando houver).

---

## 5. Modelo canônico

Três entidades centrais. Mantenha os nomes.

```
purchase          # um pedido/nota — a compra como evento comercial
  purchase_id     # natural key da fonte (order_id do ML, chave de acesso da NFC-e)
  source          # 'mercadolivre' | 'nfce'
  purchased_at
  merchant
  gross_amount    # o que a fonte diz que foi o total
  raw             # JSONB do payload original, sempre preservado

purchase_item     # linha do pedido
  purchase_id
  line_no
  description     # texto cru da fonte, NUNCA normalizado in-place
  quantity
  unit_amount
  line_amount
  kind            # 'product' | 'shipping' | 'discount' | 'service_fee'

bank_transaction  # lançamento do extrato
  transaction_id
  posted_at
  amount
  raw_description
  account
```

E a tabela que é o coração do projeto:

```
reconciliation
  purchase_id
  transaction_id
  match_strategy   # como foi casado
  confidence       # 0..1
  matched_at
  status           # 'matched' | 'unmatched_purchase' | 'unmatched_transaction' | 'manual'
```

**Regra invariante:** `raw` nunca é descartado, e `description` nunca é sobrescrita. Toda normalização produz coluna nova. Isso permite reprocessar do zero quando as regras mudarem — que é o argumento central de design deste pipeline.

---

## 6. Reconciliação — as regras difíceis

Esta é a parte intelectual do projeto e a que vai ser discutida em entrevista. Trate cada regra abaixo como requisito com teste correspondente em `tests/unit/`.

**Estratégia base.** Casar `purchase.gross_amount` com `bank_transaction.amount` dentro de uma janela de data. Default: `±2 dias` para e-commerce (a cobrança ocorre no envio, não na compra) e `±0 dias` para NFC-e presencial. A janela é configurável, nunca hardcoded no meio da função.

**Parcelamento.** Um pedido de R$ 600 em 6× vira 6 lançamentos de R$ 100 em meses diferentes. Casar por valor total falha em silêncio — que é o pior modo de falha possível. Detectar o padrão (n lançamentos de mesmo valor, espaçamento ~mensal, mesmo comerciante) e registrar como um match de um-para-muitos. Se não houver confiança suficiente, marque `unmatched` e mande para revisão; **nunca invente um match**.

**Estorno e cancelamento.** O pedido continua existindo no histórico e o lançamento é revertido depois. Um estorno não apaga a compra: cria uma linha de reversão. A categoria não pode continuar contando gasto que não houve.

**Rateio de frete, cupom e taxa.** A soma dos itens raramente bate com o valor cobrado. Decisão do projeto: essas linhas existem como `purchase_item` com `kind` próprio e são **rateadas proporcionalmente** sobre os itens de produto ao gerar a visão de despesa por categoria. O resíduo de arredondamento vai para a maior linha. Documente isso; é um trade-off, não uma verdade.

**Pagamento fora do escopo.** Pedido pago em saldo de carteira, vale-refeição ou cartão não importado não gera lançamento nenhum. `unmatched_purchase` é um estado **esperado e legítimo**, não um bug. O pipeline deve reportar a taxa de não-casados como métrica, não escondê-la.

**Idempotência.** Rodar a mesma DAG duas vezes sobre a mesma janela não pode duplicar nada nem alterar matches já confirmados manualmente. Upsert por natural key. Todo modelo dbt precisa ser reconstruível do zero a partir de `staging`.

---

## 7. Classificação

Modelo híbrido em duas etapas, nesta ordem:

1. **Dicionário aprendido.** Tabela `item_category_map` de `description_normalized` → `category`, alimentada pelas correções manuais do usuário. Match exato primeiro; a categoria mais frequente vence em caso de histórico divergente. Esta camada é determinística, gratuita e cobre a maior parte do volume real (compras se repetem).
2. **LLM com saída estruturada** apenas para o item que o dicionário não conhece. Schema fixo, categoria vinda de um enum fechado, resposta que inclui `confidence`. Item com confiança baixa vai para fila de revisão em vez de ser gravado.

Toda decisão do LLM que o usuário corrigir **realimenta o dicionário**. Com o tempo, a chamada de API tende a zero.

**Não use a categoria do vendedor do Mercado Livre como categoria de despesa.** "Eletrodomésticos" é taxonomia de catálogo; o que interessa é a finalidade na vida do usuário (mercado, refeição de conveniência, lazer, casa). Categorizar por estabelecimento ou por catálogo é exatamente o problema que este projeto existe para resolver.

**Métrica obrigatória:** acurácia da classificação contra um conjunto rotulado à mão, reportada no README. Um número honesto (mesmo que 82%) vale mais que a ausência dele.

---

## 8. Convenções de código

- Type hints em toda função pública. `mypy` não é obrigatório, mas o código deve passar se rodado.
- Funções de domínio são **puras**: recebem dados, devolvem dados, não tocam banco nem rede. Facilita teste e é o que torna a lógica demonstrável.
- Logging estruturado (`structlog` ou `logging` com `extra=`). Nunca `print`.
- Sem `except Exception: pass`. Falha explícita, com contexto no log.
- Nomes de negócio em inglês no código (`purchase`, `reconciliation`), documentação e ADRs em português.
- Commits em imperativo, escopo pequeno. Sem commits "wip" no histórico final — é um repositório de portfólio; o `git log` é lido.
- Toda decisão arquitetural não óbvia vira um ADR em `docs/decisions/`. Um ADR curto (problema, opções, escolha, consequência) é melhor sinal em entrevista do que um README longo.

### Airflow

- DAGs declarativas. Nenhuma lógica de negócio dentro de `dags/` — só chamadas para `src/gastos/`.
- Uma DAG por domínio: `ingest_mercadolivre`, `ingest_nfce`, `ingest_bank`, `reconcile`, `classify`.
- Tasks idempotentes e com `retries` configurado. Sem `datetime.now()` dentro de task — use a data lógica do Airflow, senão o backfill mente.

### dbt

- `staging`: 1:1 com a fonte, apenas renomeação e cast. Sem regra de negócio.
- `intermediate`: joins e a lógica de rateio.
- `marts`: as visões que respondem perguntas (`fct_expenses`, `dim_category`).
- Testes `not_null` e `unique` nas chaves de todo modelo. `relationships` nas FKs.

---

## 9. Dados e privacidade

Este repositório processa dados financeiros reais do dono. Ele é público (ou será).

- **Nunca commitar dados reais.** `data/`, `*.ofx`, `*.csv` de extrato e XMLs de nota estão no `.gitignore` — confirme antes de qualquer `git add`.
- Fixtures de teste são **anonimizadas e sintéticas**: valores alterados, comerciantes genéricos, sem CPF, sem chave de acesso real, sem número de cartão.
- Credenciais em `.env`, nunca em código. `.env.example` versionado com as chaves vazias.
- Se for gerar um dataset de demonstração para o README, gere sintético e diga que é sintético.

---

## 10. Comandos

```bash
uv sync                          # instalar dependências
docker compose up -d             # Airflow + Postgres
uv run pytest                    # testes unitários
uv run ruff check . && uv run ruff format .
cd dbt && uv run dbt build       # modelos + testes
```

Mantenha esta seção correta. Um comando quebrado no README é o defeito mais caro deste tipo de repositório.

---

## 11. Sequência de construção

Não pule etapas nem trabalhe em duas ao mesmo tempo. Cada uma termina com testes verdes e um commit.

1. **Fundação** — Docker Compose (Airflow + Postgres), `uv`, ruff, pytest, esqueleto de pastas, `.env.example`.
2. **Ingestão Mercado Livre** — OAuth com refresh persistido, paginação, backoff, gravação em `purchase` / `purchase_item` com `raw` preservado.
3. **Ingestão NFC-e** — parser de XML para o mesmo modelo canônico. Se exigir mudança no modelo, é sinal de que o modelo estava errado — corrija o modelo, não crie um caminho paralelo.
4. **Ingestão bancária** — leitor de OFX/CSV.
5. **Reconciliação** — todas as regras da §6, com teste por regra. Esta é a etapa que justifica o projeto; dê a ela o tempo que as outras não merecem.
6. **Classificação** — dicionário, depois LLM, depois a métrica de acurácia.
7. **dbt + marts** — as visões finais e os testes de modelo.
8. **Documentação** — `docs/architecture.md` com diagrama, README com problema/arquitetura/como rodar/trade-offs/limitações, ADRs.

A etapa 8 não é opcional nem posterior ao "projeto pronto": **ela é o entregável.** Sem diagrama, o projeto não existe para quem revisa.