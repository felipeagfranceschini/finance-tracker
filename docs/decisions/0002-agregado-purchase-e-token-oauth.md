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

## Atualização — validado contra a API real (2026-08-26)

O ponto em aberto original (abaixo, mantido como histórico) foi resolvido:
o Mercado Livre **não tem sandbox** — testes são feitos em produção, com
até 10 "usuários de teste" por conta (`POST /users/test_user`, expiram
após 60 dias sem uso, só transacionam contra anúncios de outros usuários
de teste). Em vez de criar um usuário de teste sem histórico de compras
(o que não validaria nada), o dono do projeto autorizou a aplicação com a
própria conta e o client validou `GET /orders/search?buyer={id}` contra 5
pedidos reais. **Nenhum dado real foi persistido no repositório** — a
resposta foi inspecionada só em memória/scratch.

**Validação final:** com `client_id`/`client_secret`/`refresh_token`
reais, o DAG `ingest_mercadolivre` foi disparado de ponta a ponta pelo
Airflow (não só chamando funções isoladas) contra a conta real do dono
do projeto — refresh do token, paginação completa, mapeamento e upsert.
Resultado: 129 `purchase` / 134 `purchase_item` (129 `product` + 5
`discount` reais). **Rodado uma segunda vez para confirmar
idempotência**: mesmos números, zero `purchase_id` duplicado — o
requisito mais importante do `CLAUDE.md §6` confirmado contra dado real,
não só contra fixture sintética. Os dados ficam no Postgres local (uso
real do pipeline); nada disso foi commitado.

Confirmado: `paging.total/offset/limit`, `order.total_amount`,
`order.date_created`, `order.seller.nickname`, `order_items[].quantity`,
`order_items[].unit_price`, `order_items[].item.title`,
`order_items[].item.category_id`. Dois campos foram corrigidos em relação
à hipótese inicial:

- **Desconto vem em `order.coupon.amount`**, não em `payments[].coupon_amount`
  como uma fonte secundária sugeria. Mapeado agora como linha `discount`
  com valor **negativo** (reduz o total, não é uma despesa).
- **Taxa de serviço vem em `order.taxes.amount`** (`null` quando não há).
  Mapeado como linha `service_fee`.

`shipping_cost` veio `null` nos 5 pedidos observados (frete
provavelmente embutido no preço do item nesses casos específicos) — o
código já tratava `None`/`0` como "sem linha de frete", então nenhuma
mudança foi necessária aí, mas o caminho "`shipping_cost` > 0" ainda não
foi observado contra um pedido real.

**Pegadinha de configuração do app** (guardado aqui porque não é óbvio e
vai se repetir se o app precisar ser reconfigurado): a página de
autorização do Mercado Livre retorna um erro genérico ("a aplicação não
está pronta para se conectar") quando a URL de autorização inclui
`code_challenge`/`code_challenge_method` (PKCE) mas o app **não** está
marcado com "PKCE necessário" no painel de desenvolvedores — remover
esses parâmetros da URL resolve. Além disso, o fluxo "Refresh Token"
precisa estar marcado explicitamente em "Fluxos OAuth" no app para a
troca de código retornar um `refresh_token` (sem isso, só vem
`access_token`, válido por 6h, sem forma de renovar).

## Ponto em aberto original (histórico)

O endpoint `GET /orders/search?buyer={id}` e o payload de `order_items`
usados em `sources/mercadolivre.py` e nas fixtures de teste foram
confirmados via busca (a documentação oficial bloqueou fetch automatizado
neste ambiente — HTTP 403), não contra uma resposta real da API. Campos
de desconto/taxa de serviço (`discount`/`service_fee`) foram
deliberadamente deixados sem mapeamento por esse motivo — melhor não
mapear do que mapear um campo inventado. **Antes do primeiro uso real**,
validar o client contra uma resposta de sandbox e ajustar
`domain/mercadolivre.py` se a estrutura divergir.
