# 0002 — Purchase como agregado, persistência do refresh_token, e schema parcial

## Problema

Três decisões de design surgiram implementando a ingestão do Mercado
Livre (Etapa 2) que não eram óbvias a partir do modelo canônico descrito
no `CLAUDE.md §5`:

1. O mapeamento de uma ordem da API para o modelo canônico devolve uma
   `purchase` e vários `purchase_item` — como representar isso na
   fronteira entre `domain/` (puro) e `io/` (persistência)?
2. O Mercado Livre rotaciona o `refresh_token` a cada uso — onde
   persistir o valor vigente?
3. O schema SQL da Etapa 1 previa 4 tabelas (`purchase`, `purchase_item`,
   `bank_transaction`, `reconciliation`), mas só as duas primeiras têm
   requisitos claros nesta etapa.

## Decisões

**1. `Purchase` como agregado com `items` embutido.** `domain.models.Purchase`
carrega uma lista de `PurchaseItem` em vez de o mapeamento devolver duas
listas paralelas. `io/purchases.upsert_purchase` é quem divide isso nas
duas tabelas. Isso mantém a função de mapeamento (`domain/mercadolivre.py`)
com uma única responsabilidade e uma assinatura simples
(`dict -> Purchase`), testável sem tocar em `io/`.

**2. Tabela `oauth_token` dedicada, não arquivo.** Um arquivo local (ex.:
`.token.json`) seria mais simples, mas quebraria em qualquer execução
que não compartilhe o filesystem do container anterior — e o Airflow já
roda contra Postgres. Persistir na mesma base elimina uma segunda fonte
de verdade e mantém o comportamento idempotente entre reruns do
LocalExecutor. Consequência: `io/oauth_store.py` depende de uma conexão
de banco só para isso, mas essa dependência já existe para tudo o mais.

**3. `bank_transaction` e `reconciliation` ficam fora do schema por
enquanto.** A tabela de reconciliação só pode ser desenhada corretamente
depois de entender os 5 casos difíceis do `CLAUDE.md §6` (parcelamento
1:N, estorno, `unmatched` como estado legítimo) — desenhá-la agora seria
adivinhar. `schema.sql` documenta isso explicitamente. Consequência:
`docs/decisions/0001-...md` previa migrar as 4 tabelas já na Etapa 1;
esta decisão substitui aquela previsão por uma mais conservadora.

## Ponto em aberto (não uma decisão, um risco assumido)

O endpoint `GET /orders/search?buyer={id}` e o payload de `order_items`
usados em `sources/mercadolivre.py` e nas fixtures de teste foram
confirmados via busca (a documentação oficial bloqueou fetch automatizado
neste ambiente — HTTP 403), não contra uma resposta real da API. Campos
de desconto/taxa de serviço (`discount`/`service_fee`) foram
deliberadamente deixados sem mapeamento por esse motivo — melhor não
mapear do que mapear um campo inventado. **Antes do primeiro uso real**,
validar o client contra uma resposta de sandbox e ajustar
`domain/mercadolivre.py` se a estrutura divergir.
