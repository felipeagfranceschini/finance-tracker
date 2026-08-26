"""Mapeamento puro: dict extraído do XML da NFC-e -> modelo canônico.

Sem I/O, sem `lxml`. Mesmo modelo canônico usado para o Mercado Livre
(`Purchase`/`PurchaseItem`) — essa é a etapa que testa se o modelo
acomoda um contrato de dados radicalmente diferente sem gambiarra
(CLAUDE.md §4.2, §11 item 3).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from gastos.domain.models import Purchase, PurchaseItem, PurchaseItemKind, PurchaseSource


def map_nota_to_purchase(nota: dict[str, Any]) -> Purchase:
    """Converte o dict extraído de uma NFC-e (ver `sources.nfce.parse_nfce_xml`)
    no modelo canônico `Purchase`.
    """
    purchase_id = nota["chave_acesso"]
    items = [_map_product_item(purchase_id, item) for item in nota.get("itens", [])]

    v_frete = _decimal_or_none(nota.get("v_frete"))
    if v_frete:
        items.append(
            _map_extra_line(
                purchase_id, len(items) + 1, "Frete", v_frete, PurchaseItemKind.SHIPPING
            )
        )

    v_desc = _decimal_or_none(nota.get("v_desc"))
    if v_desc:
        items.append(
            _map_extra_line(
                purchase_id, len(items) + 1, "Desconto", -v_desc, PurchaseItemKind.DISCOUNT
            )
        )

    v_outro = _decimal_or_none(nota.get("v_outro"))
    if v_outro:
        items.append(
            _map_extra_line(
                purchase_id,
                len(items) + 1,
                "Despesas acessórias",
                v_outro,
                PurchaseItemKind.SERVICE_FEE,
            )
        )

    return Purchase(
        purchase_id=purchase_id,
        source=PurchaseSource.NFCE,
        purchased_at=datetime.fromisoformat(nota["dh_emi"]),
        merchant=nota.get("emit_fantasia") or nota["emit_nome"],
        gross_amount=Decimal(nota["v_nf"]),
        raw={"xml": nota["xml"]},
        items=items,
    )


def _map_product_item(purchase_id: str, item: dict[str, Any]) -> PurchaseItem:
    quantity = Decimal(item["q_com"])
    unit_amount = Decimal(item["v_un_com"])
    return PurchaseItem(
        purchase_id=purchase_id,
        line_no=int(item["n_item"]),
        description=item["x_prod"],
        quantity=quantity,
        unit_amount=unit_amount,
        line_amount=Decimal(item["v_prod"]),
        kind=PurchaseItemKind.PRODUCT,
    )


def _map_extra_line(
    purchase_id: str, line_no: int, description: str, amount: Decimal, kind: PurchaseItemKind
) -> PurchaseItem:
    return PurchaseItem(
        purchase_id=purchase_id,
        line_no=line_no,
        description=description,
        quantity=Decimal(1),
        unit_amount=amount,
        line_amount=amount,
        kind=kind,
    )


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None
    amount = Decimal(value)
    return amount if amount != 0 else None
