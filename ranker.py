"""
HiMart Ranker — 카테고리별 TOP 10 추천 알고리즘 (총 100점 만점)

가중치:
  판매량 (popularity_rank)        50점 — e-himart WEIGHT 기반 인기순위
  리뷰 수 (review_count)          20점 — 리뷰 = 실구매 검증 지표
  동급사양대비 가성비              20점 — 할인율 + 카테고리 내 상대 가격
  직전대비 가격인하                10점 — 어제 대비 하락폭
"""
import json
from statistics import median
from config import (
    CATEGORIES, TOP_N,
    SCORE_POPULARITY_MAX, SCORE_REVIEW_MAX,
    SCORE_VALUE_MAX, SCORE_PRICE_DROP_MAX,
)
from database import get_latest_prices, get_alltime_lows, get_competitor_prices
from badge_calculator import get_enhanced_badges


# ── 판매량 50점 ────────────────────────────────────────────────────────────────
def _popularity_score(rank: int | None) -> int:
    """e-himart WEIGHT(인기순) 기반 점수 — 최대 50점.
    rank가 작을수록(상위일수록) 높은 점수. 미수집(NULL) = 0점.
    """
    if not rank or rank <= 0:
        return 0
    if rank <= 10:   return SCORE_POPULARITY_MAX               # 50
    if rank <= 30:   return int(SCORE_POPULARITY_MAX * 0.84)   # 42
    if rank <= 50:   return int(SCORE_POPULARITY_MAX * 0.72)   # 36
    if rank <= 100:  return int(SCORE_POPULARITY_MAX * 0.58)   # 29
    if rank <= 200:  return int(SCORE_POPULARITY_MAX * 0.40)   # 20
    if rank <= 500:  return int(SCORE_POPULARITY_MAX * 0.20)   # 10
    if rank <= 1000: return int(SCORE_POPULARITY_MAX * 0.08)   # 4
    return 0


# ── 리뷰 수 20점 ───────────────────────────────────────────────────────────────
def _review_score(review_count: int | None) -> int:
    """리뷰 수 기반 점수 — 최대 20점 (로그 스케일)."""
    if not review_count or review_count <= 0:
        return 0
    if review_count >= 1000: return SCORE_REVIEW_MAX               # 20
    if review_count >= 500:  return int(SCORE_REVIEW_MAX * 0.75)   # 15
    if review_count >= 200:  return int(SCORE_REVIEW_MAX * 0.55)   # 11
    if review_count >= 100:  return int(SCORE_REVIEW_MAX * 0.40)   # 8
    if review_count >= 30:   return int(SCORE_REVIEW_MAX * 0.25)   # 5
    if review_count >= 10:   return int(SCORE_REVIEW_MAX * 0.10)   # 2
    return 0


# ── 동급사양대비 가성비 20점 ───────────────────────────────────────────────────
def _value_score(benefit: int, original: int, all_benefits: list[int]) -> int:
    """동급사양대비 가성비 점수 — 최대 20점.

    ① 할인율 점수 (최대 10점): 5% 할인마다 1점, 50% 이상 = 10점
    ② 카테고리 내 상대 가격 점수 (최대 10점):
       중앙값 이하일수록 높은 점수 — 같은 가격대에서 더 저렴하면 가성비 우수
    """
    if not benefit or not original or original <= 0:
        return 0

    # ① 할인율
    rate = (original - benefit) / original * 100
    discount_pts = min(int(rate / 5), 10)

    # ② 카테고리 내 상대 가격 (중앙값 대비)
    if all_benefits and len(all_benefits) >= 2:
        med = median(all_benefits)
        if benefit <= med * 0.60:   price_pts = 10
        elif benefit <= med * 0.75: price_pts = 8
        elif benefit <= med * 0.90: price_pts = 6
        elif benefit <= med:        price_pts = 4
        elif benefit <= med * 1.20: price_pts = 2
        else:                       price_pts = 0
    else:
        price_pts = 5  # 비교 대상 부족 시 중간값 부여

    return min(discount_pts + price_pts, SCORE_VALUE_MAX)


# ── 직전대비 가격인하 10점 ─────────────────────────────────────────────────────
def _price_drop_score(benefit: int, prev_benefit: int | None) -> int:
    """직전 수집일 대비 가격 하락 점수 — 최대 10점."""
    if not benefit or not prev_benefit:
        return 0
    drop = prev_benefit - benefit
    if drop <= 0:        return 0
    if drop >= 200_000:  return 10
    if drop >= 100_000:  return 8
    if drop >= 50_000:   return 6
    if drop >= 20_000:   return 4
    if drop >= 5_000:    return 2
    return 1


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

    # 배치 조회로 N+1 쿼리 방지
    model_nos = [r["model_no"] for r in rows]
    alltime_lows = get_alltime_lows(model_nos)
    naver_prices = get_competitor_prices(model_nos)

    # 가성비 계산용: 카테고리 내 유효 benefit_price 전체 목록
    valid_benefits = [
        r.get("benefit_price") or r.get("sale_price") or 0
        for r in rows
        if (r.get("benefit_price") or r.get("sale_price") or 0) > 200_000
    ]

    scored = []

    for r in rows:
        original = r.get("original_price") or 0
        benefit  = r.get("benefit_price") or r.get("sale_price") or 0
        prev     = r.get("prev_benefit_price")

        if benefit == 0 or benefit <= 200_000:
            continue

        alltime_low  = alltime_lows.get(r["model_no"])
        naver_price  = naver_prices.get(r["model_no"])
        review_count = r.get("review_count") or 0
        pop_rank     = r.get("popularity_rank")

        s_popularity = _popularity_score(pop_rank)
        s_review     = _review_score(review_count)
        s_value      = _value_score(benefit, original, valid_benefits)
        s_drop       = _price_drop_score(benefit, prev)
        total_score  = s_popularity + s_review + s_value + s_drop

        badges = get_enhanced_badges(
            r["model_no"], total_score, original, benefit, prev, review_count,
            alltime_low=alltime_low, naver_price=naver_price,
        )

        scored.append({
            **r,
            "score": total_score,
            "score_breakdown": {
                "popularity":  s_popularity,
                "review":      s_review,
                "value":       s_value,
                "price_drop":  s_drop,
            },
            "badges": badges,
            "discount_rate": round((original - benefit) / original * 100, 1) if original else 0,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    result = scored[:TOP_N]

    for i, item in enumerate(result, 1):
        item["rank"] = i
        bd = item["score_breakdown"]
        reasons = []

        # 판매량 (50점 기준)
        if bd.get("popularity", 0) >= 42:
            reasons.append("🏆 베스트셀러")
        elif bd.get("popularity", 0) >= 20:
            reasons.append("인기 상품")

        # 리뷰
        if bd.get("review", 0) >= 11:
            reasons.append("리뷰 다수")

        # 가성비
        if bd.get("value", 0) >= 15:
            reasons.append(f"⚡ 가성비 {item['discount_rate']:.0f}% 할인")
        elif bd.get("value", 0) >= 8:
            reasons.append(f"🏷 {item['discount_rate']:.0f}% 할인")

        # 가격인하
        if bd.get("price_drop", 0) >= 6:
            reasons.append("📉 최근 가격 인하")

        if not reasons:
            reasons.append("✅ 가성비 추천 상품")

        item["reason"] = " · ".join(reasons)

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
