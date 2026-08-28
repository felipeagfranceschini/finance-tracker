"""Leitura de configuração via variável de ambiente, compartilhada por `sources/` e `io/`."""

from __future__ import annotations

import os


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"variável de ambiente obrigatória não definida: {name}")
    return value
