"""Smoke test da Etapa 1 — confirma que o pacote `gastos` está instalado e importável."""

import gastos


def test_gastos_package_is_importable() -> None:
    assert gastos is not None
