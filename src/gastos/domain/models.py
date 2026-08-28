"""Modelo canônico do pipeline — ver CLAUDE.md §5.

Módulo puro: nenhuma dependência de `sources/` nem de `io/`.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PurchaseSource(StrEnum):
    MERCADOLIVRE = "mercadolivre"
    NFCE = "nfce"


class PurchaseItemKind(StrEnum):
    PRODUCT = "product"
    SHIPPING = "shipping"
    DISCOUNT = "discount"
    SERVICE_FEE = "service_fee"


class PurchaseItem(BaseModel):
    purchase_id: str
    line_no: int
    description: str
    quantity: Decimal
    unit_amount: Decimal
    line_amount: Decimal
    kind: PurchaseItemKind


class Purchase(BaseModel):
    """Agregado: uma compra e seus itens.

    A persistência (`io/purchases.py`) divide isso em duas tabelas
    (`purchase` e `purchase_item`) — ver docs/decisions/0002-agregado-purchase-e-token-oauth.md.
    """

    purchase_id: str
    source: PurchaseSource
    purchased_at: datetime
    merchant: str
    gross_amount: Decimal
    raw: dict[str, Any]
    items: list[PurchaseItem] = Field(default_factory=list)
