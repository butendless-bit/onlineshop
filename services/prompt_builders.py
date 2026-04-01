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
    products = payload.get("products") or []

    system = """
당신은 프리미엄 가전 매장의 SNS 광고 카피라이터입니다.
출력은 반드시 한국어로만 작성합니다.
사실이 확인되지 않은 내용은 추측해서 쓰지 않습니다.
반드시 JSON 형식으로만 출력합니다.
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
        "product_dossiers": dossiers or products,
    }

    user = f"""
아래 데이터를 바탕으로 인스타그램 게시물을 작성해줘.

반드시 지킬 조건:
- 문체는 딱딱한 설명문보다 "매장에서 고객에게 추천하는 실전 광고문구"에 가깝게 쓸 것
- 이모티콘을 핵심 메시지, 혜택, 상담 유도 문장에 집중해서 넣을 것
- 첫 문단은 고객이 바로 멈춰서 읽게 만드는 생활형 훅으로 시작할 것
- 한국 고객이 익숙하게 받아들이는 표현을 사용할 것 (예: "이번에 많이 보시는 구성", "실사용 만족도 높은 모델")
- 선택된 상품들을 그냥 나열하지 말고, 왜 이 상품들이 좋고 왜 지금 볼 만한지 자연스럽게 연결할 것
- 각 상품의 장점은 실제 상세페이지 정보에 근거해서 생활 맥락 중심으로 풀어줄 것
- "최고", "무조건", "지금 안 사면 손해" 같은 과한 표현은 쓰지 말 것
- 상품이 여러 개여도 카탈로그처럼 번호를 매기지 말고, 한 흐름 안에서 자연스럽게 묶어 쓸 것
- 마지막은 방문 또는 문의를 유도하는 한두 줄 CTA로 마무리할 것
- caption 전체 길이는 15줄 이내

다음 JSON 형식으로만 출력해 (다른 텍스트 없이):
{{
  "hooks": ["시선을 잡는 첫 줄 후보1", "시선을 잡는 첫 줄 후보2"],
  "caption": "인스타그램 게시물 본문 전체 (해시태그 제외)",
  "story_lines": ["스토리용 짧은 문구1", "스토리용 짧은 문구2", "스토리용 짧은 문구3"],
  "hashtags": ["#해시태그1", "#해시태그2", "#해시태그3", "#해시태그4", "#해시태그5", "#해시태그6"],
  "dm_reply": "문의 DM에 답할 때 사용할 짧은 답변 문구"
}}

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
    product_notes = payload.get("product_notes") or []
    products = payload.get("products") or []
    target_length = int(payload.get("target_length") or 2000)

    system = """
당신은 프리미엄 가전 매장의 블로그 전문 에디터입니다.
출력은 반드시 한국어로만 작성합니다.
사실이 확인되지 않은 내용은 추측해서 쓰지 않습니다.
반드시 JSON 형식으로만 출력합니다.
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
        "product_notes": product_notes or dossiers or products,
        "target_length": target_length,
    }

    user = f"""
아래 데이터를 바탕으로 네이버 블로그용 글을 작성해줘.

반드시 지킬 조건:
- 전체 분량은 공백 포함 약 {target_length}자 내외
- 말투는 매장 직원이 고객에게 직접 상담하면서 설명하는 듯한 톤
- 전문성은 유지하되 친근하고 신뢰감 있게 풀어쓸 것
- 한국 고객이 실제 매장 상담에서 자주 듣는 표현처럼 자연스럽게 (예: "많이 물어보시는 부분", "이런 분들께 잘 맞습니다")
- 선택된 상품들을 모두 언급하되 단순 스펙 나열이 아니라 왜 좋은지, 어떤 고객에게 잘 맞는지 설명
- 상품별 장점은 실제 상세페이지 정보에 근거해서 생활 맥락 중심으로 소개
- 마크다운 기호, 번호 목록, 표, 해시태그는 쓰지 말 것
- "최고", "무조건", "안 사면 손해" 같은 과장 표현은 쓰지 말 것
- 문단 흐름: 행사 소개 → 상품별 설명 → 상담 포인트/선택 팁 → 방문/문의 안내

다음 JSON 형식으로만 출력해 (다른 텍스트 없이):
{{
  "titles": [
    "블로그 제목 후보 1 (SEO 키워드 포함)",
    "블로그 제목 후보 2",
    "블로그 제목 후보 3"
  ],
  "body": "블로그 본문 전체 ({target_length}자 내외, 소제목은 '## ' 형식 사용 가능)",
  "cta": "글 마지막 또는 댓글에 사용할 상담 유도 한두 문장"
}}

입력 데이터:
{_json_block(user_payload)}
"""

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": user.strip()},
    ]
