"""
HiMart Badge Calculator — 선정 근거 배지 산출 모듈

배지 종류:
  🔥 역대 최저가   — 현재가 ≤ 역대 최저가
  💰 최저가        — 종합 점수 ≥ 60
  📉 가격 인하     — 어제 대비 가격 하락
  ⚡ X% 할인      — 할인율 ≥ 30%
  🏷 X% 할인       — 할인율 10~29%
  🆚 네이버 대비   — 네이버 최저가보다 X% 저렴
  ⭐ 리뷰 N개+     — 리뷰 수 기준 인기상품
"""
from database import get_alltime_low, get_competitor_price


# 리뷰수 기준 임계값
REVIEW_THRESHOLD_HIGH = 500    # ⭐⭐ 아주 많음
REVIEW_THRESHOLD_LOW  = 100    # ⭐  많음

# 네이버 대비 유의미한 가격 차이 기준 (%)
NAVER_COMPARE_MIN_DIFF = 3


def get_enhanced_badges(
    model_no: str,
    score: int,
    original: int,
    benefit: int,
    prev_benefit: int | None,
    review_count: int = 0,
    alltime_low: int | None = None,
    naver_price: int | None = None,
) -> list[str]:
    """종합 배지 계산 — ranker.py 의 _assign_badges 대체.
    alltime_low, naver_price 를 미리 조회해서 전달하면 추가 DB 쿼리를 생략합니다.
    """
    badges = []

    # ① 역대 최저가 / 최저가
    low = alltime_low if alltime_low is not None else get_alltime_low(model_no)
    if low and benefit and benefit <= low:
        badges.append("🔥 역대 최저가")
    elif score >= 60:
        badges.append("💰 최저가")

    # ② 가격 인하
    if prev_benefit and benefit and prev_benefit > benefit:
        diff = prev_benefit - benefit
        badges.append(f"📉 {int(diff/1000)}천원 인하")

    # ③ 할인율
    if original and benefit and original > benefit:
        rate = (original - benefit) / original * 100
        if rate >= 30:
            badges.append(f"⚡ {int(rate)}% 할인")
        elif rate >= 10:
            badges.append(f"🏷 {int(rate)}% 할인")

    # ④ 네이버 최저가 비교
    naver = naver_price if naver_price is not None else get_competitor_price(model_no)
    if naver and benefit and naver > 0:
        diff_pct = (naver - benefit) / naver * 100
        if diff_pct >= NAVER_COMPARE_MIN_DIFF:
            badges.append(f"🆚 네이버보다 {int(diff_pct)}% ↓")

    # ⑤ 리뷰 인기
    if review_count and review_count >= REVIEW_THRESHOLD_HIGH:
        badges.append(f"⭐⭐ 리뷰 {review_count:,}개+")
    elif review_count and review_count >= REVIEW_THRESHOLD_LOW:
        badges.append(f"⭐ 리뷰 {review_count:,}개+")

    return badges or ["✅ 추천"]
