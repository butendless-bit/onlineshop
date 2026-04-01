"""Fetch richer product context from e-himart product detail pages."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

try:
    import requests as _requests
    from bs4 import BeautifulSoup as _BS
except ImportError:
    _requests = None  # type: ignore
    _BS = None  # type: ignore


_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 3600


def _get_cached(url: str) -> dict[str, Any] | None:
    with _cache_lock:
        entry = _cache.get(url)
    if not entry:
        return None
    if time.time() - float(entry["ts"]) > _CACHE_TTL:
        return None
    return dict(entry["data"])


def _set_cached(url: str, data: dict[str, Any]) -> None:
    with _cache_lock:
        if len(_cache) >= 200:
            oldest = min(_cache, key=lambda key: float(_cache[key]["ts"]))
            del _cache[oldest]
        _cache[url] = {"data": dict(data), "ts": time.time()}


def _to_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _flatten_json_ld(payload: Any) -> list[dict[str, Any]]:
    stack = _to_list(payload)
    items: list[dict[str, Any]] = []
    while stack:
        node = stack.pop(0)
        if isinstance(node, list):
            stack[:0] = node
            continue
        if not isinstance(node, dict):
            continue
        if "@graph" in node:
            stack[:0] = _to_list(node.get("@graph"))
        items.append(node)
    return items


def _type_names(node: dict[str, Any]) -> set[str]:
    values = _to_list(node.get("@type"))
    return {str(value).strip() for value in values if str(value).strip()}


def _pick_product_node(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    for node in nodes:
        if "Product" in _type_names(node):
            return node
    return {}


def _pick_breadcrumb_node(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    for node in nodes:
        if "BreadcrumbList" in _type_names(node):
            return node
    return {}


def _split_feature_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    results: list[str] = []
    for chunk in chunks:
        cleaned = re.sub(r"\s+", " ", chunk).strip(" -\t\r\n")
        if len(cleaned) >= 8 and cleaned not in results:
            results.append(cleaned)
    return results[:6]


def fetch_product_detail(product_url: str, timeout: int = 8) -> dict[str, Any]:
    if not product_url:
        return {}

    cached = _get_cached(product_url)
    if cached is not None:
        return cached

    if _requests is None or _BS is None:
        return {}

    try:
        response = _requests.get(
            product_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": "https://www.e-himart.co.kr/",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        soup = _BS(response.content, "html.parser")

        json_ld_nodes: list[dict[str, Any]] = []
        for script in soup.find_all("script", type="application/ld+json"):
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            try:
                json_ld_nodes.extend(_flatten_json_ld(json.loads(raw)))
            except Exception:
                continue

        product_ld = _pick_product_node(json_ld_nodes)
        breadcrumb_ld = _pick_breadcrumb_node(json_ld_nodes)
        if not product_ld:
            _set_cached(product_url, {})
            return {}

        description = str(product_ld.get("description") or "").strip()
        features = _split_feature_sentences(description)

        specs: list[dict[str, str]] = []
        for prop in _to_list(product_ld.get("additionalProperty")):
            if not isinstance(prop, dict):
                continue
            name = str(prop.get("name") or "").strip()
            value = str(prop.get("value") or "").strip()
            if name and value:
                specs.append({"name": name, "value": value})

        aggregate = product_ld.get("aggregateRating") or {}
        try:
            rating = float(aggregate.get("ratingValue") or 0)
        except Exception:
            rating = 0.0
        try:
            review_count = int(aggregate.get("reviewCount") or 0)
        except Exception:
            review_count = 0

        offers = product_ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        try:
            page_price = int(float((offers or {}).get("price") or 0))
        except Exception:
            page_price = 0

        breadcrumb_parts: list[str] = []
        for element in _to_list(breadcrumb_ld.get("itemListElement")):
            if not isinstance(element, dict):
                continue
            name = ""
            item = element.get("item")
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            if not name:
                name = str(element.get("name") or "").strip()
            if name:
                breadcrumb_parts.append(name)

        keywords = product_ld.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [item.strip() for item in keywords.split(",") if item.strip()]

        result = {
            "description": description,
            "feature_sentences": features,
            "specs": specs,
            "keywords": list(keywords),
            "brand": str((product_ld.get("brand") or {}).get("name") or "").strip(),
            "category_full": " > ".join(breadcrumb_parts) or str(product_ld.get("category") or "").strip(),
            "rating": rating,
            "review_count": review_count,
            "page_price": page_price,
        }
        _set_cached(product_url, result)
        return result
    except Exception:
        _set_cached(product_url, {})
        return {}


def enrich_products_from_pages(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for product in products:
        item = dict(product)
        product_url = str(item.get("product_url") or "").strip()
        page_data = fetch_product_detail(product_url) if product_url else {}

        existing_bullets = []
        for bullet in item.get("featureBullets") or []:
            text = str(bullet).strip()
            if text and len(text) > 5 and text not in existing_bullets:
                existing_bullets.append(text)

        if page_data:
            merged_bullets = existing_bullets[:]
            for sentence in page_data.get("feature_sentences") or []:
                text = str(sentence).strip()
                if text and text not in merged_bullets:
                    merged_bullets.append(text)

            item["featureBullets"] = merged_bullets[:5]
            item["pageSpecs"] = page_data.get("specs") or []
            item["pageKeywords"] = page_data.get("keywords") or []
            item["productDescription"] = page_data.get("description") or ""

            if page_data.get("brand") and not item.get("brand"):
                item["brand"] = page_data["brand"]
            if page_data.get("category_full"):
                item["categoryFull"] = page_data["category_full"]
            if page_data.get("rating"):
                item["pageRating"] = page_data["rating"]
            if page_data.get("review_count") and not item.get("review_count"):
                item["review_count"] = page_data["review_count"]
            if page_data.get("page_price") and not item.get("pagePrice"):
                item["pagePrice"] = page_data["page_price"]

        enriched.append(item)
    return enriched
