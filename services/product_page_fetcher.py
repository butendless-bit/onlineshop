"""e-himart 상품 페이지 스크래퍼 — 실제 상품 정보를 프롬프트 생성에 활용."""

from __future__ import annotations

import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT = 8
_MAX_RETRIES = 2


def _get_text(soup: BeautifulSoup, selector: str, default: str = "") -> str:
    el = soup.select_one(selector)
    return el.get_text(separator=" ", strip=True) if el else default


def _clean(text: str) -> str:
    """불필요한 공백·특수문자 정리."""
    text = re.sub(r"[\t\r\n]+", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _fetch_html(url: str) -> str | None:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
        except Exception:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(0.5)
    return None


def _extract_selling_points(soup: BeautifulSoup) -> list[str]:
    """상품 상세 페이지에서 판매 포인트·특장점 추출."""
    points: list[str] = []

    # 상품 특징 / 주요 특징 섹션
    for sel in [
        ".goods-feature li",
        ".product-feature li",
        ".spec-point li",
        ".key-feature li",
        ".item-point li",
        ".goods-point li",
        ".prod-point li",
        ".benefit-item",
        ".goods-info-summary li",
        ".summary-item",
    ]:
        items = soup.select(sel)
        for item in items[:6]:
            txt = _clean(item.get_text())
            if txt and len(txt) > 5 and txt not in points:
                points.append(txt)
        if points:
            break

    # 상품 상세 이미지 alt 텍스트에서도 추출 (간혹 key feature 이미지들)
    if not points:
        for img in soup.select(".goods-detail-area img, .product-detail img")[:10]:
            alt = (img.get("alt") or "").strip()
            if alt and len(alt) > 8 and len(alt) < 60 and alt not in points:
                points.append(alt)

    return points[:5]


def _extract_description(soup: BeautifulSoup) -> str:
    """상품 소개 텍스트 추출."""
    for sel in [
        ".goods-intro",
        ".product-intro",
        ".goods-summary",
        ".product-summary",
        ".item-intro",
        ".goods-description",
        ".detail-intro",
        "meta[name='description']",
        "meta[property='og:description']",
    ]:
        if sel.startswith("meta"):
            el = soup.select_one(sel)
            if el:
                content = (el.get("content") or "").strip()
                if len(content) > 20:
                    return _clean(content)
        else:
            el = soup.select_one(sel)
            if el:
                txt = _clean(el.get_text())
                if len(txt) > 20:
                    return txt[:300]
    return ""


def _extract_review_info(soup: BeautifulSoup) -> dict[str, Any]:
    """리뷰 수, 평점 정보 추출."""
    info: dict[str, Any] = {}

    # 리뷰 수
    for sel in [
        ".review-count",
        ".review-cnt",
        ".goods-review-count",
        "[class*='review'] [class*='count']",
        "[class*='review'] [class*='cnt']",
    ]:
        el = soup.select_one(sel)
        if el:
            txt = re.sub(r"[^\d]", "", el.get_text())
            if txt:
                info["review_count"] = int(txt)
                break

    # 평점
    for sel in [".rating-score", ".star-rating", ".review-score", "[class*='rating'][class*='score']"]:
        el = soup.select_one(sel)
        if el:
            txt = re.sub(r"[^\d.]", "", el.get_text())
            try:
                score = float(txt)
                if 0 < score <= 5:
                    info["rating"] = score
            except Exception:
                pass
            break

    return info


def _extract_spec_highlights(soup: BeautifulSoup) -> list[str]:
    """스펙 테이블에서 핵심 스펙 추출 (소비자가 알면 좋을 것들)."""
    highlights: list[str] = []
    important_keys = {
        "에너지등급", "에너지 등급", "소비전력", "용량", "정격용량",
        "세탁용량", "건조용량", "냉장용량", "냉동용량",
        "화면크기", "해상도", "방식", "소음", "소음(운전시)",
        "인버터", "제조국", "원산지", "A/S",
    }

    for table in soup.select("table.spec-table, .spec-list table, .goods-spec table, table[class*='spec']"):
        rows = table.select("tr")
        for row in rows:
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            key = _clean(th.get_text())
            val = _clean(td.get_text())
            if not val or val in ("-", "해당없음", ""):
                continue
            if any(k in key for k in important_keys):
                highlights.append(f"{key}: {val}")
        if highlights:
            break

    return highlights[:4]


def _extract_og_title(soup: BeautifulSoup) -> str:
    el = soup.select_one("meta[property='og:title']")
    if el:
        return _clean(el.get("content") or "")
    el = soup.select_one("title")
    return _clean(el.get_text()) if el else ""


def fetch_product_page(product_url: str) -> dict[str, Any]:
    """
    e-himart 상품 페이지에서 프롬프트 생성에 필요한 데이터를 추출.

    반환:
        {
            "title": str,           # 페이지 상품명
            "description": str,     # 상품 소개 텍스트
            "selling_points": list, # 판매 포인트 (최대 5개)
            "spec_highlights": list,# 핵심 스펙 (최대 4개)
            "review_count": int,    # 리뷰 수 (0이면 정보 없음)
            "rating": float,        # 평점 (0이면 정보 없음)
            "url": str,             # 원본 URL
            "fetched": bool,        # 성공적으로 가져왔는지 여부
        }
    """
    if not product_url or not product_url.startswith("http"):
        return _empty_result(product_url)

    html = _fetch_html(product_url)
    if not html:
        return _empty_result(product_url)

    soup = BeautifulSoup(html, "html.parser")

    description = _extract_description(soup)
    selling_points = _extract_selling_points(soup)
    spec_highlights = _extract_spec_highlights(soup)
    review_info = _extract_review_info(soup)
    title = _extract_og_title(soup)

    return {
        "title": title,
        "description": description,
        "selling_points": selling_points,
        "spec_highlights": spec_highlights,
        "review_count": review_info.get("review_count", 0),
        "rating": review_info.get("rating", 0.0),
        "url": product_url,
        "fetched": bool(description or selling_points or spec_highlights),
    }


def _empty_result(url: str) -> dict[str, Any]:
    return {
        "title": "",
        "description": "",
        "selling_points": [],
        "spec_highlights": [],
        "review_count": 0,
        "rating": 0.0,
        "url": url or "",
        "fetched": False,
    }


def enrich_products_with_page_data(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    상품 목록에 e-himart 페이지 스크래핑 데이터를 추가.
    각 상품에 `page_data` 키로 결과를 붙여서 반환.
    실패해도 원본 상품 데이터는 보존.
    """
    enriched = []
    for product in products:
        url = product.get("product_url") or ""
        try:
            page_data = fetch_product_page(url) if url else _empty_result(url)
        except Exception:
            page_data = _empty_result(url)
        enriched.append({**product, "page_data": page_data})
    return enriched
