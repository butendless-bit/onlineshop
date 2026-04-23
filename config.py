import os
from dotenv import load_dotenv

load_dotenv()

# ── 매장 정보 ──────────────────────────────────────────────────────────────────
STORE_NAME = os.getenv("STORE_NAME", "롯데하이마트")

# ── 크롤링 설정 ────────────────────────────────────────────────────────────────
CRAWL_DELAY = float(os.getenv("CRAWL_DELAY", "1.5"))   # 요청 간격(초)
CRAWL_RETRY = int(os.getenv("CRAWL_RETRY", "3"))        # 실패 시 재시도 횟수
CRAWL_TIMEOUT = int(os.getenv("CRAWL_TIMEOUT", "15"))   # 요청 타임아웃(초)
CRAWL_HOUR = int(os.getenv("CRAWL_HOUR", "8"))          # 자동 실행 시각(시)
CRAWL_PAGE_SIZE = int(os.getenv("CRAWL_PAGE_SIZE", "100"))  # 페이지당 상품 수 (최대화)
CRAWL_MAX_PAGES = int(os.getenv("CRAWL_MAX_PAGES", "50"))   # 안전 상한 (100개씩 50페이지 = 5000개)

# ── 크롤링 정렬 옵션 (여러 정렬로 누락 방지) ────────────────────────────────
CRAWL_SORT_ORDERS = ["WEIGHT", "DATE", "PRICE_LOW", "PRICE_HIGH"]

# ── DB ────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_is_vercel = bool(os.environ.get("VERCEL"))
DB_PATH  = "/tmp/himart.db"                             if _is_vercel else os.path.join(BASE_DIR, "data", "himart.db")
LOG_PATH = "/tmp/crawler.log"                           if _is_vercel else os.path.join(BASE_DIR, "logs", "crawler.log")
DB_SEED  = os.path.join(BASE_DIR, "data", "himart.db")  # 번들된 시드 DB (읽기 전용)

# ── 카테고리 ───────────────────────────────────────────────────────────────────
CATEGORIES = {
    "tv":           {"name": "TV",        "code": "002001"},
    "refrigerator": {"name": "냉장고",    "code": "002002"},
    "washer":       {"name": "세탁기",    "code": "002003"},
    "dryer":        {"name": "건조기",    "code": "002004"},
    "kimchi":       {"name": "김치냉장고","code": "002005"},
    "aircon":       {"name": "에어컨",    "code": "002006"},
    "airpurifier":  {"name": "공기청정기","code": "002007"},
    "vacuum":       {"name": "청소기",    "code": "002008"},
    "dishwasher":   {"name": "식기세척기","code": "002009"},
    "range":        {"name": "전기레인지","code": "002010"},
    "laptop":       {"name": "노트북",    "code": "002011"},
    "tablet":       {"name": "태블릿",    "code": "002012"},
}

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ── 랭킹 알고리즘 가중치 ──────────────────────────────────────────────────────
TOP_N = 10                   # 카테고리별 추천 수
SCORE_POPULARITY_MAX = 60    # 인기도 (e-himart WEIGHT 순위 기반) — 최대 가중치
SCORE_REVIEW_MAX = 20        # 리뷰 수 (판매량 대리 지표)
SCORE_DISCOUNT_MAX = 40      # 할인율 점수 상한
SCORE_PRICE_DROP_MAX = 40    # 가격 하락 점수 상한
SCORE_ALLTIME_LOW = 20       # 역대 최저가 보너스
# 총 160점 만점

# ── 카테고리별 다중 검색어 (끝까지 페이징 · 페이지 수 제한 없음) ──────────────
# 형식: {category_key: [keyword, ...]}
# 각 키워드를 CRAWL_SORT_ORDERS 정렬로 끝까지 긁고 중복 제거
CATEGORY_SEARCH_TERMS = {
    "tv":           ["TV", "OLED TV", "QLED TV", "소형 TV", "대형 TV", "Mini LED TV"],
    "refrigerator": ["냉장고", "양문형 냉장고", "4도어 냉장고", "소형 냉장고", "비스포크 냉장고"],
    "washer":       ["세탁기", "드럼세탁기", "통돌이세탁기", "대용량 세탁기", "미니세탁기"],
    "dryer":        ["건조기", "히트펌프 건조기", "대용량 건조기", "의류건조기"],
    "kimchi":       ["김치냉장고", "스탠드 김치냉장고", "뚜껑형 김치냉장고"],
    "aircon":       ["에어컨", "스탠드 에어컨", "벽걸이 에어컨", "시스템 에어컨", "이동식 에어컨"],
    "airpurifier":  ["공기청정기", "대형 공기청정기", "소형 공기청정기"],
    "vacuum":       ["청소기", "무선청소기", "로봇청소기", "유선청소기", "물걸레청소기"],
    "dishwasher":   ["식기세척기", "빌트인 식기세척기", "소형 식기세척기"],
    "range":        ["전기레인지", "인덕션", "하이브리드레인지", "가스레인지"],
    "laptop":       ["노트북", "게이밍 노트북", "초경량 노트북", "비즈니스 노트북", "맥북"],
    "tablet":       ["태블릿", "갤럭시탭", "아이패드", "태블릿PC"],
}

# ── 카테고리별 서브 필터 정의 ──────────────────────────────────────────────────
# group: 표시 그룹명, key: spec JSON 키, filters: [{label, value}]
SUB_FILTERS = {
    "tv": [
        {"group": "크기", "key": "size_group", "filters": [
            {"label": "80인치 이상", "value": "80+"},
            {"label": "70~79인치",   "value": "70s"},
            {"label": "60~69인치",   "value": "60s"},
            {"label": "50~59인치",   "value": "50s"},
            {"label": "40~49인치",   "value": "40s"},
            {"label": "32~39인치",   "value": "30s"},
            {"label": "31인치 이하", "value": "small"},
        ]},
        {"group": "종류", "key": "tv_type", "filters": [
            {"label": "OLED", "value": "OLED"},
            {"label": "QNED", "value": "QNED"},
            {"label": "QLED", "value": "QLED"},
            {"label": "LED",  "value": "LED"},
        ]},
    ],
    "refrigerator": [
        {"group": "종류", "key": "fridge_type", "filters": [
            {"label": "일반형",  "value": "일반형"},
            {"label": "양문형",  "value": "양문형"},
            {"label": "4도어",   "value": "4도어"},
            {"label": "소형",    "value": "소형"},
        ]},
        {"group": "용량", "key": "fridge_size", "filters": [
            {"label": "800L 이상", "value": "800+"},
            {"label": "600~799L",  "value": "600s"},
            {"label": "400~599L",  "value": "400s"},
            {"label": "400L 미만", "value": "small"},
        ]},
    ],
    "washer": [
        {"group": "종류", "key": "washer_type", "filters": [
            {"label": "드럼",   "value": "드럼"},
            {"label": "통돌이", "value": "통돌이"},
        ]},
        {"group": "용량", "key": "washer_cap", "filters": [
            {"label": "20kg 이상", "value": "20+"},
            {"label": "15~19kg",   "value": "15s"},
            {"label": "12~14kg",   "value": "12s"},
            {"label": "12kg 미만", "value": "small"},
        ]},
    ],
    "dryer": [
        {"group": "종류", "key": "dryer_type", "filters": [
            {"label": "히트펌프", "value": "히트펌프"},
            {"label": "전기히터", "value": "전기히터"},
        ]},
        {"group": "용량", "key": "dryer_cap", "filters": [
            {"label": "16kg 이상", "value": "16+"},
            {"label": "12~15kg",   "value": "12s"},
            {"label": "12kg 미만", "value": "small"},
        ]},
    ],
    "kimchi": [
        {"group": "형태", "key": "kimchi_type", "filters": [
            {"label": "스탠드형", "value": "스탠드"},
            {"label": "뚜껑형",   "value": "뚜껑"},
        ]},
        {"group": "용량", "key": "kimchi_size", "filters": [
            {"label": "500L 이상", "value": "500+"},
            {"label": "300~499L",  "value": "300s"},
            {"label": "300L 미만", "value": "small"},
        ]},
    ],
    "aircon": [
        {"group": "형태", "key": "aircon_type", "filters": [
            {"label": "벽걸이형",     "value": "벽걸이"},
            {"label": "스탠드형",     "value": "스탠드"},
            {"label": "시스템에어컨", "value": "시스템"},
        ]},
        {"group": "평형", "key": "aircon_size", "filters": [
            {"label": "20평 이상", "value": "20+"},
            {"label": "15~19평",   "value": "15s"},
            {"label": "10~14평",   "value": "10s"},
            {"label": "10평 미만", "value": "small"},
        ]},
    ],
    "airpurifier": [
        {"group": "적용 면적", "key": "purifier_size", "filters": [
            {"label": "60평 이상", "value": "60+"},
            {"label": "40~59평",   "value": "40s"},
            {"label": "20~39평",   "value": "20s"},
            {"label": "20평 미만", "value": "small"},
        ]},
    ],
    "vacuum": [
        {"group": "종류", "key": "vacuum_type", "filters": [
            {"label": "무선청소기", "value": "무선"},
            {"label": "로봇청소기", "value": "로봇"},
            {"label": "유선청소기", "value": "유선"},
        ]},
    ],
    "dishwasher": [
        {"group": "종류", "key": "dish_type", "filters": [
            {"label": "프리스탠딩", "value": "프리스탠딩"},
            {"label": "빌트인",     "value": "빌트인"},
            {"label": "카운터탑",   "value": "카운터탑"},
        ]},
    ],
    "range": [
        {"group": "종류", "key": "range_type", "filters": [
            {"label": "인덕션",     "value": "인덕션"},
            {"label": "하이브리드", "value": "하이브리드"},
            {"label": "하이라이트", "value": "하이라이트"},
        ]},
        {"group": "구성", "key": "range_burner", "filters": [
            {"label": "3구 이상", "value": "3+"},
            {"label": "2구",      "value": "2"},
            {"label": "1구",      "value": "1"},
        ]},
    ],
    "laptop": [
        {"group": "브랜드", "key": "laptop_brand", "filters": [
            {"label": "삼성",   "value": "삼성"},
            {"label": "LG",     "value": "LG"},
            {"label": "애플",   "value": "애플"},
            {"label": "기타",   "value": "기타"},
        ]},
        {"group": "화면크기", "key": "laptop_size", "filters": [
            {"label": "16인치 이상", "value": "16+"},
            {"label": "14~15인치",   "value": "14s"},
            {"label": "13인치 이하", "value": "small"},
        ]},
    ],
    "tablet": [
        {"group": "브랜드", "key": "tablet_brand", "filters": [
            {"label": "삼성",   "value": "삼성"},
            {"label": "애플",   "value": "애플"},
            {"label": "기타",   "value": "기타"},
        ]},
        {"group": "화면크기", "key": "tablet_size", "filters": [
            {"label": "12인치 이상", "value": "12+"},
            {"label": "10~11인치",   "value": "10s"},
            {"label": "9인치 이하",  "value": "small"},
        ]},
    ],
}

# ── 카테고리별 구독상품 검색어 ─────────────────────────────────────────────────
SUBSCRIPTION_SEARCH_TERMS = {
    "tv":           "TV 구독",
    "refrigerator": "냉장고 구독",
    "washer":       "세탁기 구독",
    "dryer":        "건조기 구독",
    "kimchi":       "김치냉장고 구독",
    "aircon":       "에어컨 구독",
    "airpurifier":  "공기청정기 구독",
    "vacuum":       "청소기 구독",
    "dishwasher":   "식기세척기 구독",
    "range":        "전기레인지 구독",
    "laptop":       "노트북 구독",
    "tablet":       "태블릿 구독",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
