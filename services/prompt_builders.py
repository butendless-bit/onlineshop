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
당신은 프리미엄 가전 매장의 인스타그램 SNS 카피라이터입니다.
"광고 같지 않은 광고"를 쓰는 것이 핵심 원칙입니다.
진짜 사람이 직접 경험하고 솔직하게 추천하는 느낌으로 작성합니다.
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
【도입부】
- 공감 또는 현장 묘사로 시작. 절대 제품명/브랜드로 시작하지 말 것
- 예) '솔직히 이게 이렇게 달라질 줄 몰랐어요' / '집에서 보내는 시간이 달라지면 기분도 달라지더라고요'
- 고객이 스크롤을 멈추게 만드는 생활형 훅

【본문】
- 스펙 나열 금지. 고객이 실제로 느낄 변화와 경험으로 풀어쓸 것
  나쁜 예) '1600rpm 고속탈수, 에너지 A등급'
  좋은 예) '세탁 끝나고 꺼냈을 때 옷에서 나던 퀴퀴한 냄새가 없어요. 진짜로요.'
- 상품의 장점은 실제 상세페이지 정보에 근거해서 생활 맥락 중심으로
- 상품 여러 개면 번호 매기지 말고 한 흐름으로 자연스럽게 묶을 것

【금지 표현】
- '최고!', '무조건', '지금 안 사면 손해' 등 과한 표현 금지
- '~드립니다', '~하십시오' 같은 딱딱한 존댓말 금지
- 광고성 강조 표현: '혁신적인', '놀라운', '완벽한' 등 금지

【마무리 CTA】
- 방문·문의를 판매 냄새 없이 자연스럽게 유도
- 예) '광복롯데몰 하이마트에 오시면 직접 만져보실 수 있어요 :)'
- caption 전체 길이는 15줄 이내

【이모지 활용 규칙】
- 각 문장/줄 앞에 내용에 맞는 이모지를 붙여서 시각적으로 읽기 쉽게 구성
  ✨ 도입/공감  🏠 생활경험  ❄️ 냉장고  🧺 세탁기  📺 TV  💨 에어컨  🍳 주방가전
  💡 혜택/가격  🛍️ 행사안내  📍 매장위치  💬 문의/CTA  🤍 감성포인트
- 같은 이모지 반복 금지, 줄마다 다른 이모지 선택
- 해시태그 줄은 이모지 없이

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
당신은 프리미엄 가전 매장의 네이버 블로그 전문 에디터입니다.
"전문성 있고 신뢰감 있는 사람이 직접 경험하고 쓴 글" 느낌이 핵심 원칙입니다.
오래 써본 사람의 솔직한 리뷰, 가전에 밝은 매장 담당자의 진심 추천 느낌으로 작성합니다.
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
【톤과 문체】
- 전체 분량: 공백 포함 약 {target_length}자 내외
- '전문성 있는 사람이 직접 경험하고 쓴 글' 느낌. 친한 친구 ❌ → 믿을 수 있는 전문가 추천 ✅
- 경험 기반 신뢰 표현 사용: '직접 확인해보니', '써보고 나서야 알게 된 것들', '솔직히 말하면'
- 차분한 관찰 문체: '~더라고요', '~는 점이 인상적이었어요', '~가 다른 제품과 달랐던 건'

【필수 포함 요소】
- 단점/아쉬운 점 1개 이상 반드시 포함 (신뢰도 상승에 결정적)
  예) '이 부분은 아쉬웠는데요' / '가격이 좀 있는 건 사실이에요'
- 도입부: 절대 제품명으로 시작하지 말 것. 공감 또는 현장 묘사로
  예) '프리미엄 세탁기를 고민하다 보면 결국 이 브랜드 얘기가 나옵니다.'
- 소제목(## 형식): 3~4개, 키워드 자연 포함, 클릭 유도형
  나쁜 예) '## 제품 특징'  좋은 예) '## 직접 써보니까 달랐던 점'
- 마무리: '이런 분께 추천한다' 형식으로 자연스럽게

【금지 사항】
- AI 번역체: '~할 수 있습니다', '다양한 기능을 제공합니다', '효율적인', '혁신적인' 금지
- 어색한 존댓말: '~드립니다', '~하시기 바랍니다' 금지
- '최고', '무조건', '안 사면 손해' 같은 과장 표현 금지
- 마크다운 번호 목록·표·해시태그 쓰지 말 것 (## 소제목만 허용)
- 스펙 나열 금지 → 반드시 경험·생활 맥락으로 번역

【문단 흐름】
도입부(공감) → ## 소제목1(상품 경험) → ## 소제목2(차별점/심화) → ## 소제목3(실용 정보/가격) → 마무리(추천 대상)

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
