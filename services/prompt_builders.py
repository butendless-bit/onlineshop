"""Prompt builders for promo copy generation."""

from __future__ import annotations

import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_instagram_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    event_title = str(payload.get("event_title") or "").strip()
    store_name = str(payload.get("store_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    kakao = str(payload.get("kakao_channel_url") or "").strip()
    landing = payload.get("landing") or {}
    dossiers = payload.get("product_dossiers") or []

    system = """
당신은 프리미엄 가전 매장의 SNS 광고 카피라이터입니다.
출력은 반드시 한국어로만 작성합니다.
사실이 확인되지 않은 내용은 추측해서 쓰지 않습니다.
"""

    user_payload = {
        "event_title": event_title,
        "store_name": store_name,
        "contact": {
            "phone": phone,
            "kakao_channel_url": kakao,
        },
        "landing_context": {
            "landing_title": landing.get("landing_title", ""),
            "intro_text": landing.get("intro_text", ""),
            "disclaimer": landing.get("disclaimer", ""),
        },
        "product_dossiers": dossiers,
    }

    user = f"""
아래 데이터를 바탕으로 인스타그램 게시물 본문 1개만 작성해줘.

반드시 지킬 조건:
- 결과는 오직 게시물 본문만 출력하고, 설명이나 제목 후보나 추가 옵션은 쓰지 말 것
- 전체 길이는 15줄 이내로 작성할 것
- 첫 2줄 안에 시선을 잡는 광고 문구가 들어가야 함
- 인스타그램 업로드용 문구처럼 이모티콘을 이전보다 적극적으로 사용할 것
- 단, 아무 줄에나 남발하지 말고 핵심 메시지, 혜택, 상담 유도 문장에 집중해서 넣을 것
- 문장 길이를 너무 길게 끌지 말고, 한 줄씩 눈에 잘 들어오게 끊어 쓸 것
- 첫 문단은 고객이 바로 멈춰서 읽게 만드는 생활형 훅으로 시작할 것
- 한국 고객이 익숙하게 받아들이는 표현을 사용할 것
- 예: "이번에 많이 보시는 구성", "실사용 만족도 높은 모델", "가격 메리트가 괜찮은 편", "직접 비교해보시면 차이가 보이는 모델"
- 랜딩페이지와 상품 이미지를 보고 홍보하는 느낌으로 작성할 것
- 선택된 상품들을 그냥 나열하지 말고, 왜 이 상품들이 좋고 왜 지금 볼 만한지 자연스럽게 연결할 것
- 각 상품의 장점은 실제 상세페이지 정보에 근거해서 생활 맥락 중심으로 풀어줄 것
- 혜택, 가격 메리트, 상담 유도 문구는 과장 없이 광고 문구처럼 눈에 잘 들어오게 정리할 것
- "최고", "무조건", "지금 안 사면 손해" 같은 과한 표현은 쓰지 말 것
- 문체는 딱딱한 설명문보다 "매장에서 고객에게 추천하는 실전 광고문구"에 가깝게 쓸 것
- 상품이 여러 개여도 카탈로그처럼 번호를 매기지 말고, 한 흐름 안에서 자연스럽게 묶어 쓸 것
- 마지막은 방문 또는 문의를 유도하는 한두 줄 CTA로 마무리할 것
- 해시태그는 본문 마지막 줄에만 6개 이하로 넣을 것
- 결과 전체가 너무 밋밋하면 안 되고, 핵심어가 눈에 띄도록 리듬감 있게 구성할 것

입력 데이터:
{_json_block(user_payload)}
"""

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": user.strip()},
    ]


def build_blog_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    event_title = str(payload.get("event_title") or "").strip()
    store_name = str(payload.get("store_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    kakao = str(payload.get("kakao_channel_url") or "").strip()
    landing = payload.get("landing") or {}
    dossiers = payload.get("product_dossiers") or []
    target_length = int(payload.get("target_length") or 2000)

    system = """
당신은 프리미엄 가전 매장의 블로그 전문 에디터입니다.
출력은 반드시 한국어로만 작성합니다.
사실이 확인되지 않은 내용은 추측해서 쓰지 않습니다.
"""

    user_payload = {
        "event_title": event_title,
        "store_name": store_name,
        "contact": {
            "phone": phone,
            "kakao_channel_url": kakao,
        },
        "landing_context": {
            "landing_title": landing.get("landing_title", ""),
            "intro_text": landing.get("intro_text", ""),
            "disclaimer": landing.get("disclaimer", ""),
        },
        "product_dossiers": dossiers,
        "target_length": target_length,
    }

    user = f"""
아래 데이터를 바탕으로 네이버 블로그용 본문 1개만 작성해줘.

반드시 지킬 조건:
- 결과는 오직 블로그 본문만 출력하고, 제목 후보나 요약이나 메모는 쓰지 말 것
- 전체 분량은 공백 포함 약 {target_length}자 내외로 작성할 것
- 말투는 우리 매장 직원이 고객에게 직접 상담하면서 설명하는 듯한 톤으로 작성할 것
- 전문성은 유지하되 너무 딱딱하지 않게, 친근하고 신뢰감 있게 풀어쓸 것
- 한국 고객이 실제 매장 상담에서 자주 듣는 표현처럼 자연스럽게 쓸 것
- 예: "많이 물어보시는 부분", "이런 분들께 잘 맞습니다", "직접 보면 차이가 느껴지는 부분", "설치 전에 같이 보시면 좋습니다"
- 문장은 너무 길게 늘어뜨리지 말고, 읽기 편하게 호흡을 적절히 나눌 것
- 블로그 특성상 정보는 충분히 주되, 제품 설명이 교과서처럼 딱딱하지 않게 할 것
- 선택된 상품들을 모두 언급하되 단순 스펙 나열이 아니라 왜 이 제품이 좋은지, 어떤 고객에게 잘 맞는지, 실제로 비교할 때 어떤 메리트가 있는지 설명할 것
- 상품별 장점은 실제 상세페이지 정보에 근거해서 생활 맥락 중심으로 소개할 것
- 혜택과 가격 메리트는 자연스럽게 녹여 쓰고, 과한 세일 문구처럼 보이지 않게 할 것
- 문단 흐름은 "행사 소개 -> 상품별 설명 -> 상담 포인트/선택 팁 -> 방문/문의 안내" 순서로 자연스럽게 이어갈 것
- 각 상품 문단은 "이 제품이 왜 눈에 들어오는지 -> 어떤 고객에게 잘 맞는지 -> 상담 시 같이 보면 좋은 포인트" 흐름으로 쓰는 것을 우선할 것
- 여러 상품을 소개하더라도 중간중간 비교 기준이나 선택 팁을 넣어, 실제 상담받는 느낌이 나게 할 것
- 한국 블로그 독자가 읽기 편하도록 지나치게 추상적인 표현보다 생활형 표현을 사용할 것
- 마크다운 기호, 번호 목록, 표, 해시태그는 쓰지 말 것
- "최고", "무조건", "안 사면 손해" 같은 과장 표현은 쓰지 말 것

입력 데이터:
{_json_block(user_payload)}
"""

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": user.strip()},
    ]
