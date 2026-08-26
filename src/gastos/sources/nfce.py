"""Leitura e parsing do XML da NFC-e (modelo 65) para uma estrutura genérica.

I/O e tradução de formato — nenhuma regra de negócio aqui (isso fica em
`gastos.domain.nfce`, que faz o mesmo papel que `domain.mercadolivre` faz
para o JSON do Mercado Livre). Parseia com `lxml`, nunca regex sobre XML
(CLAUDE.md §4.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
NS = {"nfe": NFE_NAMESPACE}


def parse_nfce_xml(xml_bytes: bytes) -> dict[str, Any]:
    """Extrai os campos relevantes do XML da NFC-e para um dict genérico.

    Não interpreta o significado de negócio dos valores — só traduz a
    árvore XML para uma estrutura plana, o papel equivalente a
    `response.json()` no cliente do Mercado Livre.
    """
    root = etree.fromstring(xml_bytes)
    inf_nfe = root.find(".//nfe:infNFe", namespaces=NS)
    if inf_nfe is None:
        raise ValueError("XML não contém infNFe — não parece ser uma NFC-e válida")

    chave_acesso = (inf_nfe.get("Id") or "").removeprefix("NFe")
    emit = inf_nfe.find("nfe:emit", namespaces=NS)
    ide = inf_nfe.find("nfe:ide", namespaces=NS)
    icms_tot = inf_nfe.find("nfe:total/nfe:ICMSTot", namespaces=NS)

    return {
        "chave_acesso": chave_acesso,
        "emit_cnpj": _text(emit, "nfe:CNPJ"),
        "emit_nome": _text(emit, "nfe:xNome"),
        "emit_fantasia": _text(emit, "nfe:xFant"),
        "dh_emi": _text(ide, "nfe:dhEmi"),
        "v_nf": _text(icms_tot, "nfe:vNF"),
        "v_desc": _text(icms_tot, "nfe:vDesc"),
        "v_frete": _text(icms_tot, "nfe:vFrete"),
        "v_outro": _text(icms_tot, "nfe:vOutro"),
        "itens": [_extract_item(det) for det in inf_nfe.findall("nfe:det", namespaces=NS)],
        "xml": xml_bytes.decode("utf-8"),
    }


def _extract_item(det: etree._Element) -> dict[str, Any]:
    prod = det.find("nfe:prod", namespaces=NS)
    return {
        "n_item": det.get("nItem"),
        "c_prod": _text(prod, "nfe:cProd"),
        "x_prod": _text(prod, "nfe:xProd"),
        "u_com": _text(prod, "nfe:uCom"),
        "q_com": _text(prod, "nfe:qCom"),
        "v_un_com": _text(prod, "nfe:vUnCom"),
        "v_prod": _text(prod, "nfe:vProd"),
    }


def _text(element: etree._Element | None, tag: str) -> str | None:
    if element is None:
        return None
    found = element.find(tag, namespaces=NS)
    return found.text if found is not None else None


def read_nfce_file(path: Path) -> dict[str, Any]:
    """Lê um arquivo XML de NFC-e do disco (entrada via arquivo — CLAUDE.md §4.2)."""
    return parse_nfce_xml(path.read_bytes())
