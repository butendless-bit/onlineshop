"""Anthropic Claude 전용 AI 서비스 — OpenAI 의존성 없음."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from services.prompt_builders import build_blog_messages, build_instagram_messages
from services.product_enricher import enrich_products_from_pages

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore


class ClaudeServiceError(RuntimeError):
    pass


_DEFAULT_MODEL = "claude-sonnet-4-6"
_FAST_MODEL    = "claude-haiku-4-5-20251001"

PROMO_KEYWORDS = ["온라인", "가성비", "최저가도전", "특가모델", "특가상품", "행사상품"]

_CAT_KO = {
    "refrigerator": "냉장고", "kimchi": "김치냉장고", "washer": "세탁기",
    "dryer": "건조기", "tv": "TV", "aircon": "에어컨",
    "airpurifier": "공기청정기", "vacuum": "청소기", "dishwasher": "식기세척기",
    "range": "레인지", "laptop": "노트북", "tablet": "태블릿",
}

_BRAND_MAP = [
    ("삼성",   ["삼성", "SAMSUNG"]),
    ("엘지",   ["LG", "엘지", "LG전자", "휘센"]),
    ("위니아", ["위니아", "WINIA"]),
    ("딤채",   ["딤채", "DIMCHAE"]),
    ("캐리어", ["캐리어", "CARRIER"]),
    ("쿠쿠",   ["쿠쿠", "CUCKOO"]),
    ("쿠첸",   ["쿠첸", "CUCHEN"]),
    ("애플",   ["애플", "APPLE", "IPHONE", "IPAD", "MACBOOK"]),
    ("다이슨", ["다이슨", "DYSON"]),
    ("DJI",    ["DJI"]),
    ("로보락", ["로보락", "ROBOROCK"]),
]


# ── 순수 헬퍼 함수 ────────────────────────────────────────────────────────────

def _category_label(category: str) -> str:
    return _CAT_KO.get(category, "추천상품")


def _best_price_value(product: dict[str, Any]) -> int:
    for k in ("benefit_price", "benefitPrice", "sale_price", "salePrice",
              "original_price", "originalPrice", "price", "monthly_fee", "subscriptionPrice"):
        v = product.get(k)
        try:
            if v:
                return int(float(v))
        except Exception:
            continue
    return 0


def _discount_text(product: dict[str, Any]) -> str:
    try:
        original = int(float(
            product.get("original_price") or product.get("originalPrice") or
            product.get("price") or 0
        ))
        current = int(float(
            product.get("benefit_price") or product.get("benefitPrice") or
            product.get("sale_price") or product.get("salePrice") or
            product.get("price") or product.get("monthly_fee") or 0
        ))
    except Exception:
        return "혜택 문의"
    if original > current > 0:
        diff = original - current
        if diff >= 10000:
            return f"기존가 대비 약 {int(round(diff / 10000))}만원 혜택"
        return "기존가 대비 혜택 적용"
    return "행사 혜택 적용"


def _format_price_manwon(value: Any) -> str:
    try:
        n = int(float(value or 0))
    except Exception:
        n = 0
    return f"{int(round(n / 10000))}만원대" if n > 0 else "가격 문의"


def _extract_brand(text: str) -> str:
    upper = str(text or "").upper()
    for label, aliases in _BRAND_MAP:
        if any(a.upper() in upper for a in aliases):
            return label
    return ""


def _extract_liters(text: str) -> str:
    m = re.search(r"(\d{2,4})\s*L", text, re.I)
    return f"{m.group(1)}L" if m else ""


def _extract_kg(text: str) -> str:
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*KG", text, re.I)
    return f"{m.group(1)}KG" if m else ""


def _extract_inches(text: str) -> str:
    m = re.search(r"(\d{2,3})\s*(?:인치|\")", text)
    return f"{m.group(1)}인치" if m else ""


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"\[[^\]]*\]", " ", name or "")
    cleaned = re.sub(r"\([^\)]*\)", " ", cleaned)
    for token in ["증정", "행사", "롯데마트점", "최상급", "기획전", "온라인", "공식", "단독", "방문설치"]:
        cleaned = cleaned.replace(token, "").strip()
    return re.sub(r"\s+", " ", cleaned).strip()


def _heuristic_short_name(name: str, category: str = "", limit: int = 15) -> str:
    cleaned = _normalize_name(name)
    if len(cleaned) <= limit:
        return cleaned

    brand   = _extract_brand(cleaned)
    liters  = _extract_liters(cleaned)
    kg      = _extract_kg(cleaned)
    inches  = _extract_inches(cleaned)

    def _kw(options: list[str]) -> str:
        for o in options:
            if o in cleaned:
                return o
        return ""

    def _join(*parts: str) -> str:
        return " ".join(p for p in parts if p).strip()

    def _best(groups: list[list[str]]) -> str:
        for parts in groups:
            c = "".join(p for p in parts if p)
            s = _join(*parts)
            for candidate in [s, c]:
                if candidate and len(candidate) <= limit:
                    return candidate
        for parts in groups:
            c = "".join(p for p in parts if p)
            if c:
                return c[:limit].strip()
        return ""

    if category == "refrigerator":
        door = _kw(["4도어", "양문형", "비스포크", "일반형"])
        return _best([[brand, liters, door, "냉장고"], [brand, liters, "냉장고"], [brand, "냉장고"]]) or cleaned[:limit]
    if category == "kimchi":
        shape = _kw(["뚜껑형", "스탠드형", "스탠드"])
        return _best([[brand, liters, shape, "김치냉장고"], [brand, shape, "김치냉장고"], [brand, liters, "김치냉장고"]]) or cleaned[:limit]
    if category == "washer":
        shape = _kw(["드럼", "통돌이", "일체형"])
        return _best([[brand, kg, shape, "세탁기"], [brand, shape, "세탁기"], [brand, kg, "세탁기"]]) or cleaned[:limit]
    if category == "dryer":
        feat = _kw(["히트펌프", "일체형"])
        return _best([[brand, kg, feat, "건조기"], [brand, feat, "건조기"], [brand, kg, "건조기"]]) or cleaned[:limit]
    if category == "tv":
        panel = _kw(["OLED", "QLED", "QNED", "LED"])
        return _best([[brand, inches, panel, "TV"], [brand, inches, "TV"], [brand, "TV"]]) or cleaned[:limit]
    if category == "aircon":
        style = _kw(["스탠드", "벽걸이", "2in1"])
        m = re.search(r"(\d+)\s*평", cleaned)
        pyeong = f"{m.group(1)}평" if m else ""
        return _best([[brand, pyeong, style, "에어컨"], [brand, pyeong, "에어컨"], [brand, "에어컨"]]) or cleaned[:limit]
    if category == "laptop":
        return _best([[brand, inches, "노트북"], [brand, "노트북"]]) or cleaned[:limit]
    if category == "tablet":
        return _best([[brand, inches, "태블릿"], [brand, "태블릿"]]) or cleaned[:limit]

    cat_ko = _category_label(category)
    return _best([[brand, cat_ko], [brand]]) or cleaned[:limit]


def _ensure_brand_first(short_name: str, original_name: str, limit: int) -> str:
    candidate = str(short_name or "").strip()
    brand = _extract_brand(original_name or "")
    if not candidate or not brand or candidate.startswith(brand):
        return candidate[:limit].strip()
    without = candidate.replace(brand, "").strip()
    result = f"{brand} {without}".strip()
    return result[:limit].strip()


def _fit_for_from_product(product: dict[str, Any]) -> str:
    category = str(product.get("category") or "")
    reason   = str(product.get("recommendationReason") or product.get("reason") or "").strip()
    if reason and "?" not in reason and len(reason) < 80:
        return reason
    defaults = {
        "refrigerator": "식재료 보관량이 많거나 수납을 꼼꼼히 챙기는 가정에 잘 맞습니다.",
        "kimchi":       "김치 보관량이 많거나 반찬 정리까지 함께 챙기고 싶은 분께 추천드립니다.",
        "washer":       "세탁 용량과 설치 공간을 함께 따져보는 고객께 잘 맞습니다.",
        "dryer":        "세탁 후 건조까지 한 번에 챙기고 싶은 분께 잘 맞습니다.",
        "tv":           "화면 크기와 화질을 함께 따져보시는 고객께 비교해 보기 좋습니다.",
        "aircon":       "냉방 면적과 설치 방식을 함께 따져보시는 분께 잘 맞습니다.",
    }
    return defaults.get(category, "실사용 기준으로 상담 문의가 꾸준히 이어지는 모델입니다.")


def _blog_feature_lines(product: dict[str, Any]) -> list[str]:
    raw = [str(f).strip() for f in (product.get("featureBullets") or []) if str(f).strip()]
    # 영문 내부 태그 필터
    bad = ["cap", "size group", "tv type", "fridge size", "fridge type",
           "washer cap", "dryer cap", "aircon type"]
    lines = [f for f in raw if not any(b in f.lower() for b in bad) and "?" not in f]
    if not lines:
        desc = str(product.get("productDescription") or "").strip()
        if desc and "?" not in desc:
            lines.append(desc[:80])
    return lines[:4]


def _normalize_copy(text: Any) -> str:
    s = str(text or "").strip()
    s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def _josa(word: str, josa_type: str) -> str:
    """받침 유무에 따라 올바른 조사 반환."""
    if not word:
        return josa_type.split("/")[0]
    last = word[-1]
    code = ord(last)
    # 한글 범위인 경우 받침 확인
    if 0xAC00 <= code <= 0xD7A3:
        has_batchim = (code - 0xAC00) % 28 != 0
    else:
        has_batchim = last.isalpha() and last in "bcdghjklmnpqrst"
    pairs = {"은/는": ("은", "는"), "이/가": ("이", "가"), "을/를": ("을", "를"),
             "와/과": ("과", "와"), "으로/로": ("으로", "로")}
    pair = pairs.get(josa_type)
    if not pair:
        return josa_type
    return pair[0] if has_batchim else pair[1]


# ── Claude API ────────────────────────────────────────────────────────────────

def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ClaudeServiceError(
            "ANTHROPIC_API_KEY가 설정되지 않아 AI 문구 생성을 사용할 수 없습니다."
        )
    if _anthropic is None:
        raise ClaudeServiceError(
            "anthropic 패키지가 설치되지 않았습니다. pip install anthropic 을 실행하세요."
        )
    return _anthropic.Anthropic(api_key=api_key)


def _call_claude(messages: list[dict], model: str, max_tokens: int = 2048) -> str:
    """OpenAI 형식 messages → Anthropic API 호출."""
    client = _get_client()
    system_text = ""
    user_msgs: list[dict] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text = msg["content"]
        else:
            user_msgs.append({"role": msg["role"], "content": msg["content"]})

    kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": user_msgs}
    if system_text:
        kwargs["system"] = system_text

    response = client.messages.create(**kwargs)
    return response.content[0].text


def _parse_json(text: str) -> dict:
    text = text.strip()
    if "```json" in text:
        s = text.index("```json") + 7
        text = text[s:text.index("```", s)].strip()
    elif "```" in text:
        s = text.index("```") + 3
        text = text[s:text.index("```", s)].strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    return json.loads(text)


# ── Payload 전처리 ─────────────────────────────────────────────────────────────

def _prepare_instagram_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """featureBullets 에서 내부 태그 제거 후 자연어 포인트만 남김."""
    bad = ["dryer cap", "washer cap", "fridge size", "fridge type",
           "size group", "tv type", "aircon type", "kimchi_size", "kimchi_type"]
    products = []
    for p in (payload.get("products") or []):
        bullets = [str(b).strip() for b in (p.get("featureBullets") or [])
                   if not any(t in str(b).lower() for t in bad) and "?" not in str(b)][:2]
        products.append({**p, "featureBullets": bullets})
    return {**payload, "products": products}


def _prepare_blog_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """각 상품을 product_notes 구조로 변환."""
    notes: list[dict] = []
    for p in (payload.get("products") or []):
        full_name = str(p.get("product_name") or p.get("productName") or "").strip()
        short_name = _heuristic_short_name(full_name, category=p.get("category", ""), limit=16)

        # 혜택가·원가 분리 추출
        benefit: int | None = None
        original: int | None = None
        for k in ("benefit_price", "benefitPrice"):
            v = p.get(k)
            try:
                if v and int(float(v)) > 0:
                    benefit = int(float(v)); break
            except Exception:
                pass
        for k in ("original_price", "originalPrice", "price"):
            v = p.get(k)
            try:
                if v and int(float(v)) > 0:
                    original = int(float(v)); break
            except Exception:
                pass
        if not benefit:
            for k in ("sale_price", "salePrice", "price", "monthly_fee"):
                v = p.get(k)
                try:
                    if v and int(float(v)) > 0:
                        benefit = int(float(v)); break
                except Exception:
                    pass

        price_parts = []
        if benefit and benefit > 0:
            price_parts.append(f"혜택가 {int(round(benefit/10000))}만원대")
        if original and benefit and original > benefit:
            price_parts.append(f"기존가 {int(round(original/10000))}만원에서 약 {int(round((original-benefit)/10000))}만원 절약")
        price_merit = " / ".join(price_parts) if price_parts else "가격 문의"

        notes.append({
            "full_name":   full_name or short_name or _category_label(p.get("category", "")),
            "name":        short_name or _category_label(p.get("category", "")),
            "category":    _category_label(p.get("category", "")),
            "strengths":   _blog_feature_lines(p),
            "fit_for":     _fit_for_from_product(p),
            "price_merit": price_merit,
            "pageSpecs":   p.get("pageSpecs") or [],
        })
    return {**payload, "product_notes": notes}


# ── Fallback (AI 실패 시) ──────────────────────────────────────────────────────

def _fallback_instagram(payload: dict[str, Any]) -> dict[str, Any]:
    products = payload.get("products") or []
    store    = payload.get("store_name") or "하이마트"
    phone    = payload.get("phone") or ""
    kakao    = payload.get("kakao_channel_url") or ""

    # 상품 라인 — 브랜드+품목+가격, 상품마다 다른 패턴
    item_lines = []
    for i, p in enumerate(products[:4]):
        name  = _heuristic_short_name(p.get("product_name", ""), category=p.get("category", ""), limit=16)
        price = _format_price_manwon(_best_price_value(p))
        cat   = _category_label(p.get("category", ""))
        patterns = [
            f"✔ {name} — {price}",
            f"→ {name} {price}",
            f"• {name} ({price})",
            f"▸ {cat} | {name} | {price}",
        ]
        item_lines.append(patterns[i % len(patterns)])

    if kakao:
        contact = "카카오톡으로 편하게 문의 주세요 💬"
    elif phone:
        contact = f"☎ {phone} 으로 문의 주세요"
    else:
        contact = f"{store} 매장으로 문의 주세요"

    items_text = "\n".join(item_lines) if item_lines else f"{store} 추천 상품"

    caption = (
        f"이번 주 {store} 특가 모아봤어요 🙌\n\n"
        f"{items_text}\n\n"
        f"가격·재고·설치 조건은 변동될 수 있으니\n"
        f"정확한 건 상담으로 확인하시는 게 빨라요!\n\n"
        f"{contact}"
    )

    hooks = [
        f"이번 주 {store} 온라인 특가 정리해봤어요 👀",
        f"이거 놓치면 후회할 수도 있어요 😅",
    ]

    return {
        "hooks":       hooks,
        "caption":     caption,
        "story_lines": [f"{store} 이번 주 특가", "가격 확인하러 오세요", "상담 문의 환영"],
        "hashtags":    ["#하이마트", "#온라인특가", "#가전할인", "#매장상담", "#이번주특가", "#가전행사",
                        "#부산가전", "#하이마트광복점", "#부산신혼", "#부산인테리어"],
        "dm_reply":    "안녕하세요! 상품 궁금하신 거 있으면 편하게 물어봐 주세요. 재고랑 정확한 혜택 조건 확인해드릴게요 😊",
    }


def _fallback_blog(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_blog_payload(payload)
    notes    = prepared.get("product_notes") or []
    store    = prepared.get("store_name") or "하이마트"
    event    = prepared.get("event_title") or "이번 주 특가"
    phone    = prepared.get("phone") or ""
    kakao    = prepared.get("kakao_channel_url") or ""

    if kakao:
        cta = "궁금한 모델 있으시면 카카오톡으로 편하게 문의해 주세요. 재고 현황과 정확한 혜택 조건 바로 확인해드릴게요."
    elif phone:
        cta = f"{phone}으로 연락 주시면 모델별 차이와 지금 적용 가능한 조건을 자세히 안내해드릴게요."
    else:
        cta = f"{store} 매장에 방문하시거나 문의 주시면 자세한 상담 도와드릴게요."

    # 도입 문단
    name_list = "·".join((n.get("full_name") or n["name"]) for n in notes[:3]) if notes else "추천 가전"
    intro_para = (
        f"가전 구매 전에 온라인에서 모델을 먼저 좁혀보고 매장에서 실제 조건을 확인하시는 분들이 많아졌더라고요.\n"
        f"이번 포스팅에서는 {store}의 {event} 상품 중에서 "
        f"{name_list} 위주로, 어떤 분께 잘 맞는지와 가격 포인트를 솔직하게 정리해봤습니다."
    )

    # 상품별 H2 섹션 — 순차적으로
    h2_starters = [
        lambda n: f"직접 확인해본 {n.get('full_name') or n['name']}",
        lambda n: f"{n['category']} 고민이라면 — {n.get('full_name') or n['name']}",
        lambda n: f"{n.get('full_name') or n['name']}, 이 가격에 괜찮은 이유",
        lambda n: f"써보고 나서 알게 된 {n.get('full_name') or n['name']} 이야기",
    ]

    product_sections = []
    for i, note in enumerate(notes[:5]):
        full_name = note.get("full_name") or note.get("name") or note.get("category") or "상품"
        cat       = note.get("category") or ""
        strengths = note.get("strengths") or []
        fit       = note.get("fit_for") or ""
        price     = note.get("price_merit") or ""

        h2 = h2_starters[i % len(h2_starters)](note)
        lines = [f"## {h2}\n"]

        josa_n = _josa(full_name, "은/는")
        lines.append(f"{full_name}{josa_n} {cat} 중에서 문의가 꾸준히 이어지는 모델이에요.")

        if strengths:
            lines.append(strengths[0] + "는 점이 인상적이었어요." if strengths[0][-1] in "다요" else strengths[0])
        if len(strengths) > 1:
            lines.append(f"그리고 {strengths[1]}라는 점도 다른 모델과 비교했을 때 차이가 느껴지는 부분이에요.")
        if fit:
            lines.append(f"\n{fit}")
        if price:
            lines.append(f"\n가격은 {price}.")

        product_sections.append("\n".join(lines))

    closing = (
        "행사 가격과 혜택 조건은 재고 상황이나 기간에 따라 달라질 수 있어요. "
        "정확한 조건과 설치·배송 포함 여부는 구매 전에 꼭 한 번 확인해 보시는 걸 권장드려요."
    )

    body_parts = [intro_para] + product_sections + [closing]
    body = "\n\n".join(p for p in body_parts if p)

    return {
        "titles": [
            f"{store} {event} | {name_list} 가격·특징 정리",
            f"가전 살 때 이것만 알면 돼요 — {store} 추천",
            f"{name_list} 직접 확인해봤습니다",
        ],
        "body": body,
        "cta":  cta,
    }


def _fallback_campaign_info(
    products: list[dict[str, Any]], *, store_name: str = "",
    max_event_len: int = 18, max_campaign_len: int = 24
) -> dict[str, str]:
    first    = products[0] if products else {}
    cat      = _category_label(first.get("category", ""))
    count    = len(products)
    if count == 0:
        event = "온라인 특가상품전"
        campaign = f"{store_name or '매장'} 가성비 특가홍보"
    elif count > 1:
        event = f"{cat} 특가상품전"
        campaign = f"{store_name or '매장'} 온라인 가성비 {cat}"
    else:
        short = _heuristic_short_name(first.get("product_name", ""), category=first.get("category", ""), limit=13)
        event = f"{short} 특가모델"
        campaign = f"{store_name or '매장'} 온라인 {short}"
    return {
        "event_title":   event[:max_event_len].strip(),
        "campaign_name": campaign[:max_campaign_len].strip(),
    }


def _fallback_landing_copy(
    products: list[dict[str, Any]], *, store_name: str = "", event_title: str = ""
) -> dict[str, str]:
    return {
        "landing_title": "온라인 가성비 특가상품 기획전",
        "intro_text": (
            f"{store_name or '매장'}에서 준비한 온라인 특가상품을 한 번에 확인해 보세요. "
            "행사상품과 혜택은 변동될 수 있으니 전화 또는 카카오톡으로 편하게 문의해 주세요."
        ),
    }


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def generate_instagram_copy_v2(payload: dict[str, Any]) -> dict[str, Any]:
    # 상품 페이지 실제 정보 보강
    if payload.get("products"):
        payload = {**payload, "products": enrich_products_from_pages(payload["products"])}
    prepared = _prepare_instagram_payload(payload)
    try:
        model   = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
        raw     = _call_claude(build_instagram_messages(prepared), model=model, max_tokens=1500)
        result  = _parse_json(raw)
        hooks       = [str(x).strip() for x in (result.get("hooks") or []) if str(x).strip()][:2]
        caption     = str(result.get("caption") or "").strip()
        story_lines = [str(x).strip() for x in (result.get("story_lines") or []) if str(x).strip()][:3]
        hashtags    = [str(x).strip() for x in (result.get("hashtags") or []) if str(x).strip()][:15]
        dm_reply    = str(result.get("dm_reply") or "").strip()
        if not hooks or not caption:
            return _fallback_instagram(prepared)
        return {"hooks": hooks, "caption": caption, "story_lines": story_lines,
                "hashtags": hashtags, "dm_reply": dm_reply}
    except Exception:
        return _fallback_instagram(prepared)


def generate_instagram_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return generate_instagram_copy_v2(payload)


def generate_blog_copy_v2(payload: dict[str, Any]) -> dict[str, Any]:
    # 상품 페이지 실제 정보 보강
    if payload.get("products"):
        payload = {**payload, "products": enrich_products_from_pages(payload["products"])}
    prepared = _prepare_blog_payload(payload)
    try:
        model  = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
        raw    = _call_claude(build_blog_messages(prepared), model=model, max_tokens=3500)
        result = _parse_json(raw)
        titles = [str(x).strip() for x in (result.get("titles") or []) if str(x).strip()][:3]
        body   = str(result.get("body") or "").strip()
        cta    = str(result.get("cta") or "").strip()
        if not titles or not body:
            return _fallback_blog(prepared)
        return {"titles": titles, "body": body, "cta": cta}
    except Exception:
        return _fallback_blog(prepared)


def generate_blog_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return generate_blog_copy_v2(payload)


def recommend_campaign_info(
    products: list[dict[str, Any]], *, store_name: str = "",
    max_event_len: int = 18, max_campaign_len: int = 24,
) -> dict[str, str]:
    fallback = _fallback_campaign_info(
        products, store_name=store_name,
        max_event_len=max_event_len, max_campaign_len=max_campaign_len,
    )
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or _anthropic is None:
        return fallback

    model = os.getenv("ANTHROPIC_FAST_MODEL", _FAST_MODEL).strip() or _FAST_MODEL
    product_lines = [
        f"- {_heuristic_short_name(p.get('product_name',''), category=p.get('category',''), limit=13)}"
        for p in products[:6]
    ]
    try:
        client = _get_client()
        response = client.messages.create(
            model=model, max_tokens=200,
            system="하이마트 매장 홍보 문구 도우미. 짧고 실무적인 행사명·캠페인명 추천. JSON만 반환.",
            messages=[{"role": "user", "content": (
                f"매장: {store_name or '하이마트'}\n"
                f"상품: {chr(10).join(product_lines)}\n\n"
                f"event_title {max_event_len}자 이내, campaign_name {max_campaign_len}자 이내.\n"
                '{"event_title":"...","campaign_name":"..."}'
            )}],
        )
        result = _parse_json(response.content[0].text)
        et = str(result.get("event_title") or "").strip()[:max_event_len]
        cn = str(result.get("campaign_name") or "").strip()[:max_campaign_len]
        return {"event_title": et, "campaign_name": cn} if et and cn else fallback
    except Exception:
        return fallback


def recommend_landing_copy(
    products: list[dict[str, Any]], *, store_name: str = "", event_title: str = ""
) -> dict[str, str]:
    fallback = _fallback_landing_copy(products, store_name=store_name, event_title=event_title)
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or _anthropic is None:
        return fallback

    model = os.getenv("ANTHROPIC_FAST_MODEL", _FAST_MODEL).strip() or _FAST_MODEL
    product_lines = [
        f"- {_heuristic_short_name(p.get('product_name',''), category=p.get('category',''), limit=13)}"
        for p in products[:5]
    ]
    try:
        client = _get_client()
        response = client.messages.create(
            model=model, max_tokens=200,
            system="하이마트 랜딩페이지 문구 도우미. 짧고 실무적으로 작성. JSON만 반환.",
            messages=[{"role": "user", "content": (
                f"매장: {store_name or '하이마트'}\n"
                f"행사명: {event_title or '매장 특가 행사'}\n"
                f"상품: {chr(10).join(product_lines)}\n\n"
                "landing_title 22자 이내, intro_text 2문장 이내.\n"
                '{"landing_title":"...","intro_text":"..."}'
            )}],
        )
        result = _parse_json(response.content[0].text)
        lt = str(result.get("landing_title") or "").strip()[:22]
        it = str(result.get("intro_text") or "").strip()
        return {"landing_title": lt, "intro_text": it} if lt and it else fallback
    except Exception:
        return fallback


def generate_instagram_prompt(payload: dict[str, Any]) -> str:
    """인스타그램 게시글 작성용 프롬프트 생성 — AI 호출 없음. 사용자가 ChatGPT/Gemini에 복사해서 사용.
    e-himart 상품 페이지 실제 데이터를 스크래핑해서 프롬프트에 반영."""
    # 상품 페이지 실제 데이터 보강
    raw_products = payload.get("products") or []
    try:
        products = enrich_products_from_pages(raw_products) if raw_products else []
    except Exception:
        products = raw_products

    store = payload.get("store_name") or "하이마트"
    event = payload.get("event_title") or "이번 주 특가 행사"
    phone = payload.get("phone") or ""
    kakao = payload.get("kakao_channel_url") or ""

    lines = [
        "아래 정보를 참고해서 하이마트 매장 인스타그램 홍보 게시물을 작성해줘.",
        "",
        "【핵심 작성 원칙】",
        "- 도입부: '광고 같지 않은' 느낌으로 공감 또는 현장 묘사로 시작. 절대 제품명/브랜드로 시작하지 말 것",
        "  예) '이번에 바꿨는데 진짜 잘 바꿨다 싶었어요' / '집에서 보내는 시간이 달라지면 기분도 달라지더라고요'",
        "- 본문: 스펙 나열 금지. 고객이 실제 생활에서 느낄 변화와 경험으로 풀어쓸 것",
        "  나쁜 예) '1600rpm 고속탈수, 에너지 A등급'",
        "  좋은 예) '세탁 끝나고 꺼냈을 때 옷에서 나던 퀴퀴한 냄새가 없어요. 진짜로요.'",
        "- 상품이 여러 개면 번호 매기지 말고 한 흐름으로 자연스럽게 묶을 것",
        "- 광고성 과장 표현 금지: '최고!', '무조건', '지금 안 사면 손해' 등",
        "- 마무리: 방문·문의 유도 CTA를 판매 냄새 없이 자연스럽게",
        "  예) '하이마트에 오시면 직접 만져보실 수 있어요 :)'",
        "- 전체 본문: 15줄 이내",
        "",
        "【이모지 활용 규칙 — 눈에 잘 보이도록】",
        "- 각 문장/줄 앞에 어울리는 이모지를 붙여서 시각적으로 읽기 쉽게 구성",
        "  예시 포맷:",
        "  ✨ 도입 공감 문장",
        "  🏠 생활 경험 서술",
        "  ❄️ 냉장고 관련 내용",
        "  🧺 세탁기 관련 내용",
        "  📺 TV 관련 내용",
        "  💨 에어컨 관련 내용",
        "  🍳 주방가전 관련 내용",
        "  💡 혜택/가격 포인트",
        "  🛍️ 행사/쇼핑 안내",
        "  📍 매장 위치/방문 안내",
        "  💬 문의/CTA",
        "- 같은 이모지 반복 사용 금지, 내용에 맞는 이모지 선택",
        "- 해시태그 줄은 이모지 없이",
        "",
        "【매장 정보】",
        f"- 매장명: {store}",
        f"- 행사명: {event}",
    ]
    if phone:
        lines.append(f"- 전화 문의: {phone}")
    if kakao:
        lines.append(f"- 카카오채널: {kakao}")

    lines += ["", "【상품별 실제 정보 (e-himart 페이지 데이터 포함)】"]
    bad_tags = ["dryer cap", "washer cap", "fridge size", "fridge type",
                "size group", "tv type", "aircon type", "kimchi_size", "kimchi_type"]
    for i, p in enumerate(products[:5], 1):
        name  = _heuristic_short_name(
            p.get("product_name", "") or p.get("productName", ""),
            category=p.get("category", ""), limit=22,
        )
        price = _best_price_value(p)
        price_text = f"{int(round(price / 10000))}만원대" if price > 0 else "가격 문의"
        cat   = _category_label(p.get("category", ""))
        brand = (p.get("brand") or "").strip()
        reason = (p.get("recommendationReason") or p.get("reason") or "").strip()

        # featureBullets: DB 데이터 + 페이지 feature_sentences 합산
        bullets = [str(b).strip() for b in (p.get("featureBullets") or [])
                   if str(b).strip() and "?" not in str(b)
                   and not any(t in str(b).lower() for t in bad_tags)][:3]

        # 페이지 설명 (productDescription)
        page_desc = (p.get("productDescription") or "").strip()[:120]

        # 리뷰 정보
        review_count = int(p.get("review_count") or 0)
        page_rating  = float(p.get("pageRating") or 0)

        header = f"{i}. {name}"
        if brand:
            header += f" ({brand})"
        header += f" — {cat} | 혜택가 {price_text}"
        lines.append(header)

        if reason:
            lines.append(f"   ✅ 추천 이유: {reason}")
        if page_desc:
            lines.append(f"   📝 상품 설명 (페이지 원문): {page_desc}")
        for b in bullets:
            lines.append(f"   · {b}")
        if review_count > 0 and page_rating > 0:
            lines.append(f"   ⭐ 리뷰 {review_count}건, 평점 {page_rating:.1f}/5")
        elif review_count > 0:
            lines.append(f"   ⭐ 고객 리뷰 {review_count}건")

    lines += [
        "",
        "【출력 형식】 (아래 구분선 그대로 사용)",
        "=== 게시글 본문 ===",
        "(공감 도입 → 상품 경험 서술 → 자연스러운 CTA, 15줄 이내)",
        "",
        "=== 해시태그 ===",
        "(15개 내외: 브랜드·품목·지역·감성 태그 혼합. 필수 포함: #하이마트광복점 #부산가전)",
        "",
        "=== DM 답변 템플릿 ===",
        "(문의 DM에 바로 사용할 짧고 친근한 답변 문구 1개)",
    ]
    return "\n".join(lines)


def generate_blog_prompt(payload: dict[str, Any]) -> str:
    """블로그 글 작성용 프롬프트 생성 — AI 호출 없음. 사용자가 ChatGPT/Gemini에 복사해서 사용.
    e-himart 상품 페이지 실제 데이터를 스크래핑해서 프롬프트에 반영."""
    # 상품 페이지 실제 데이터 보강
    raw_products = payload.get("products") or []
    try:
        products = enrich_products_from_pages(raw_products) if raw_products else []
    except Exception:
        products = raw_products

    store    = payload.get("store_name") or "하이마트"
    event    = payload.get("event_title") or "이번 주 특가 행사"
    phone    = payload.get("phone") or ""
    kakao    = payload.get("kakao_channel_url") or ""

    lines = [
        "아래 정보를 참고해서 네이버 블로그용 홍보 글을 작성해줘.",
        "",
        "【핵심 작성 원칙】",
        "- 톤: '전문성 있고 신뢰감 있는 사람이 직접 경험하고 쓴 글' 느낌. 친한 친구 ❌ → 믿을 수 있는 전문가 추천 ✅",
        "- 도입부: 공감 또는 현장 묘사로 시작. 절대 제품명/브랜드로 시작하지 말 것",
        "  예) '프리미엄 세탁기를 고민하다 보면 결국 이 브랜드 얘기가 나옵니다.'",
        "- AI 번역체 금지: '~할 수 있습니다', '다양한 기능을 제공합니다', '효율적인' 등 광고 형용사 사용 금지",
        "- 단점 포함 필수: 아쉬운 점 1개 이상 솔직하게 포함해서 신뢰도 높일 것",
        "  예) '이 부분은 아쉬웠는데요' / '가격이 좀 있는 건 사실이에요'",
        "- 스펙은 경험으로 번역: '1600rpm' → '세탁 후 옷이 훨씬 덜 눅눅하게 나왔어요'",
        "- 소제목: ## 사용, 키워드 자연 포함, 클릭 유도형으로",
        "  나쁜 예) '## 제품 특징'  좋은 예) '## 직접 써보니까 달랐던 점'",
        "- 전체 분량: 공백 포함 1800~2200자",
        "- 마무리: '이런 분께 추천한다' 형식으로 자연스럽게 마무리, 억지 CTA 없이",
        "",
        "【SEO 핵심 키워드 (자연스럽게 포함)】",
        "지역: 부산 가전제품, 광복 롯데몰, 부산 하이마트, 부산 신혼가전, 부산 인테리어 가전",
        "상황: 신혼 가전 추천, 이사 가전 세팅, 빌트인 설치, 가전 교체",
        "기능: 프리미엄 가전, 독일 가전, 유럽 가전, 고급 가전",
        "",
        "【매장 정보】",
        f"- 매장명: {store}",
        f"- 행사명: {event}",
    ]
    if phone:
        lines.append(f"- 전화 문의: {phone}")
    if kakao:
        lines.append(f"- 카카오채널: {kakao}")

    lines += ["", "【상품별 실제 정보 (e-himart 페이지 데이터 포함)】"]
    for i, p in enumerate(products[:5], 1):
        full_name  = (p.get("product_name") or p.get("productName") or "").strip()
        name       = _heuristic_short_name(full_name, category=p.get("category", ""), limit=22)
        price      = _best_price_value(p)
        price_text = f"{int(round(price / 10000))}만원대" if price > 0 else "가격 문의"
        original   = 0
        for k in ("original_price", "originalPrice", "price"):
            v = p.get(k)
            try:
                if v and int(float(v)) > 0:
                    original = int(float(v)); break
            except Exception:
                pass
        cat    = _category_label(p.get("category", ""))
        brand  = (p.get("brand") or "").strip()
        reason = (p.get("recommendationReason") or p.get("reason") or "").strip()
        bullets = _blog_feature_lines(p)

        # 페이지에서 가져온 추가 데이터
        page_desc    = (p.get("productDescription") or "").strip()[:200]
        review_count = int(p.get("review_count") or 0)
        page_rating  = float(p.get("pageRating") or 0)
        page_specs   = (p.get("pageSpecs") or [])[:3]
        page_keywords = (p.get("pageKeywords") or [])[:5]
        category_full = (p.get("categoryFull") or "").strip()

        header = f"{i}. {name}"
        if brand:
            header += f" ({brand})"
        header += f" — {cat}"
        if category_full:
            header += f" [{category_full}]"
        lines.append(header)
        if full_name and full_name != name:
            lines.append(f"   전체 상품명: {full_name[:70]}")
        lines.append(f"   혜택가: {price_text}")
        if original > price > 0:
            lines.append(f"   절약 혜택: 기존 {int(round(original / 10000))}만원대 → 약 {int(round((original - price) / 10000))}만원 절약")
        if reason:
            lines.append(f"   ✅ 추천 이유: {reason}")
        if page_desc:
            lines.append(f"   📝 상품 공식 설명 (페이지 원문): {page_desc}")
        for b in bullets:
            lines.append(f"   · {b}")
        if page_specs:
            spec_text = " / ".join(str(s.get("name", "")) + ":" + str(s.get("value", "")) for s in page_specs)
            lines.append(f"   📊 주요 스펙: {spec_text}")
        if review_count > 0 and page_rating > 0:
            lines.append(f"   ⭐ 고객 리뷰 {review_count}건, 평점 {page_rating:.1f}/5 — 인기 이유 글에서 자연스럽게 언급")
        elif review_count > 0:
            lines.append(f"   ⭐ 고객 리뷰 {review_count}건 — 인기도 언급 가능")
        if page_keywords:
            lines.append(f"   🔑 페이지 키워드: {', '.join(page_keywords)}")

    lines += [
        "",
        "【출력 형식】 (아래 구분선 그대로 사용)",
        "=== 제목 후보 ===",
        "1. (SEO 키워드 포함, 클릭하고 싶은 제목)",
        "2. (다른 각도의 제목)",
        "3. (감성 또는 정보형 제목)",
        "",
        "=== 본문 ===",
        "(도입부 → ## 소제목1 → ## 소제목2 → ## 소제목3 → 마무리, 1800~2200자)",
        "",
        "=== 상담 유도 문구 ===",
        "(글 마지막 또는 댓글용, 자연스럽게 방문/문의 유도 1~2문장)",
        "",
        "=== SEO 메모 ===",
        "- 핵심 키워드: (사용된 주요 키워드 나열)",
        "- 자연 삽입 횟수: (키워드별 등장 횟수)",
        "- 예상 독자 체류 시간: (읽기 시간 추정)",
    ]
    return "\n".join(lines)


def generate_short_product_name(product_name: str, *, category: str = "", limit: int = 13) -> str:
    """순수 휴리스틱 기반 상품명 축약 (AI 호출 없음)."""
    result = _heuristic_short_name(product_name, category=category, limit=limit)
    return _ensure_brand_first(result, product_name, limit)


def generate_creative_title(product_name: str, *, category: str = "", limit: int = 15) -> str:
    """시안용 제목 (generate_short_product_name 의 alias)."""
    return generate_short_product_name(product_name, category=category, limit=limit)
