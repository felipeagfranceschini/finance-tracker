from pathlib import Path

from gastos.sources.nfce import parse_nfce_xml

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "nfce"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_extracts_chave_de_acesso_from_id_attribute():
    nota = parse_nfce_xml(_load("nota_item_unico.xml"))

    assert nota["chave_acesso"] == "35240512345678000199650010000012340123456789"
    assert len(nota["chave_acesso"]) == 44


def test_extracts_emit_and_totais():
    nota = parse_nfce_xml(_load("nota_item_unico.xml"))

    assert nota["emit_cnpj"] == "12345678000199"
    assert nota["emit_nome"] == "MERCADO EXEMPLO LTDA"
    assert nota["emit_fantasia"] == "Mercado Exemplo"
    assert nota["v_nf"] == "9.00"
    assert nota["dh_emi"] == "2024-05-10T18:22:31-03:00"


def test_extracts_multiple_itens_in_document_order():
    nota = parse_nfce_xml(_load("nota_multi_item_com_frete_desconto.xml"))

    assert len(nota["itens"]) == 2
    assert nota["itens"][0]["x_prod"] == "Pão Francês"
    assert nota["itens"][0]["n_item"] == "1"
    assert nota["itens"][1]["x_prod"] == "Queijo Minas 300g"
    assert nota["itens"][1]["n_item"] == "2"


def test_extracts_frete_desconto_e_outras_despesas():
    nota = parse_nfce_xml(_load("nota_multi_item_com_frete_desconto.xml"))

    assert nota["v_frete"] == "5.00"
    assert nota["v_desc"] == "2.00"
    assert nota["v_outro"] == "1.50"


def test_preserves_raw_xml_text():
    nota = parse_nfce_xml(_load("nota_item_unico.xml"))

    assert "Leite Integral" in nota["xml"]
