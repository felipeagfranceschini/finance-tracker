# 0003 — NFC-e acomodada no modelo canônico sem nenhuma mudança de schema

## Problema

`CLAUDE.md §4.2` e `§11` (item 3) colocam a Etapa 3 como um teste
deliberado: a NFC-e tem um contrato de dados radicalmente diferente do
Mercado Livre (XML fiscal padronizado por SEFAZ vs. REST/JSON de um
marketplace) — "se o modelo canônico acomodar as duas sem gambiarra, o
desenho está certo." Se acomodar exigisse mudar `purchase`/`purchase_item`,
isso seria sinal de que o modelo da Etapa 2 estava errado, não motivo
para abrir um caminho paralelo.

## Resultado

Acomodou sem nenhuma mudança de schema nem de `io/purchases.py`. Mapeamento:

| Campo canônico          | Mercado Livre                  | NFC-e                                  |
|--------------------------|--------------------------------|-----------------------------------------|
| `purchase_id`            | `order.id`                     | `infNFe/@Id` (chave de acesso, 44 dígitos) |
| `purchased_at`            | `order.date_created`           | `ide/dhEmi`                             |
| `merchant`                | `order.seller.nickname`        | `emit/xFant` (ou `xNome` se ausente)    |
| `gross_amount`            | `order.total_amount`           | `total/ICMSTot/vNF`                     |
| `purchase_item` (product) | `order_items[]`                | `det/prod`                              |
| `purchase_item` (shipping)| `order.shipping_cost`          | `ICMSTot/vFrete`                        |
| `purchase_item` (discount)| `order.coupon.amount`          | `ICMSTot/vDesc`                         |
| `purchase_item` (service_fee)| `order.taxes.amount`        | `ICMSTot/vOutro`                        |

As duas fontes convergem para o mesmo padrão de mapeamento — item(ns) do
pedido/nota + até três linhas extras condicionais (frete/desconto/taxa),
todas com o mesmo formato de decisão ("se o valor existir e for
diferente de zero, vira uma `purchase_item` própria"). `io/purchases.upsert_purchase`
não sabe nem precisa saber de onde a `Purchase` veio.

## Decisão de design: `raw` para XML

O modelo canônico define `raw: dict[str, Any]` (pensado originalmente
para o JSON nativo do Mercado Livre). Para NFC-e, em vez de inventar uma
conversão XML→dict (que arriscaria perder informação ou introduzir bugs
próprios), `raw` guarda `{"xml": <texto original>}` — o XML bruto
preservado como string dentro do único campo JSONB. Simples, honesto, e
mantém a garantia de "`raw` nunca é descartado" (CLAUDE.md §5) igual para
as duas fontes.

## Namespace do XML

O XML da NFC-e usa o namespace `http://www.portalfiscal.inf.br/nfe` em
todas as tags. `sources/nfce.py` usa esse namespace explicitamente em
todo XPath (`nfe:infNFe`, `nfe:det`, etc.) — esquecer isso é o erro mais
comum ao parsear NF-e/NFC-e com `lxml` (as buscas silenciosamente não
encontram nada, sem erro).

## Fora de escopo, deliberadamente

Validação do dígito verificador da chave de acesso, parsing de impostos
(ICMS/PIS/COFINS por item) e do XML de cancelamento/carta de correção
não são feitos — nenhum desses dados é necessário para o modelo canônico
de despesa. `emit_cnpj` é extraído mas não usado ainda (fica disponível
em `raw` para uma eventual necessidade futura).
