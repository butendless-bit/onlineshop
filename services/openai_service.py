"""Manual prompt workflow helpers for promo copy generation."""

from __future__ import annotations

import re
from typing import Any

from services.product_enricher import enrich_products_from_pages
from services.prompt_builders import build_blog_messages, build_instagram_messages


class OpenAIServiceError(RuntimeError):
    pass


_CATEGORY_LABELS = {
    "refrigerator": "냉장고",
    "kimchi": "김치냉장고",
    "washer": "세탁기",
    "dryer": "건조기",
    "tv": "TV",
    "aircon": "에어컨",
    "airpurifier": "공기청정기",
    "vacuum": "청소기",
    "dishwasher": "식기세척기",
    "range": "전기레인지",
    "laptop": "노트북",
    "tablet": "태블릿",
}

_CATEGORY_BEST_FOR = {
    "refrigerator": "신혼집이나 이사 준비로 냉장고를 오래 쓸 기본 가전으로 비교하는 고객",
    "kimchi": "김치 보관은 물론 반찬과 식재료까지 함께 정리하고 싶은 고객",
    "washer": "세탁 용량과 설치 공간을 함께 고려하는 고객",
    "dryer": "세탁부터 건조까지 한 번에 정리하고 싶은 고객",
    "tv": "거실 메인 TV를 바꾸거나 화면 크기와 화질 체감을 중요하게 보는 고객",
    "aircon": "평형과 설치 조건을 함께 고려해야 하는 고객",
    "airpurifier": "집 구조와 사용 면적에 맞는 관리 편의성을 보는 고객",
    "vacuum": "청소 빈도와 동선, 무게감까지 체감이 중요한 고객",
}

_CATEGORY_CAUTIONS = {
    "refrigerator": "문 열림 공간과 주방 동선을 함께 확인해보면 선택이 더 쉬워집니다.",
    "kimchi": "설치 위치와 도어 열림 방향을 미리 체크해두면 좋습니다.",
    "washer": "배수 위치와 문 열림 방향을 같이 봐야 설치가 편합니다.",
    "dryer": "상단 설치인지 직렬 설치인지 먼저 정하면 모델 선택이 훨씬 쉬워집니다.",
    "tv": "시청 거리와 설치 위치에 따라 만족도가 달라져서 화면 크기를 함께 보는 편이 좋습니다.",
    "aircon": "설치 환경과 배관 조건에 따라 추천 모델이 달라질 수 있습니다.",
    "airpurifier": "사용 면적과 필터 관리 비용까지 같이 보면 더 정확합니다.",
    "vacuum": "흡입력뿐 아니라 무게감과 손목 부담도 함께 보는 편이 좋습니다.",
}

_RAW_SPEC_PATTERNS = [
    r"\bsize\s*group\b",
    r"\b(tv|fridge|washer|dryer|aircon|vacuum|dish|range|laptop|tablet)\s*(type|size|cap|brand|burner)\b",
    r"^(small|medium|large|top|stand|drum|builtin|integrated|white|black|silver)$",
]


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _format_price(value: Any) -> str:
    try:
        amount = int(float(value or 0))
    except Exception:
        return ""
    if amount <= 0:
        return ""
    if amount >= 10000:
        return f"{amount:,}원"
    return f"{amount:,}원"


def _category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category or "가전")


def _extract_brand(name: str) -> str:
    upper = str(name or "").upper()
    for brand in [
        "SAMSUNG",
        "LG",
        "TCL",
        "BESPOKE",
        "WHISEN",
        "DIOS",
        "BOSCH",
        "MIELE",
        "LIEBHERR",
        "AEG",
        "DYSON",
        "ROBOROCK",
        "APPLE",
        "WINIA",
        "CUCKOO",
        "CUCHEN",
    ]:
        if brand in upper:
            return brand
    return ""


def _extract_model_code(name: str) -> str:
    text = str(name or "")
    for pattern in [r"\b([A-Z]{1,5}\d[A-Z0-9\-]{3,})\b", r"\b(\d{2,3}[A-Z][A-Z0-9\-]{2,})\b"]:
        match = re.search(pattern, text.upper())
        if match:
            return match.group(1)
    return ""


def _extract_capacity_token(name: str) -> str:
    text = str(name or "")
    for pattern, suffix in [
        (r"(\d{2,4})\s*L", "L"),
        (r"(\d{1,2}(?:\.\d)?)\s*KG", "kg"),
        (r"(\d{2,3})\s*(?:인치|\")", "인치"),
        (r"(\d{1,3}(?:\.\d)?)\s*평", "평"),
    ]:
        match = re.search(pattern, text, re.I)
        if match:
            return f"{match.group(1)}{suffix}"
    return ""


def _short_product_name(product_name: str, category: str = "", limit: int = 28) -> str:
    text = re.sub(r"\[[^\]]*\]|\([^\)]*\)", " ", product_name or "")
    text = re.sub(r"\s+", " ", text).strip(" _-")
    if len(text) <= limit:
        return text
    candidate = " ".join(
        part
        for part in [
            _extract_brand(text),
            _extract_model_code(text),
            _extract_capacity_token(text),
            _category_label(category),
        ]
        if part
    ).strip()
    return candidate[:limit].strip() or text[:limit].strip()


def _price_snapshot(product: dict[str, Any]) -> dict[str, int]:
    def pick(keys: list[str]) -> int:
        for key in keys:
            try:
                value = int(float(product.get(key) or 0))
            except Exception:
                value = 0
            if value > 0:
                return value
        return 0

    return {
        "original": pick(["original_price", "originalPrice", "price", "pagePrice"]),
        "benefit": pick(["benefit_price", "benefitPrice", "sale_price", "salePrice", "pagePrice", "monthly_fee"]),
    }


def _price_summary(product: dict[str, Any]) -> str:
    snapshot = _price_snapshot(product)
    original = snapshot["original"]
    benefit = snapshot["benefit"]
    if not benefit:
        return "가격은 매장 문의 기준"
    if original and original > benefit:
        return f"혜택가 {_format_price(benefit)}, 기존가 대비 {_format_price(original - benefit)} 절약"
    return f"혜택가 {_format_price(benefit)}"


def _is_low_signal_feature(text: str) -> bool:
    lowered = text.lower()
    if len(text) < 8:
        return True
    return any(re.search(pattern, lowered) for pattern in _RAW_SPEC_PATTERNS)


def _sentence_chunks(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    results: list[str] = []
    for piece in pieces:
        cleaned = _clean_text(piece).strip(" -")
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def _top_features(product: dict[str, Any]) -> list[str]:
    results: list[str] = []
    description = _clean_text(product.get("productDescription"))
    for sentence in _sentence_chunks(description):
        if len(sentence) >= 12 and not _is_low_signal_feature(sentence):
            results.append(sentence)
    for bullet in product.get("featureBullets") or []:
        text = _clean_text(bullet)
        if text and not _is_low_signal_feature(text) and text not in results:
            results.append(text)
    return results[:4]


def _key_specs(product: dict[str, Any]) -> list[str]:
    specs: list[str] = []
    for spec in product.get("pageSpecs") or []:
        name = _clean_text(spec.get("name"))
        value = _clean_text(spec.get("value"))
        if not name or not value:
            continue
        combined = f"{name}: {value}"
        if not _is_low_signal_feature(combined):
            specs.append(combined)
    return specs[:5]


def _best_for(product: dict[str, Any]) -> str:
    reason = _clean_text(product.get("reason") or product.get("recommendationReason"))
    if reason and not _is_low_signal_feature(reason):
        return reason
    return _CATEGORY_BEST_FOR.get(str(product.get("category") or ""), "비교 포인트를 생활 기준으로 보고 싶은 고객")


def _caution(product: dict[str, Any]) -> str:
    return _CATEGORY_CAUTIONS.get(
        str(product.get("category") or ""),
        "설치 환경과 사용 습관을 함께 보고 고르는 편이 좋습니다.",
    )


def _review_summary(product: dict[str, Any]) -> str:
    rating = product.get("pageRating") or product.get("rating")
    review_count = product.get("review_count") or 0
    try:
        rating_value = float(rating or 0)
    except Exception:
        rating_value = 0.0
    try:
        reviews = int(review_count or 0)
    except Exception:
        reviews = 0
    if rating_value > 0 and reviews > 0:
        return f"상세페이지 기준 평점 {rating_value:.1f}, 리뷰 {reviews:,}건"
    if reviews > 0:
        return f"상세페이지 기준 리뷰 {reviews:,}건"
    return ""


def _product_dossier(product: dict[str, Any]) -> dict[str, Any]:
    snapshot = _price_snapshot(product)
    original = snapshot["original"]
    benefit = snapshot["benefit"]
    return {
        "name": _clean_text(product.get("product_name") or product.get("productName")),
        "short_name": _short_product_name(
            _clean_text(product.get("product_name") or product.get("productName")),
            category=str(product.get("category") or ""),
        ),
        "category": _category_label(str(product.get("category") or "")),
        "category_full": _clean_text(product.get("categoryFull")),
        "brand": _clean_text(product.get("brand")),
        "product_url": _clean_text(product.get("product_url")),
        "price_summary": _price_summary(product),
        "benefit_price": benefit,
        "original_price": original,
        "savings_amount": max(original - benefit, 0) if original and benefit else 0,
        "features": _top_features(product),
        "key_specs": _key_specs(product),
        "best_for": _best_for(product),
        "caution": _caution(product),
        "social_proof": _review_summary(product),
        "card_benefit_text": _clean_text(product.get("card_benefit_text")),
    }


def _enrich_payload(payload: dict[str, Any]) -> dict[str, Any]:
    products = payload.get("products") or []
    enriched_products = enrich_products_from_pages(products) if products else []
    dossiers = [_product_dossier(product) for product in enriched_products]
    return {**payload, "products": enriched_products, "product_dossiers": dossiers}


def _build_prompt_package(messages: list[dict[str, str]], *, mode: str) -> dict[str, Any]:
    system_prompt = next((message["content"] for message in messages if message.get("role") == "system"), "")
    user_prompt = next((message["content"] for message in messages if message.get("role") == "user"), "")
    single_prompt = f"{system_prompt}\n\n{user_prompt}".strip()
    return {
        "mode": mode,
        "single_prompt": single_prompt,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "combined_prompt": single_prompt,
        "quick_steps": [
            "1. ChatGPT를 새 대화로 엽니다.",
            "2. 아래 프롬프트 1개만 그대로 붙여 넣습니다.",
            "3. 생성 결과를 검토하고 바로 실사용합니다.",
        ],
    }


def generate_instagram_copy_v2(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = _enrich_payload(payload)
    prompt_package = _build_prompt_package(build_instagram_messages(prepared), mode="manual_prompt")
    return {
        "workflow_mode": "manual_prompt",
        "prompt_package": prompt_package,
        "caption": prompt_package["single_prompt"],
    }


def generate_instagram_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return generate_instagram_copy_v2(payload)


def generate_blog_copy_v2(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = _enrich_payload(payload)
    prompt_package = _build_prompt_package(build_blog_messages(prepared), mode="manual_prompt")
    return {
        "workflow_mode": "manual_prompt",
        "prompt_package": prompt_package,
        "body": prompt_package["single_prompt"],
    }


def generate_blog_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return generate_blog_copy_v2(payload)


def recommend_campaign_info(
    products: list[dict[str, Any]], *, store_name: str = "", max_event_len: int = 18, max_campaign_len: int = 24
) -> dict[str, str]:
    prepared = _enrich_payload({"products": products, "store_name": store_name})
    dossiers = prepared.get("product_dossiers") or []
    if not dossiers:
        return {"event_title": "온라인 특가전", "campaign_name": f"{store_name or '하이마트'} 추천 행사"}
    categories = sorted({item["category"] for item in dossiers})
    event_title = (" / ".join(categories[:2]) + " 특가")[:max_event_len]
    return {"event_title": event_title, "campaign_name": f"{store_name or '하이마트'} {event_title}"[:max_campaign_len]}


def recommend_landing_copy(products: list[dict[str, Any]], *, store_name: str = "", event_title: str = "") -> dict[str, str]:
    return {
        "landing_title": event_title or "온라인 가전 특가 기획전",
        "intro_text": "실사용 만족도와 가격 메리트를 함께 보기 좋은 행사 모델만 모아 정리했습니다.",
    }


def generate_short_product_name(product_name: str, *, category: str = "", limit: int = 13) -> str:
    return _short_product_name(product_name, category=category, limit=limit)


def generate_creative_title(product_name: str, *, category: str = "", limit: int = 15) -> str:
    return _short_product_name(product_name, category=category, limit=limit)
