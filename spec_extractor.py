"""
HiMart Spec Extractor — 상품명/모델번호에서 카테고리별 사양 추출
"""
import re
import json


def _inch(name: str, model_no: str) -> int | None:
    m = re.search(r'(\d{2,3})\s*(?:인치|형|")', name)
    if m:
        return int(m.group(1))
    # 모델번호 패턴: QN65, OLED65, UN55, KU65, LM65 등
    m = re.search(r'(?:QN|OLED|UN|KU|LM|UM|KS|QE)(\d{2})', model_no.upper())
    if m:
        v = int(m.group(1))
        if 20 <= v <= 120:
            return v
    return None


def _kg(name: str) -> float | None:
    m = re.search(r'(\d+(?:\.\d+)?)\s*[Kk][Gg]', name)
    return float(m.group(1)) if m else None


def _liter(name: str) -> int | None:
    m = re.search(r'(\d{2,4})\s*[Ll](?!\w)', name)
    return int(m.group(1)) if m else None


def _pyeong(name: str) -> int | None:
    m = re.search(r'(\d+)\s*평', name)
    return int(m.group(1)) if m else None


# ── TV ────────────────────────────────────────────────────────────────────────
def _extract_tv(name: str, model_no: str) -> dict:
    spec = {}

    inch = _inch(name, model_no)
    if inch:
        if inch >= 80:   spec["size_group"] = "80+"
        elif inch >= 70: spec["size_group"] = "70s"
        elif inch >= 60: spec["size_group"] = "60s"
        elif inch >= 50: spec["size_group"] = "50s"
        elif inch >= 40: spec["size_group"] = "40s"
        elif inch >= 32: spec["size_group"] = "30s"
        else:            spec["size_group"] = "small"

    combined = name.upper() + " " + model_no.upper()
    if "OLED" in combined:   spec["tv_type"] = "OLED"
    elif "QNED" in combined: spec["tv_type"] = "QNED"
    elif "QLED" in combined: spec["tv_type"] = "QLED"
    else:                    spec["tv_type"] = "LED"

    return spec


# ── 냉장고 ─────────────────────────────────────────────────────────────────────
def _extract_refrigerator(name: str, model_no: str) -> dict:
    spec = {}

    if any(k in name for k in ["양문형", "사이드바이사이드", "Side by Side"]):
        spec["fridge_type"] = "양문형"
    elif any(k in name for k in ["4도어", "프렌치도어", "French Door"]):
        spec["fridge_type"] = "4도어"
    else:
        l = _liter(name)
        spec["fridge_type"] = "소형" if (l and l < 200) else "일반형"

    l = _liter(name)
    if l:
        if l >= 800:   spec["fridge_size"] = "800+"
        elif l >= 600: spec["fridge_size"] = "600s"
        elif l >= 400: spec["fridge_size"] = "400s"
        else:          spec["fridge_size"] = "small"

    return spec


# ── 세탁기 ─────────────────────────────────────────────────────────────────────
def _extract_washer(name: str, model_no: str) -> dict:
    spec = {}

    if "드럼" in name:
        spec["washer_type"] = "드럼"
    elif any(k in name for k in ["통돌이", "일반세탁"]):
        spec["washer_type"] = "통돌이"
    else:
        spec["washer_type"] = "드럼"  # 기본값 (최신 제품 대부분 드럼)

    kg = _kg(name)
    if kg:
        if kg >= 20:    spec["washer_cap"] = "20+"
        elif kg >= 15:  spec["washer_cap"] = "15s"
        elif kg >= 12:  spec["washer_cap"] = "12s"
        else:           spec["washer_cap"] = "small"

    return spec


# ── 건조기 ─────────────────────────────────────────────────────────────────────
def _extract_dryer(name: str, model_no: str) -> dict:
    spec = {}

    if "히트펌프" in name:
        spec["dryer_type"] = "히트펌프"
    elif any(k in name for k in ["전기히터", "전기식", "콘덴서"]):
        spec["dryer_type"] = "전기히터"
    else:
        spec["dryer_type"] = "히트펌프"  # 기본값

    kg = _kg(name)
    if kg:
        if kg >= 16:   spec["dryer_cap"] = "16+"
        elif kg >= 12: spec["dryer_cap"] = "12s"
        else:          spec["dryer_cap"] = "small"

    return spec


# ── 김치냉장고 ─────────────────────────────────────────────────────────────────
def _extract_kimchi(name: str, model_no: str) -> dict:
    spec = {}

    if any(k in name for k in ["스탠드", "입형", "세로"]):
        spec["kimchi_type"] = "스탠드"
    elif any(k in name for k in ["뚜껑", "상단", "김치통"]):
        spec["kimchi_type"] = "뚜껑"
    else:
        spec["kimchi_type"] = "스탠드"  # 기본값

    l = _liter(name)
    if l:
        if l >= 500:   spec["kimchi_size"] = "500+"
        elif l >= 300: spec["kimchi_size"] = "300s"
        else:          spec["kimchi_size"] = "small"

    return spec


# ── 에어컨 ─────────────────────────────────────────────────────────────────────
def _extract_aircon(name: str, model_no: str) -> dict:
    spec = {}

    if any(k in name for k in ["스탠드", "타워형"]):
        spec["aircon_type"] = "스탠드"
    elif any(k in name for k in ["시스템", "천장형", "4way", "덕트"]):
        spec["aircon_type"] = "시스템"
    else:
        spec["aircon_type"] = "벽걸이"  # 기본값

    py = _pyeong(name)
    if py:
        if py >= 20:    spec["aircon_size"] = "20+"
        elif py >= 15:  spec["aircon_size"] = "15s"
        elif py >= 10:  spec["aircon_size"] = "10s"
        else:           spec["aircon_size"] = "small"

    return spec


# ── 공기청정기 ─────────────────────────────────────────────────────────────────
def _extract_airpurifier(name: str, model_no: str) -> dict:
    spec = {}

    py = _pyeong(name)
    if py:
        if py >= 60:    spec["purifier_size"] = "60+"
        elif py >= 40:  spec["purifier_size"] = "40s"
        elif py >= 20:  spec["purifier_size"] = "20s"
        else:           spec["purifier_size"] = "small"

    return spec


# ── 청소기 ─────────────────────────────────────────────────────────────────────
def _extract_vacuum(name: str, model_no: str) -> dict:
    spec = {}

    if any(k in name for k in ["로봇", "로봇청소기"]):
        spec["vacuum_type"] = "로봇"
    elif any(k in name for k in ["유선", "실린더"]):
        spec["vacuum_type"] = "유선"
    else:
        spec["vacuum_type"] = "무선"  # 기본값 (무선이 대세)

    return spec


# ── 식기세척기 ─────────────────────────────────────────────────────────────────
def _extract_dishwasher(name: str, model_no: str) -> dict:
    spec = {}

    if any(k in name for k in ["빌트인", "붙박이"]):
        spec["dish_type"] = "빌트인"
    elif any(k in name for k in ["카운터탑", "소형", "미니", "테이블"]):
        spec["dish_type"] = "카운터탑"
    else:
        spec["dish_type"] = "프리스탠딩"  # 기본값

    return spec


# ── 전기레인지 ─────────────────────────────────────────────────────────────────
def _extract_range(name: str, model_no: str) -> dict:
    spec = {}

    if "하이브리드" in name:
        spec["range_type"] = "하이브리드"
    elif any(k in name for k in ["하이라이트", "세라믹"]):
        spec["range_type"] = "하이라이트"
    else:
        spec["range_type"] = "인덕션"  # 기본값

    m = re.search(r'(\d+)\s*구', name)
    if m:
        b = int(m.group(1))
        spec["range_burner"] = "3+" if b >= 3 else str(b)

    return spec


# ── 통합 추출 ─────────────────────────────────────────────────────────────────
_EXTRACTORS = {
    "tv":           _extract_tv,
    "refrigerator": _extract_refrigerator,
    "washer":       _extract_washer,
    "dryer":        _extract_dryer,
    "kimchi":       _extract_kimchi,
    "aircon":       _extract_aircon,
    "airpurifier":  _extract_airpurifier,
    "vacuum":       _extract_vacuum,
    "dishwasher":   _extract_dishwasher,
    "range":        _extract_range,
}


def extract_spec(product_name: str, model_no: str, category: str) -> str:
    """상품명·모델번호에서 스펙을 추출하여 JSON 문자열 반환"""
    fn = _EXTRACTORS.get(category)
    if not fn:
        return "{}"
    spec = fn(product_name or "", model_no or "")
    return json.dumps(spec, ensure_ascii=False)
