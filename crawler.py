"""
HiMart Crawler — e-himart.co.kr REST API 기반 가격 수집기
확인된 API: /app/api/v1/search?query={keyword}&pageNo={n}&pageSize=20

가격 구조:
  priceInfo.salePrc        → 판매가 (행사가)
  priceInfo.dscntSalePrc   → 할인판매가
  priceInfo.maxBenefitPrc  → 최대혜택가 (카드 등 포함 최저가)
  priceInfo.prcPrefix      → null이면 일반 판매 / '월 구독료'이면 렌탈 (제외)
"""
import time
import logging
import os
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import re
import json
from config import (
    CATEGORIES, CRAWL_DELAY, CRAWL_RETRY, CRAWL_TIMEOUT, USER_AGENT, LOG_PATH,
    CATEGORY_SEARCH_TERMS, SUBSCRIPTION_SEARCH_TERMS,
)
from database import (
    init_db, upsert_product, insert_price,
    update_review_count, upsert_competitor_price, upsert_subscription_from_crawl,
)
from spec_extractor import extract_spec

# ── 로깅 ──────────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_URL   = "https://www.e-himart.co.kr"
SEARCH_API = f"{BASE_URL}/app/api/v1/search"

# 호환성을 위해 유지 (구독크롤러 등에서 사용)
CATEGORY_KEYWORDS = {
    "tv":           "TV",
    "refrigerator": "냉장고",
    "washer":       "세탁기",
    "dryer":        "건조기",
    "kimchi":       "김치냉장고",
    "aircon":       "에어컨",
    "airpurifier":  "공기청정기",
    "vacuum":       "청소기",
    "dishwasher":   "식기세척기",
    "range":        "전기레인지",
    "laptop":       "노트북",
    "tablet":       "태블릿",
}

CATEGORY_INCLUDE_PATTERNS = {
    "tv": [
        r"\bTV\b", r"OLED", r"QLED", r"QNED", r"UHD", r"Mini LED", r"구글 TV", r"스마트 TV",
        r"\d{2,3}\s*(?:cm|인치|\")",
    ],
    "refrigerator": [r"냉장고", r"\d{2,4}\s*L", r"양문형", r"일반냉장고"],
    "washer": [r"세탁기", r"드럼", r"통돌이", r"\d{1,2}(?:\.\d)?\s*kg"],
    "dryer": [r"건조기", r"히트펌프", r"\d{1,2}(?:\.\d)?\s*kg"],
    "kimchi": [r"김치냉장고", r"딤채", r"김치톡톡"],
    "aircon": [r"에어컨", r"시스템에어컨", r"스탠드형", r"벽걸이형", r"\d{1,3}(?:\.\d)?\s*㎡"],
    "airpurifier": [r"공기청정기", r"헤파", r"청정"],
    "vacuum": [r"청소기", r"무선", r"유선", r"로봇청소기", r"싸이킹", r"흡입"],
    "dishwasher": [r"식기세척기", r"식세기"],
    "range": [r"인덕션", r"하이브리드", r"전기레인지", r"가스레인지"],
    "laptop": [r"노트북", r"그램", r"맥북", r"갤럭시북"],
    "tablet": [r"태블릿", r"아이패드", r"갤럭시탭", r"패드"],
}

CATEGORY_EXCLUDE_PATTERNS = {
    "tv": [r"아이패드", r"태블릿", r"갤럭시탭", r"노트북", r"맥북", r"모니터", r"사운드바"],
    "refrigerator": [r"정수기", r"냉동고", r"와인셀러"],
    "washer": [r"건조기", r"식기세척기", r"청소기"],
    "dryer": [r"세탁기", r"식품건조기", r"음식물처리기"],
    "kimchi": [r"정수기"],
    "aircon": [r"공기청정기", r"선풍기", r"제습기"],
    "airpurifier": [r"에어컨", r"제습기"],
    "vacuum": [r"공기청정기"],
    "dishwasher": [r"세제", r"린스", r"클리너"],
    "range": [r"전자레인지", r"오븐"],
    "laptop": [r"태블릿", r"아이패드"],
    "tablet": [r"\bTV\b", r"노트북", r"모니터"],
}


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=CRAWL_RETRY,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"{BASE_URL}/",
        "Origin": BASE_URL,
    })
    return session


def fetch_products(session: requests.Session, keyword: str, page_no: int) -> list[dict]:
    """검색 API로 상품 목록 1페이지 가져오기"""
    params = {
        "query":    keyword,
        "pageNo":   page_no,
        "pageSize": 20,
        "sort":     "POPULAR",
    }
    try:
        resp = session.get(SEARCH_API, params=params, timeout=CRAWL_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("product") or []
    except Exception as e:
        log.error(f"[API] 요청 실패 (keyword={keyword}, page={page_no}): {e}")
        return []


def _is_relevant_product(product_name: str, model_no: str, category_key: str) -> bool:
    text = f"{product_name} {model_no}".strip()
    if not text:
        return False

    exclude_patterns = CATEGORY_EXCLUDE_PATTERNS.get(category_key, [])
    if any(re.search(pattern, text, re.I) for pattern in exclude_patterns):
        return False

    include_patterns = CATEGORY_INCLUDE_PATTERNS.get(category_key, [])
    if not include_patterns:
        return True
    return any(re.search(pattern, text, re.I) for pattern in include_patterns)


def _parse_product(p: dict, category_key: str) -> bool:
    """상품 1개 파싱 → DB 저장. 성공 시 True 반환."""
    try:
        price_info = p.get("priceInfo") or {}

        # 렌탈/구독 상품 제외 (월 구독료 상품만 제외)
        if price_info.get("prcPrefix") == "월 구독료":
            return False

        model_no     = (p.get("mdlNm") or p.get("goodsNo") or "UNKNOWN").strip()
        product_name = (p.get("goodsNm") or "").strip()
        if not _is_relevant_product(product_name, model_no, category_key):
            log.info(f"[FILTER/{category_key}] skipped irrelevant product: {product_name} ({model_no})")
            return False
        goods_no     = p.get("goodsNo") or ""
        product_url  = (f"{BASE_URL}/app/goods/goodsDetail?goodsNo={goods_no}"
                        if goods_no else "")
        image_url    = p.get("imgPath") or p.get("imgAltPath") or ""

        sale_price    = price_info.get("salePrc")
        discnt_price  = price_info.get("dscntSalePrc")
        benefit_price = price_info.get("maxBenefitPrc")

        original_price = discnt_price or sale_price
        if not (benefit_price and original_price and benefit_price < original_price):
            benefit_price = original_price

        if not original_price:
            return False

        # 스펙 추출 (상품명 + 모델번호)
        spec = extract_spec(product_name, model_no, category_key)

        upsert_product(model_no, product_name, category_key, product_url, image_url, spec)
        insert_price(model_no, original_price, sale_price, benefit_price)

        review_cnt = (p.get("reviewCnt") or p.get("reviewCount")
                      or p.get("rvwCnt") or 0)
        if review_cnt:
            update_review_count(model_no, int(review_cnt))

        return True

    except Exception as e:
        log.debug(f"상품 파싱 오류: {e}")
        return False


def crawl_category(session: requests.Session, category_key: str) -> int:
    """카테고리 1개 다중 키워드 크롤링 → DB 저장. 저장된 상품 수 반환."""
    cat_name  = CATEGORIES[category_key]["name"]
    terms     = CATEGORY_SEARCH_TERMS.get(category_key, [(CATEGORY_KEYWORDS[category_key], 3)])
    seen      = set()  # 중복 model_no 방지
    count     = 0

    log.info(f"[{cat_name}] 크롤링 시작 — {len(terms)}개 키워드")

    for keyword, page_count in terms:
        log.info(f"[{cat_name}] keyword={keyword!r} ({page_count}페이지)")

        for page_no in range(1, page_count + 1):
            products = fetch_products(session, keyword, page_no)
            if not products:
                log.info(f"[{cat_name}] '{keyword}' 페이지 {page_no}: 상품 없음, 중단")
                break

            saved = 0
            for p in products:
                model_no = (p.get("mdlNm") or p.get("goodsNo") or "").strip()
                if model_no in seen:
                    continue
                seen.add(model_no)
                if _parse_product(p, category_key):
                    saved += 1
                    count += 1

            log.info(f"[{cat_name}] '{keyword}' 페이지 {page_no}: {saved}개 신규 저장")
            time.sleep(CRAWL_DELAY)

        time.sleep(CRAWL_DELAY)  # 키워드 간 간격

    log.info(f"[{cat_name}] 완료 — 총 {count}개 저장 (중복 제외)")
    return count


def fetch_review_count(session: requests.Session, goods_no: str) -> int:
    """e-himart 상품 리뷰 수 조회"""
    if not goods_no:
        return 0
    try:
        url = f"{BASE_URL}/app/api/v1/review/summary?goodsNo={goods_no}"
        resp = session.get(url, timeout=8)
        data = resp.json()
        # 응답 구조: {"totalCount": 123, ...} 또는 {"reviewCount": 123}
        return (data.get("totalCount") or data.get("reviewCount") or
                data.get("total") or 0)
    except Exception:
        return 0


def fetch_naver_price(session: requests.Session, keyword: str) -> int | None:
    """네이버 쇼핑 검색으로 최저가 조회 (공개 검색 파싱)"""
    try:
        naver_client_id = os.environ.get("NAVER_CLIENT_ID", "")
        naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
        if not naver_client_id or not naver_client_secret:
            return None
        url = "https://openapi.naver.com/v1/search/shop.json"
        headers = {
            "X-Naver-Client-Id":     naver_client_id,
            "X-Naver-Client-Secret": naver_client_secret,
        }
        resp = session.get(url, params={"query": keyword, "display": 5, "sort": "asc"},
                           headers=headers, timeout=8)
        if resp.status_code == 401:
            return None  # API 키 미설정
        data = resp.json()
        items = data.get("items") or []
        prices = [int(i.get("lprice") or 0) for i in items if i.get("lprice")]
        return min(prices) if prices else None
    except Exception:
        return None


def _parse_prc_txt(prc_txt: str | None) -> tuple[int | None, str | None]:
    """prcTxt 파싱 → (구독개월수, 케어플랜)
    예) '(60개월/안심케어1)' → (60, '안심케어1')
        '(36개월)'           → (36, None)
    """
    if not prc_txt:
        return None, None
    m_months = re.search(r'(\d+)개월', prc_txt)
    months = int(m_months.group(1)) if m_months else None
    m_care = re.search(r'(안심케어\d+)', prc_txt)
    care_plan = m_care.group(1) if m_care else None
    return months, care_plan


def crawl_subscription_by_category(session: requests.Session, category_key: str) -> int:
    """카테고리별 구독전용 상품 수집 (prcPrefix='월 구독료')"""
    cat_name = CATEGORIES.get(category_key, {}).get("name", category_key)
    keyword  = SUBSCRIPTION_SEARCH_TERMS.get(category_key, f"{cat_name} 구독")
    seen     = set()
    count    = 0

    log.info(f"[구독크롤/{cat_name}] keyword={keyword!r}")

    for page_no in range(1, 4):  # 최대 3페이지 (60개)
        try:
            params = {"query": keyword, "pageNo": page_no, "pageSize": 20, "sort": "POPULAR"}
            resp = session.get(SEARCH_API, params=params, timeout=CRAWL_TIMEOUT)
            resp.raise_for_status()
            products = resp.json().get("product") or []
        except Exception as e:
            log.error(f"[구독크롤/{cat_name}] page {page_no}: {e}")
            break

        if not products:
            break

        saved = 0
        for p in products:
            pi = p.get("priceInfo") or {}
            if pi.get("prcPrefix") != "월 구독료":
                continue

            goods_no    = p.get("goodsNo") or ""
            model_no    = (p.get("mdlNm") or goods_no or "UNKNOWN").strip()
            if model_no in seen:
                continue
            seen.add(model_no)

            product_name        = (p.get("goodsNm") or "").strip()
            monthly_fee         = int(pi.get("salePrc") or 0)
            card_benefit_monthly= int(pi.get("maxBenefitPrc") or monthly_fee)
            image_url           = p.get("imgPath") or p.get("imgAltPath") or ""
            product_url         = (f"{BASE_URL}/app/goods/goodsDetail?goodsNo={goods_no}"
                                   if goods_no else "")

            # prcTxt: '(60개월/안심케어1)' 파싱
            prc_txt = pi.get("prcTxt") or ""
            contract_months, care_plan = _parse_prc_txt(prc_txt)

            # goodsAttrs JSON
            goods_attrs = json.dumps(
                [{"grp": a.get("attrGrp",""), "val": a.get("attrVal","")}
                 for a in (p.get("goodsAttrs") or [])],
                ensure_ascii=False
            )

            if not monthly_fee:
                continue

            upsert_subscription_from_crawl(
                product_name, model_no, category_key,
                monthly_fee, image_url, product_url,
                contract_months=contract_months,
                care_plan=care_plan,
                card_benefit_monthly=card_benefit_monthly,
                goods_attrs=goods_attrs,
            )
            saved += 1
            count += 1

        log.info(f"[구독크롤/{cat_name}] page {page_no}: {saved}개 저장")
        time.sleep(CRAWL_DELAY)

    log.info(f"[구독크롤/{cat_name}] 완료 — {count}개")
    return count


def crawl_subscription_products(session: requests.Session) -> int:
    """전체 카테고리 구독상품 크롤링 (기존 호환 함수)"""
    total = 0
    for key in CATEGORIES:
        total += crawl_subscription_by_category(session, key)
        time.sleep(CRAWL_DELAY * 2)
    log.info(f"[구독크롤] 전체 완료 — {total}개")
    return total


def run_crawler(categories: list | None = None):
    """메인 크롤링 실행. categories=None 이면 전체 실행."""
    init_db()
    targets = categories or list(CATEGORIES.keys())
    session = _make_session()
    total   = 0

    log.info(f"크롤링 시작 — {len(targets)}개 카테고리")
    for key in targets:
        count = crawl_category(session, key)
        total += count
        time.sleep(CRAWL_DELAY * 2)

    log.info(f"크롤링 완료 — 총 {total}개 저장 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    return total


def run_subscription_crawler():
    """구독상품 크롤러 단독 실행"""
    init_db()
    session = _make_session()
    return crawl_subscription_products(session)


if __name__ == "__main__":
    import sys
    cats = sys.argv[1:] if len(sys.argv) > 1 else None
    run_crawler(cats)
