import json
from decimal import Decimal
from pathlib import Path

from gastos.domain.mercadolivre import map_order_to_purchase
from gastos.domain.models import PurchaseItemKind, PurchaseSource

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "mercadolivre"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_maps_single_item_order():
    order = _load_fixture("order_single_item.json")

    purchase = map_order_to_purchase(order)

    assert purchase.purchase_id == "2000012345678"
    assert purchase.source == PurchaseSource.MERCADOLIVRE
    assert purchase.merchant == "LOJA_EXEMPLO"
    assert purchase.gross_amount == Decimal("39.90")
    assert purchase.raw == order
    assert len(purchase.items) == 1

    item = purchase.items[0]
    assert item.description == "Kit 3 Escovas de Dente Macias"
    assert item.quantity == Decimal("1")
    assert item.unit_amount == Decimal("39.90")
    assert item.line_amount == Decimal("39.90")
    assert item.kind == PurchaseItemKind.PRODUCT


def test_shipping_cost_becomes_its_own_line_when_present():
    order = _load_fixture("order_multi_item_with_shipping.json")

    purchase = map_order_to_purchase(order)

    assert len(purchase.items) == 3  # 2 produtos + frete
    kinds = [item.kind for item in purchase.items]
    assert kinds == [
        PurchaseItemKind.PRODUCT,
        PurchaseItemKind.PRODUCT,
        PurchaseItemKind.SHIPPING,
    ]
    shipping_item = purchase.items[-1]
    assert shipping_item.description == "Frete"
    assert shipping_item.line_amount == Decimal("115.30")


def test_shipping_line_is_omitted_when_shipping_cost_is_zero():
    order = _load_fixture("order_single_item.json")

    purchase = map_order_to_purchase(order)

    assert all(item.kind != PurchaseItemKind.SHIPPING for item in purchase.items)


def test_line_amount_is_quantity_times_unit_amount():
    order = _load_fixture("order_multi_item_with_shipping.json")

    purchase = map_order_to_purchase(order)

    rice, beans, _shipping = purchase.items
    assert rice.line_amount == Decimal("2") * Decimal("24.90")
    assert beans.line_amount == Decimal("3") * Decimal("8.50")


def test_does_not_use_seller_catalog_category_as_expense_category():
    order = _load_fixture("order_single_item.json")

    purchase = map_order_to_purchase(order)

    # category_id do vendedor não deve virar campo do domínio — só continua
    # disponível dentro de `raw` para inspeção (ver CLAUDE.md §7).
    for item in purchase.items:
        assert not hasattr(item, "category_id")
    assert purchase.raw["order_items"][0]["item"]["category_id"] == "MLB271599"


def test_mapping_is_deterministic():
    order = _load_fixture("order_single_item.json")

    first = map_order_to_purchase(order)
    second = map_order_to_purchase(order)

    assert first == second
