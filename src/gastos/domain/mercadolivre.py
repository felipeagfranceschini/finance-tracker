"""Mapeamento puro: payload de uma ordem da API do Mercado Livre -> modelo canônico.

Sem I/O. Ver CLAUDE.md §4.1 e §7.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from gastos.domain.models import Purchase, PurchaseItem, PurchaseItemKind, PurchaseSource


def map_order_to_purchase(order: dict[str, Any]) -> Purchase:
    """Converte uma ordem do Mercado Livre no modelo canônico `Purchase`.

    Não propaga `order_items[].item.category_id` (categoria de catálogo do
    vendedor) para `purchase_item.kind` nem para nenhum outro campo — essa
    categoria não é a finalidade da despesa (CLAUDE.md §7). O campo continua
    disponível em `raw` para inspeção futura, só não é usado pelo domínio.

    Rateio de frete/cupom/taxa (CLAUDE.md §6) não é feito aqui — isso é
    lógica de reconciliação (Etapa 5), não de mapeamento da fonte. Aqui só
    traduzimos o que a API do Mercado Livre já expõe como linha própria
    (frete). Desconto e taxa de serviço (`discount`/`service_fee`) ainda não
    são mapeados: o formato exato desses campos na resposta da API não foi
    confirmado contra uma resposta real (ver ADR 0002) — melhor não mapear
    do que mapear errado.
    """
    purchase_id = str(order["id"])
    items = [
        _map_product_item(purchase_id, line_no, raw_item)
        for line_no, raw_item in enumerate(order.get("order_items", []), start=1)
    ]

    shipping_cost = order.get("shipping_cost")
    if shipping_cost:
        items.append(_map_shipping_item(purchase_id, len(items) + 1, Decimal(str(shipping_cost))))

    return Purchase(
        purchase_id=purchase_id,
        source=PurchaseSource.MERCADOLIVRE,
        purchased_at=_parse_datetime(order["date_created"]),
        merchant=_extract_merchant(order),
        gross_amount=Decimal(str(order["total_amount"])),
        raw=order,
        items=items,
    )


def _map_product_item(purchase_id: str, line_no: int, raw_item: dict[str, Any]) -> PurchaseItem:
    item = raw_item["item"]
    quantity = Decimal(str(raw_item["quantity"]))
    unit_amount = Decimal(str(raw_item["unit_price"]))
    return PurchaseItem(
        purchase_id=purchase_id,
        line_no=line_no,
        description=item["title"],
        quantity=quantity,
        unit_amount=unit_amount,
        line_amount=quantity * unit_amount,
        kind=PurchaseItemKind.PRODUCT,
    )


def _map_shipping_item(purchase_id: str, line_no: int, amount: Decimal) -> PurchaseItem:
    return PurchaseItem(
        purchase_id=purchase_id,
        line_no=line_no,
        description="Frete",
        quantity=Decimal(1),
        unit_amount=amount,
        line_amount=amount,
        kind=PurchaseItemKind.SHIPPING,
    )


def _extract_merchant(order: dict[str, Any]) -> str:
    seller = order.get("seller", {})
    return seller.get("nickname") or str(seller.get("id", "desconhecido"))


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)
