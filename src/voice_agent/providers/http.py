"""Shared HTTP plumbing for vendor calls (standards §3: 2 retries, backoff + jitter)."""

import asyncio
import random
from typing import Any

import httpx

from voice_agent.domain.ports import ProviderError


def open_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0))


async def post_with_retry(
    provider: str,
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = 2,
    backoff: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """POST; retry 429/5xx/network errors, raise ProviderError on anything else or when out of tries."""
    error = ProviderError(provider, "no attempt made")
    for attempt in range(retries + 1):
        try:
            resp = await client.post(url, **kwargs)
        except httpx.TransportError as exc:
            error = ProviderError(provider, f"network error: {exc}", retryable=True)
        else:
            if resp.status_code < 400:
                return resp
            retryable = resp.status_code == 429 or resp.status_code >= 500
            error = ProviderError(
                provider, f"HTTP {resp.status_code}: {resp.text[:200]}", retryable
            )
            if not retryable:
                raise error
        if attempt < retries:
            await asyncio.sleep(backoff * 2**attempt + random.uniform(0, backoff / 2))
    raise error
