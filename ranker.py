"""
HiMart Ranker — 카테고리별 TOP 5 추천 알고리즘
"""
import json
from config import (
    CATEGORIES, TOP_N,
    SCORE_DISCOUNT_MAX, SCORE_PRICE_DROP_MAX, SCORE_ALLTIME_LOW,
)
from database import get_latest_prices, get_alltime_low
from badge_calculator import get_enhanced_badges


def _discount_score(original: int, benefit: int) -> int:
    """할인율 점수 (최대 40점)"""
    if not original or not benefit or original <= 0:
        return 0
    rate = (original - benefit) / original * 100
    return min(int(rate), SCORE_DISCOUNT_MAX)


def _price_drop_score(benefit: int, prev_benefit: int | None) -> int:
    """어제 대비 가격 하락 점수 (최대 40점)"""
    if not benefit or not prev_benefit:
        return 0
    drop = prev_benefit - benefit
    if drop <= 0:
        return 0
    if drop >= 300_000:
        return 40
    if drop >= 200_000:
        return 30
    if drop >= 100_000:
        return 20
    if drop >= 50_000:
        return 10
    return 0


def _alltime_low_score(model_no: str, benefit: int) -> int:
    """역대 최저가 보너스 (20점)"""
    if not benefit:
        return 0
    low = get_alltime_low(model_no)
    return SCORE_ALLTIME_LOW if (low and benefit <= low) else 0


def _assign_badges(score: int, original: int, benefit: int, prev_benefit: int | None) -> list[str]:
    badges = []
    if score >= 80:
        badges.append("🔥 역대 최저가")
    elif score >= 60:
        badges.append("💰 최저가")

    if prev_benefit and prev_benefit > benefit:
        badges.append("📉 가격 인하")

    if original and benefit:
        rate = (original - benefit) / original * 100
        if rate >= 30:
            badges.append(f"⚡ {int(rate)}% 할인")
        elif rate >= 10:
            badges.append(f"🏷 {int(rate)}% 할인")

    return badges or ["✅ 추천"]


def rank_category(category_key: str, filters: dict | None = None) -> list[dict]:
    """카테고리 1개 랭킹 계산 → TOP_N 반환.
    filters: {'spec_key': 'value', ...} — spec JSON 값과 매칭 필터링
    """
    rows = get_latest_prices(category_key)

    # 서브 필터 적용 (spec JSON 파싱 후 매칭)
    if filters:
        filtered = []
        for r in rows:
            try:
                spec = json.loads(r.get("spec") or "{}")
            except Exception:
                spec = {}
            if all(spec.get(k) == v for k, v in filters.items()):
                filtered.append(r)
        rows = filtered

    scored = []

    for r in rows:
        original = r.get("original_price") or 0
        benefit = r.get("benefit_price") or r.get("sale_price") or 0
        prev = r.get("prev_benefit_price")

        if benefit == 0:
            continue

        s_discount = _discount_score(original, benefit)
        s_drop = _price_drop_score(benefit, prev)
        s_low = _alltime_low_score(r["model_no"], benefit)
        total_score = s_discount + s_drop + s_low

        review_count = r.get("review_count") or 0
        badges = get_enhanced_badges(
            r["model_no"], total_score, original, benefit, prev, review_count
        )

        scored.append({
            **r,
            "score": total_score,
            "score_breakdown": {
                "discount": s_discount,
                "price_drop": s_drop,
                "alltime_low": s_low,
            },
            "badges": badges,
            "discount_rate": round((original - benefit) / original * 100, 1) if original else 0,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    result = scored[:TOP_N]

    for i, item in enumerate(result, 1):
        item["rank"] = i

    return result


def get_all_recommendations(filters_per_category: dict | None = None) -> dict:
    """전체 카테고리 추천 결과 반환"""
    result = {}
    for key, meta in CATEGORIES.items():
        cat_filters = (filters_per_category or {}).get(key)
        items = rank_category(key, filters=cat_filters)
        result[key] = {
            "category_key": key,
            "category_name": meta["name"],
            "items": items,
        }
    return result
