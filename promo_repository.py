"""Persistence and query helpers for the promo workflow."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from config import STORE_NAME
from database import get_conn


DEFAULT_DISCLAIMER = (
    "행사 및 가격 정보는 생성 시점 기준이며 변동될 수 있습니다.\n"
    "카드 혜택 및 구독 조건은 적용 기준에 따라 달라질 수 있습니다.\n"
    "자세한 내용은 매장 문의를 통해 확인해 주세요."
)


def init_promo_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS store_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_code TEXT UNIQUE,
                store_name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                kakao_channel_url TEXT DEFAULT '',
                address TEXT DEFAULT '',
                location_url TEXT DEFAULT '',
                staff_code TEXT DEFAULT '',
                staff_name TEXT DEFAULT '',
                is_default INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                campaign_name TEXT NOT NULL,
                event_title TEXT NOT NULL,
                store_code TEXT DEFAULT '',
                store_name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                kakao_channel_url TEXT DEFAULT '',
                address TEXT DEFAULT '',
                location_url TEXT DEFAULT '',
                staff_code TEXT DEFAULT '',
                staff_name TEXT DEFAULT '',
                selected_product_ids TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS generated_creatives (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tracked_links (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                short_url TEXT DEFAULT '',
                qr_image_url TEXT DEFAULT '',
                visit_count INTEGER DEFAULT 0,
                call_click_count INTEGER DEFAULT 0,
                kakao_click_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS image_assets (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                original_url TEXT NOT NULL,
                processed_url TEXT DEFAULT '',
                transparent_png_url TEXT DEFAULT '',
                background_removed INTEGER DEFAULT 0,
                bg_removal_provider TEXT DEFAULT 'noop',
                metadata TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS campaign_events (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                link_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON campaigns(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_generated_creatives_campaign ON generated_creatives(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_tracked_links_campaign ON tracked_links(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_image_assets_product ON image_assets(product_id, original_url);
            CREATE INDEX IF NOT EXISTS idx_campaign_events_campaign ON campaign_events(campaign_id, event_type);
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM store_info").fetchone()[0]
        if count == 0:
            conn.execute(
                """
                INSERT INTO store_info (
                    store_code, store_name, phone, kakao_channel_url, address, location_url,
                    staff_code, staff_name, is_default
                ) VALUES (?, ?, '', '', '', '', '', '', 1)
                """,
                ("default", STORE_NAME),
            )


def get_default_store_info() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM store_info ORDER BY is_default DESC, id ASC LIMIT 1"
        ).fetchone()
    if not row:
        return {
            "store_code": "default",
            "store_name": STORE_NAME,
            "phone": "",
            "kakao_channel_url": "",
            "address": "",
            "location_url": "",
            "staff_code": "",
            "staff_name": "",
        }
    return dict(row)


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value in (None, "", b""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


SPEC_KEY_LABELS = {
    "kimchi_size": "김치냉장고 크기",
    "kimchi_type": "김치냉장고 형태",
    "door_type": "도어 형태",
    "capacity": "용량",
    "washer_type": "세탁 방식",
    "dryer_type": "건조 방식",
    "installation_type": "설치 방식",
    "color": "색상",
    "panel": "패널",
    "size": "크기",
}


SPEC_VALUE_LABELS = {
    "small": "소형",
    "medium": "중형",
    "large": "대형",
    "top": "뚜껑형",
    "stand": "스탠드형",
    "stand-type": "스탠드형",
    "drum": "드럼형",
    "top-load": "통돌이형",
    "front-load": "드럼형",
    "integrated": "일체형",
    "builtin": "빌트인형",
    "white": "화이트",
    "black": "블랙",
    "silver": "실버",
}


def _prettify_spec_token(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if lowered in SPEC_KEY_LABELS:
        return SPEC_KEY_LABELS[lowered]
    if lowered in SPEC_VALUE_LABELS:
        return SPEC_VALUE_LABELS[lowered]
    return text.replace("_", " ")


def _naturalize_raw_tag(value: Any, category: str = "") -> str:
    text = _clean_text(value)
    if not text:
        return ""

    lowered = text.lower()

    rules: list[tuple[str, str]] = [
        (r"^size group\s*50s$", "50형대 TV를 찾는 고객이 보기 좋은 크기대입니다."),
        (r"^size group\s*60s$", "60형대 이상 큰 화면을 찾는 고객에게 잘 맞는 크기대입니다."),
        (r"^size group\s*70s$", "70형대 이상 대화면을 선호하는 고객이 눈여겨볼 만합니다."),
        (r"^tv type\s*led$", "기본기에 충실한 LED TV로 부담 없이 비교해 보기 좋습니다."),
        (r"^tv type\s*oled$", "명암 표현과 화질 만족도를 중요하게 보는 고객이 선호하는 OLED TV입니다."),
        (r"^tv type\s*qled$", "밝은 화면감과 선명한 색 표현을 기대하는 고객이 많이 찾는 QLED TV입니다."),
        (r"^tv type\s*qned$", "화질과 화면 밸런스를 함께 보는 고객이 비교해 보기 좋은 QNED TV입니다."),
        (r"^washer cap\s*12s$", "12kg대 용량으로 1~2인 가구나 서브 세탁기로 보기 좋습니다."),
        (r"^washer cap\s*15s$", "15kg대 용량으로 일상 세탁량이 많은 집에서 무난하게 쓰기 좋습니다."),
        (r"^washer cap\s*20s$", "대용량 세탁을 자주 하는 가정에서 여유 있게 보기 좋은 급입니다."),
        (r"^kimchi size\s*small$", "소형 김치냉장고를 찾거나 세컨드 보관용으로 보기 좋습니다."),
        (r"^kimchi size\s*medium$", "가정용으로 무난하게 쓰기 좋은 중형급 김치냉장고입니다."),
        (r"^kimchi size\s*large$", "보관량이 많은 집에서 넉넉하게 쓰기 좋은 대형급입니다."),
        (r"^kimchi type\s*top$", "뚜껑형 구조라 자주 꺼내 쓰는 반찬이나 김치 보관에 편합니다."),
        (r"^kimchi type\s*stand$", "스탠드형 구조라 수납 구분과 정리를 중요하게 보는 고객이 선호합니다."),
        (r"^door type\s*4door$", "4도어 구성이라 식재료를 나눠 보관하기 편한 편입니다."),
        (r"^door type\s*side by side$", "양문형 스타일이라 자주 쓰는 식재료를 넓게 정리하기 좋습니다."),
    ]

    for pattern, replacement in rules:
        if re.search(pattern, lowered):
            return replacement

    if lowered in {"premium", "value", "wedding", "move-in", "popular", "event"}:
        label_map = {
            "premium": "프리미엄 라인을 찾는 고객이 많이 보는 모델입니다.",
            "value": "가성비 중심으로 비교하는 고객이 눈여겨볼 만합니다.",
            "wedding": "신혼이나 혼수 가전으로 많이 비교하는 편입니다.",
            "move-in": "입주 가전으로 한 번에 맞춰보는 고객 문의가 잘 붙는 편입니다.",
            "popular": "매장에서 비교 문의가 꾸준히 들어오는 인기 모델군입니다.",
            "event": "행사 타이밍에 맞춰 혜택을 함께 보기 좋은 모델입니다.",
        }
        return label_map[lowered]

    prettified = _prettify_spec_token(text)
    if prettified != text:
        return prettified

    if category == "tv" and "led" in lowered:
        return "기본기 좋은 TV로 편하게 보기 좋은 모델입니다."
    if category == "washer" and "cap" in lowered:
        return "용량대 기준으로 가구 규모에 맞춰 비교해 보기 좋습니다."
    if category == "kimchi" and "type" in lowered:
        return "보관 방식에 따라 편의성을 비교해 보기 좋습니다."

    return text


def _extract_name_specs(product_name: str) -> list[str]:
    text = _clean_text(product_name)
    specs: list[str] = []
    liters = re.search(r"(\d{2,4})\s*L", text, re.I)
    kg = re.search(r"(\d{1,2}(?:\.\d)?)\s*KG", text, re.I)
    inch = re.search(r"(\d{2,3})\s*(?:인치|\")", text, re.I)
    if liters:
        specs.append(f"{liters.group(1)}L")
    if kg:
        specs.append(f"{kg.group(1)}KG")
    if inch:
        specs.append(f"{inch.group(1)}인치")

    keywords = [
        "OLED",
        "QLED",
        "QNED",
        "LED",
        "4도어",
        "양문형",
        "뚜껑형",
        "스탠드형",
        "드럼",
        "통돌이",
        "일체형",
        "히트펌프",
        "2in1",
    ]
    upper = text.upper()
    for keyword in keywords:
        if keyword.upper() in upper and keyword not in specs:
            specs.append(keyword)
    return specs[:4]


def _derive_feature_bullets(item: dict[str, Any], selection: dict[str, Any]) -> list[str]:
    bullets: list[str] = []
    category = _clean_text(item.get("category") or selection.get("category"))
    spec_data = _safe_json_loads(item.get("spec"), {})
    if isinstance(spec_data, dict):
        for key, value in spec_data.items():
            label = _prettify_spec_token(key)
            text = _naturalize_raw_tag(value, category=category)
            if not text:
                continue
            if label and label not in text:
                bullets.append(f"{label} {text}")
            else:
                bullets.append(text)
    goods_attrs = _safe_json_loads(item.get("goods_attrs"), [])
    if isinstance(goods_attrs, list):
        for value in goods_attrs:
            text = _naturalize_raw_tag(value, category=category)
            if text:
                bullets.append(text)

    for key in ("feature_bullets", "featureBullets", "product_description", "productDescription", "recommendationReason", "reason"):
        value = selection.get(key) or item.get(key)
        if isinstance(value, list):
            for bullet in value:
                text = _naturalize_raw_tag(bullet, category=category)
                if text:
                    bullets.append(text)
        else:
            text = _naturalize_raw_tag(value, category=category)
            if text:
                bullets.append(text)

    for spec in _extract_name_specs(item.get("product_name", "")):
        bullets.append(spec)

    unique: list[str] = []
    seen: set[str] = set()
    for bullet in bullets:
        normalized = bullet.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
        if len(unique) >= 6:
            break
    return unique


def _derive_tags(item: dict[str, Any], selection: dict[str, Any]) -> list[str]:
    source = " ".join(
        [
            _clean_text(item.get("product_name")),
            _clean_text(selection.get("reason")),
            _clean_text(selection.get("recommendationReason")),
            _clean_text(item.get("category")),
        ]
    ).lower()
    mapping = [
        ("premium", ["oled", "qned", "qled", "premium", "프리미엄"]),
        ("value", ["가성비", "혜택", "특가", "할인", "value"]),
        ("wedding", ["혼수", "신혼", "wedding"]),
        ("move-in", ["입주", "이사", "move"]),
        ("popular", ["인기", "베스트", "review", "리뷰"]),
        ("event", ["행사", "이벤트", "특가", "프로모션"]),
    ]
    tags: list[str] = []
    for tag, keywords in mapping:
        if any(keyword in source for keyword in keywords):
            tags.append(tag)
    if not tags and item.get("review_count"):
        tags.append("popular")
    return tags[:4]


def _derive_product_description(item: dict[str, Any], feature_bullets: list[str], selection: dict[str, Any]) -> str:
    recommendation = _clean_text(selection.get("recommendationReason") or selection.get("reason") or item.get("recommendationReason"))
    if recommendation and not re.search(r"최저가|특가|할인|혜택|행사", recommendation):
        return recommendation
    category = {
        "refrigerator": "수납력과 사용 편의성을 함께 보기 좋은 냉장고 모델입니다.",
        "kimchi": "계절 식재료와 김치 보관을 함께 고려하기 좋은 김치냉장고입니다.",
        "washer": "세탁 용량과 설치 환경을 함께 비교해 보기 좋은 세탁기입니다.",
        "dryer": "건조 성능과 편의 기능을 함께 체크하기 좋은 건조기입니다.",
        "tv": "화면 크기와 화질 체감을 함께 보기 좋은 TV 모델입니다.",
        "aircon": "공간 구성과 냉방 방식에 따라 비교하기 좋은 에어컨입니다.",
    }.get(item.get("category", ""), "매장에서 많이 비교해 보는 인기 생활가전 모델입니다.")
    if feature_bullets:
        return f"{feature_bullets[0]} 포인트가 눈에 띄는 상품으로, {category}"
    return category


def _enrich_product_context(item: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    feature_bullets = _derive_feature_bullets(item, selection)
    recommendation_reason = _clean_text(selection.get("recommendationReason") or selection.get("reason") or item.get("recommendationReason"))
    description = _derive_product_description(item, feature_bullets, selection)
    tags = _derive_tags(item, selection)
    card_benefit_text = _clean_text(
        selection.get("cardBenefitText")
        or item.get("card_benefit_text")
        or item.get("benefit_desc")
        or item.get("care_benefit")
    )
    return {
        **item,
        "productName": item.get("product_name", ""),
        "modelName": item.get("model_no", ""),
        "price": item.get("sale_price") or item.get("price") or item.get("monthly_fee") or 0,
        "benefitPrice": item.get("benefit_price") or item.get("sale_price") or item.get("price") or 0,
        "subscriptionPrice": item.get("monthly_fee") or 0,
        "cardBenefitText": card_benefit_text,
        "recommendationReason": recommendation_reason,
        "featureBullets": feature_bullets,
        "productDescription": description,
        "tags": tags,
        "specData": _safe_json_loads(item.get("spec"), {}),
    }


def resolve_selected_products(selections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    with get_conn() as conn:
        for selection in selections:
            model_no = (selection.get("model_no") or "").strip()
            if not model_no:
                continue
            if selection.get("_isSubscription"):
                row = conn.execute(
                    "SELECT * FROM subscription_products WHERE model_no = ? LIMIT 1",
                    (model_no,),
                ).fetchone()
                if row:
                    item = {**dict(row), **selection}
                    item["_isSubscription"] = True
                    item["product_id"] = item.get("model_no") or str(item.get("id"))
                    resolved.append(_enrich_product_context(item, selection))
                continue

            row = conn.execute(
                """
                WITH latest AS (
                    SELECT ph.*,
                           ROW_NUMBER() OVER (PARTITION BY ph.model_no ORDER BY ph.crawled_at DESC) AS rn
                    FROM price_history ph
                )
                SELECT p.model_no, p.product_name, p.category, p.product_url, p.image_url, p.spec, p.review_count,
                       l.original_price, l.sale_price, l.benefit_price, l.crawled_at
                FROM products p
                JOIN latest l ON l.model_no = p.model_no AND l.rn = 1
                WHERE p.model_no = ?
                LIMIT 1
                """,
                (model_no,),
            ).fetchone()
            if row:
                item = {**dict(row), **selection}
                item["_isSubscription"] = False
                item["product_id"] = item.get("model_no")
                resolved.append(_enrich_product_context(item, selection))
    return resolved


def normalize_promo_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for product in products or []:
      item = dict(product)
      item.setdefault("product_name", item.get("productName", ""))
      item.setdefault("model_no", item.get("modelName", ""))
      item.setdefault("benefit_price", item.get("benefitPrice", item.get("benefit_price")))
      item.setdefault("sale_price", item.get("salePrice", item.get("sale_price", item.get("price"))))
      item.setdefault("original_price", item.get("originalPrice", item.get("original_price", item.get("price"))))
      item.setdefault("card_benefit_text", item.get("cardBenefitText", item.get("card_benefit_text", "")))
      normalized.append(_enrich_product_context(item, item))
    return normalized


def create_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    campaign_id = payload.get("id") or uuid.uuid4().hex[:12]
    metadata = payload.get("metadata") or {}
    selected_product_ids = payload.get("selected_product_ids") or []
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO campaigns (
                id, campaign_name, event_title, store_code, store_name, phone, kakao_channel_url,
                address, location_url, staff_code, staff_name, selected_product_ids, metadata,
                expires_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                campaign_id,
                payload.get("campaign_name", ""),
                payload.get("event_title", ""),
                payload.get("store_code", ""),
                payload.get("store_name", STORE_NAME),
                payload.get("phone", ""),
                payload.get("kakao_channel_url", ""),
                payload.get("address", ""),
                payload.get("location_url", ""),
                payload.get("staff_code", ""),
                payload.get("staff_name", ""),
                json.dumps(selected_product_ids, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                expires_at,
            ),
        )
    return get_campaign(campaign_id)


def update_campaign(campaign_id: str, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "campaign_name",
        "event_title",
        "store_code",
        "store_name",
        "phone",
        "kakao_channel_url",
        "address",
        "location_url",
        "staff_code",
        "staff_name",
        "selected_product_ids",
        "metadata",
    }
    sets = []
    values = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {"selected_product_ids", "metadata"}:
            value = json.dumps(value, ensure_ascii=False)
        sets.append(f"{key} = ?")
        values.append(value)
    if not sets:
        return get_campaign(campaign_id)
    values.append(campaign_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE campaigns SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
    return get_campaign(campaign_id)


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["selected_product_ids"] = json.loads(data.get("selected_product_ids") or "[]")
    data["metadata"] = json.loads(data.get("metadata") or "{}")
    data["products"] = resolve_selected_products(data["selected_product_ids"])
    data["assets"] = list_generated_assets(campaign_id)
    data["links"] = list_tracked_links(campaign_id)
    data["summary"] = get_campaign_metrics(campaign_id)
    return data


def list_campaigns() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM campaigns ORDER BY datetime(created_at) DESC"
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["selected_product_ids"] = json.loads(item.get("selected_product_ids") or "[]")
        item["metadata"] = json.loads(item.get("metadata") or "{}")
        item["summary"] = get_campaign_metrics(item["id"])
        results.append(item)
    return results


def delete_campaign(campaign_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM generated_creatives WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM tracked_links WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaign_events WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))


def save_generated_asset(campaign_id: str, asset_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    asset_id = uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO generated_creatives (id, campaign_id, type, payload)
            VALUES (?, ?, ?, ?)
            """,
            (asset_id, campaign_id, asset_type, json.dumps(payload, ensure_ascii=False)),
        )
    return {"id": asset_id, "campaign_id": campaign_id, "type": asset_type, "payload": payload}


def list_generated_assets(campaign_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM generated_creatives WHERE campaign_id = ? ORDER BY datetime(created_at) DESC",
            (campaign_id,),
        ).fetchall()
    results = [dict(row) for row in rows]
    for item in results:
        item["payload"] = json.loads(item.get("payload") or "{}")
    return results


def save_tracked_link(campaign_id: str, source: str, url: str, short_url: str, qr_image_url: str = "") -> dict[str, Any]:
    link_id = uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tracked_links (id, campaign_id, source, url, short_url, qr_image_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (link_id, campaign_id, source, url, short_url, qr_image_url),
        )
    return get_tracked_link(link_id) or {}


def update_tracked_link(link_id: str, *, url: str, short_url: str, qr_image_url: str = "") -> dict[str, Any] | None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tracked_links
            SET url = ?, short_url = ?, qr_image_url = ?
            WHERE id = ?
            """,
            (url, short_url, qr_image_url, link_id),
        )
    return get_tracked_link(link_id)


def list_tracked_links(campaign_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tracked_links WHERE campaign_id = ? ORDER BY datetime(created_at) DESC",
            (campaign_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_tracked_link(link_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tracked_links WHERE id = ?", (link_id,)).fetchone()
    return dict(row) if row else None


def record_campaign_event(campaign_id: str, event_type: str, metadata: dict[str, Any] | None = None, link_id: str = "") -> dict[str, Any]:
    event_id = uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO campaign_events (id, campaign_id, link_id, event_type, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, campaign_id, link_id, event_type, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        if link_id:
            column = {
                "landing_visit": "visit_count",
                "call_click": "call_click_count",
                "kakao_click": "kakao_click_count",
            }.get(event_type)
            if column:
                conn.execute(
                    f"UPDATE tracked_links SET {column} = {column} + 1 WHERE id = ?",
                    (link_id,),
                )
    return {"id": event_id, "campaign_id": campaign_id, "event_type": event_type, "metadata": metadata or {}}


def get_campaign_metrics(campaign_id: str) -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM campaign_events
            WHERE campaign_id = ?
            GROUP BY event_type
            """,
            (campaign_id,),
        ).fetchall()
    mapping = {row["event_type"]: row["count"] for row in rows}
    return {
        "landing_visit_count": mapping.get("landing_visit", 0),
        "call_click_count": mapping.get("call_click", 0),
        "kakao_click_count": mapping.get("kakao_click", 0),
    }


def get_cached_image_asset(product_id: str, original_url: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM image_assets WHERE product_id = ? AND original_url = ? LIMIT 1",
            (product_id, original_url),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["metadata"] = json.loads(item.get("metadata") or "{}")
    return item


def save_image_asset(
    product_id: str,
    original_url: str,
    processed_url: str,
    transparent_png_url: str,
    background_removed: bool,
    provider: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cached = get_cached_image_asset(product_id, original_url)
    asset_id = cached["id"] if cached else uuid.uuid4().hex[:16]
    with get_conn() as conn:
        if cached:
            conn.execute(
                """
                UPDATE image_assets
                SET processed_url = ?, transparent_png_url = ?, background_removed = ?,
                    bg_removal_provider = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    processed_url,
                    transparent_png_url,
                    int(background_removed),
                    provider,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    asset_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO image_assets (
                    id, product_id, original_url, processed_url, transparent_png_url,
                    background_removed, bg_removal_provider, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    product_id,
                    original_url,
                    processed_url,
                    transparent_png_url,
                    int(background_removed),
                    provider,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
    return get_cached_image_asset(product_id, original_url) or {}


def build_landing_payload(payload: dict[str, Any], campaign: dict[str, Any]) -> dict[str, Any]:
    return {
        "landing_title": payload.get("landing_title") or "온라인 가성비 특가상품 기획전",
        "intro_text": payload.get("intro_text") or "추천 상품을 한 번에 확인하고 매장으로 문의해 보세요.",
        "cta_visibility": payload.get("cta_visibility") or {"phone": True, "kakao": True},
        "product_order": payload.get("product_order") or [item.get("product_id") or item.get("model_no") for item in campaign.get("products", [])],
        "disclaimer": payload.get("disclaimer") or DEFAULT_DISCLAIMER,
    }
