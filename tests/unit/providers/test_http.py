import httpx
import pytest

from voice_agent.domain.ports import ProviderError
from voice_agent.providers.http import json_body, post_with_retry


def test_json_body_rejects_list_body() -> None:
    with pytest.raises(ProviderError) as err:
        json_body("v", httpx.Response(200, json=[1, 2]))
    assert not err.value.retryable


def test_json_body_rejects_non_json() -> None:
    with pytest.raises(ProviderError):
        json_body("v", httpx.Response(200, content=b"<html>"))


def _client(statuses: list[int]) -> tuple[httpx.AsyncClient, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(statuses[len(calls) - 1], json={"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def test_retries_429_then_succeeds() -> None:
    client, calls = _client([429, 200])
    resp = await post_with_retry("v", client, "https://x.test", backoff=0)
    assert resp.status_code == 200 and len(calls) == 2


async def test_gives_up_after_two_retries() -> None:
    client, calls = _client([503, 503, 503])
    with pytest.raises(ProviderError) as err:
        await post_with_retry("v", client, "https://x.test", backoff=0)
    assert err.value.retryable and len(calls) == 3


async def test_client_error_is_not_retried() -> None:
    client, calls = _client([401])
    with pytest.raises(ProviderError) as err:
        await post_with_retry("v", client, "https://x.test", backoff=0)
    assert not err.value.retryable and len(calls) == 1
    assert "401" in str(err.value)


async def test_network_error_becomes_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        await post_with_retry("v", client, "https://x.test", backoff=0)
