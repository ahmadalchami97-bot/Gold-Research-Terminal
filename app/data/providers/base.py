"""Shared HTTP helpers and the provider exception type.

Providers are thin functions that return tidy pandas objects with a
``DatetimeIndex``. They never raise into the UI: the data service catches
``ProviderError`` and falls back to the bundled snapshot.
"""
from __future__ import annotations

import io

import pandas as pd
import requests

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)


class ProviderError(RuntimeError):
    """Raised when a live data source is unavailable or returns bad data."""


def http_get(url: str, *, timeout: int = 12, params: dict | None = None,
             headers: dict | None = None) -> requests.Response:
    """GET with a browser user-agent and uniform error surface."""
    hdrs = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    try:
        resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    except requests.RequestException as exc:  # network / DNS / timeout
        raise ProviderError(f"request failed: {exc}") from exc
    if resp.status_code != 200:
        raise ProviderError(f"HTTP {resp.status_code} for {resp.url}")
    return resp


def get_csv(url: str, *, timeout: int = 12, params: dict | None = None,
            **read_csv_kwargs) -> pd.DataFrame:
    resp = http_get(url, timeout=timeout, params=params)
    try:
        return pd.read_csv(io.StringIO(resp.text), **read_csv_kwargs)
    except Exception as exc:  # malformed payload
        raise ProviderError(f"could not parse CSV from {url}: {exc}") from exc


def get_json(url: str, *, timeout: int = 12, params: dict | None = None) -> dict:
    resp = http_get(url, timeout=timeout, params=params)
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(f"could not parse JSON from {url}: {exc}") from exc
