"""Cliente HTTP da API do Mercado Livre: OAuth2 (refresh_token) e busca de pedidos.

Sem lógica de negócio aqui — só I/O. O mapeamento para o modelo canônico
fica em `gastos.domain.mercadolivre`.

Endpoint e parâmetros validados contra pedidos reais (ver ADR 0002) —
a documentação oficial (developers.mercadolivre.com.br) bloqueia fetch
automatizado neste ambiente (403), então a validação foi feita chamando
a API diretamente com uma conta real, não pela documentação.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from gastos.config import require_env

logger = structlog.get_logger(__name__)

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ORDERS_SEARCH_URL = "https://api.mercadolibre.com/orders/search"
DEFAULT_PAGE_SIZE = 50
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class MercadoLivreConfig:
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> MercadoLivreConfig:
        return cls(
            client_id=require_env("MERCADOLIVRE_CLIENT_ID"),
            client_secret=require_env("MERCADOLIVRE_CLIENT_SECRET"),
        )


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: int


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


def _wait_respecting_retry_after(retry_state):
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, httpx.HTTPStatusError):
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                logger.warning("mercadolivre.retry_after.invalido", valor=retry_after)
    return wait_exponential(multiplier=1, min=1, max=60)(retry_state)


def _raise_for_status(response: httpx.Response) -> httpx.Response:
    response.raise_for_status()
    return response


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=_wait_respecting_retry_after,
    stop=stop_after_attempt(MAX_ATTEMPTS),
    reraise=True,
)
def refresh_access_token(
    config: MercadoLivreConfig,
    refresh_token: str,
    *,
    client: httpx.Client | None = None,
) -> TokenResponse:
    """Troca um refresh_token por um novo access_token.

    O Mercado Livre rotaciona o refresh_token a cada uso — só o valor
    devolvido nesta resposta continua válido (CLAUDE.md §4.1). Quem chama
    esta função é responsável por persistir o novo refresh_token; esta
    função não toca em I/O de persistência.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        logger.info("mercadolivre.refresh_token.start")
        response = _raise_for_status(
            client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "refresh_token": refresh_token,
                },
            )
        )
        payload = response.json()
        logger.info("mercadolivre.refresh_token.success", user_id=payload["user_id"])
        return TokenResponse(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_in=payload["expires_in"],
            user_id=payload["user_id"],
        )
    finally:
        if owns_client:
            client.close()


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=_wait_respecting_retry_after,
    stop=stop_after_attempt(MAX_ATTEMPTS),
    reraise=True,
)
def _fetch_orders_page(
    client: httpx.Client,
    access_token: str,
    buyer_id: int,
    offset: int,
    limit: int,
) -> dict:
    response = _raise_for_status(
        client.get(
            ORDERS_SEARCH_URL,
            params={"buyer": buyer_id, "offset": offset, "limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    )
    return response.json()


def iter_orders(
    access_token: str,
    buyer_id: int,
    *,
    client: httpx.Client | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[dict]:
    """Itera todos os pedidos do comprador, paginando automaticamente.

    Nunca faz polling agressivo: cada página é uma chamada, com backoff
    exponencial e respeito a `Retry-After` em 429/5xx (CLAUDE.md §4.1).

    Sem filtro de data de propósito: itera o histórico completo a cada
    chamada, em vez de só pedidos novos desde a última execução. Para o
    volume do projeto (centenas a milhares de pedidos — CLAUDE.md §2, que
    também deixa explícito para não otimizar por escala) isso é
    barato — dezenas de páginas, não milhares — e é o que permite
    detectar estorno/cancelamento em pedidos antigos (CLAUDE.md §6), que
    um filtro incremental por data de criação perderia.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        offset = 0
        total: int | None = None
        while total is None or offset < total:
            page = _fetch_orders_page(client, access_token, buyer_id, offset, page_size)
            results = page.get("results", [])
            logger.info("mercadolivre.orders.page", offset=offset, count=len(results))
            yield from results
            if not results:
                break
            total = page.get("paging", {}).get("total", offset + len(results))
            offset += page_size
    finally:
        if owns_client:
            client.close()
