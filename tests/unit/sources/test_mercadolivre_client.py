import httpx
import pytest

from gastos.sources.mercadolivre import (
    MercadoLivreConfig,
    TokenResponse,
    iter_orders,
    refresh_access_token,
)


def _config() -> MercadoLivreConfig:
    return MercadoLivreConfig(client_id="id123", client_secret="secret123")


def _token_payload(**overrides) -> dict:
    payload = {
        "access_token": "APP_USR-token",
        "token_type": "bearer",
        "expires_in": 21600,
        "scope": "offline_access read",
        "user_id": 111222333,
        "refresh_token": "TG-new-refresh",
    }
    payload.update(overrides)
    return payload


def test_refresh_access_token_returns_new_tokens_and_sends_correct_grant():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read().decode()
        return httpx.Response(200, json=_token_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))

    token = refresh_access_token(_config(), "TG-old-refresh", client=client)

    assert captured["path"] == "/oauth/token"
    assert "grant_type=refresh_token" in captured["body"]
    assert "refresh_token=TG-old-refresh" in captured["body"]
    assert token == TokenResponse(
        access_token="APP_USR-token",
        refresh_token="TG-new-refresh",
        expires_in=21600,
        user_id=111222333,
    )


def test_refresh_access_token_retries_on_rate_limit_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                429, headers={"Retry-After": "0"}, json={"message": "rate limited"}
            )
        return httpx.Response(200, json=_token_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))

    token = refresh_access_token(_config(), "TG-old", client=client)

    assert calls["count"] == 2
    assert token.access_token == "APP_USR-token"


def test_refresh_access_token_gives_up_after_max_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        refresh_access_token(_config(), "TG-old", client=client)


def test_refresh_access_token_does_not_retry_on_client_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"message": "invalid_grant"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        refresh_access_token(_config(), "TG-old", client=client)

    assert calls["count"] == 1


def test_iter_orders_paginates_until_total_reached():
    page_size = 2
    all_orders = [{"id": i} for i in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        page = all_orders[offset : offset + page_size]
        return httpx.Response(
            200,
            json={
                "results": page,
                "paging": {"total": len(all_orders), "offset": offset, "limit": page_size},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    orders = list(iter_orders("token123", buyer_id=999, client=client, page_size=page_size))

    assert [o["id"] for o in orders] == [0, 1, 2, 3, 4]


def test_iter_orders_sends_bearer_token_and_buyer_id():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"results": [], "paging": {"total": 0}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    list(iter_orders("token123", buyer_id=999, client=client))

    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.headers["Authorization"] == "Bearer token123"
    assert request.url.params["buyer"] == "999"


def test_iter_orders_stops_on_empty_page_even_if_total_not_reached():
    """Defesa contra total inconsistente vindo da API — nunca fazer polling infinito."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [], "paging": {"total": 999}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    orders = list(iter_orders("token123", buyer_id=999, client=client, page_size=10))

    assert orders == []
