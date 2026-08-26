from decimal import Decimal
from pathlib import Path

from gastos.domain.models import PurchaseItemKind, PurchaseSource
from gastos.domain.nfce import map_nota_to_purchase
from gastos.sources.nfce import parse_nfce_xml

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "nfce"


def _map(name: str):
    nota = parse_nfce_xml((FIXTURES / name).read_bytes())
    return map_nota_to_purchase(nota)


def test_maps_single_item_nota():
    purchase = _map("nota_item_unico.xml")

    assert purchase.purchase_id == "35240512345678000199650010000012340123456789"
    assert purchase.source == PurchaseSource.NFCE
    assert purchase.merchant == "Mercado Exemplo"
    assert purchase.gross_amount == Decimal("9.00")
    assert len(purchase.items) == 1

    item = purchase.items[0]
    assert item.description == "Leite Integral 1L"
    assert item.quantity == Decimal("2.0000")
    assert item.unit_amount == Decimal("4.5000")
    assert item.line_amount == Decimal("9.00")
    assert item.kind == PurchaseItemKind.PRODUCT


def test_maps_frete_desconto_e_outras_despesas_as_separate_lines():
    purchase = _map("nota_multi_item_com_frete_desconto.xml")

    assert len(purchase.items) == 5  # 2 produtos + frete + desconto + outras despesas
    kinds = [item.kind for item in purchase.items]
    assert kinds == [
        PurchaseItemKind.PRODUCT,
        PurchaseItemKind.PRODUCT,
        PurchaseItemKind.SHIPPING,
        PurchaseItemKind.DISCOUNT,
        PurchaseItemKind.SERVICE_FEE,
    ]

    shipping, discount, fee = purchase.items[2:]
    assert shipping.line_amount == Decimal("5.00")
    assert discount.line_amount == Decimal("-2.00")
    assert fee.line_amount == Decimal("1.50")


def test_uses_razao_social_when_nome_fantasia_absent():
    nota = parse_nfce_xml((FIXTURES / "nota_item_unico.xml").read_bytes())
    nota["emit_fantasia"] = None

    purchase = map_nota_to_purchase(nota)

    assert purchase.merchant == "MERCADO EXEMPLO LTDA"


def test_raw_preserves_original_xml_text():
    purchase = _map("nota_item_unico.xml")

    assert "xml" in purchase.raw
    assert "Leite Integral" in purchase.raw["xml"]


def test_mapping_is_deterministic():
    first = _map("nota_item_unico.xml")
    second = _map("nota_item_unico.xml")

    assert first == second
