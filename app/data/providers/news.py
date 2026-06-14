"""Keyless news provider.

Pulls gold-relevant headlines from RSS (parsed with the standard library, so no
fragile feed dependency) and, when a key is present, supplements with NewsAPI.
Returns raw items; classification / interpretation happens in the news engine
and narrative layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from app.data.providers.base import ProviderError, get_json, http_get

# Query-based feeds are the most robust keyless sources.
RSS_FEEDS = [
    ("Google News", "https://news.google.com/rss/search?q=gold+price+OR+gold+market+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News", "https://news.google.com/rss/search?q=gold+Federal+Reserve+OR+real+yields+OR+dollar+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("Kitco", "https://www.kitco.com/rss/news.xml"),
]

NEWSAPI_URL = "https://newsapi.org/v2/everything"


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # Strip rudimentary HTML tags that sometimes appear in descriptions.
    out, depth = [], 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return " ".join("".join(out).split())


def _parse_rss(xml_text: str, source: str) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0
    for item in root.iter("item"):
        title = item.findtext("title")
        link = item.findtext("link")
        date = _parse_date(item.findtext("pubDate"))
        desc = _clean(item.findtext("description"))
        if title:
            items.append({"headline": _clean(title), "url": link or "",
                          "source": source, "published_at": date, "summary": desc})

    # Atom fallback
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = entry.findtext("a:title", namespaces=ns)
            link_el = entry.find("a:link", namespaces=ns)
            link = link_el.get("href") if link_el is not None else ""
            date = _parse_date(entry.findtext("a:updated", namespaces=ns))
            desc = _clean(entry.findtext("a:summary", namespaces=ns))
            if title:
                items.append({"headline": _clean(title), "url": link or "",
                              "source": source, "published_at": date, "summary": desc})
    return items


def _fetch_newsapi(key: str, timeout: int, limit: int) -> list[dict]:
    data = get_json(
        NEWSAPI_URL,
        params={"q": "gold price OR gold market", "language": "en",
                "sortBy": "publishedAt", "pageSize": limit, "apiKey": key},
        timeout=timeout,
    )
    out = []
    for art in data.get("articles", []):
        out.append({
            "headline": art.get("title", ""),
            "url": art.get("url", ""),
            "source": (art.get("source") or {}).get("name", "NewsAPI"),
            "published_at": _parse_date(art.get("publishedAt")),
            "summary": _clean(art.get("description")),
        })
    return out


def fetch_news(newsapi_key: str | None = None, timeout: int = 12,
               limit: int = 30) -> list[dict]:
    collected: list[dict] = []
    errors = 0
    for source, url in RSS_FEEDS:
        try:
            resp = http_get(url, timeout=timeout)
            collected.extend(_parse_rss(resp.text, source))
        except ProviderError:
            errors += 1
            continue

    if newsapi_key:
        try:
            collected.extend(_fetch_newsapi(newsapi_key, timeout, limit))
        except ProviderError:
            pass

    if not collected:
        raise ProviderError(f"no news feeds reachable ({errors} errors)")

    # De-duplicate by headline, newest first.
    seen, unique = set(), []
    for item in collected:
        key = item["headline"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    def sort_key(it: dict):
        dt = it.get("published_at")
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    unique.sort(key=sort_key, reverse=True)
    return unique[:limit]
