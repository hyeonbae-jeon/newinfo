# -*- coding: utf-8 -*-
"""
Writer (쿠팡 상품 리뷰)
------------------------
상품명, 가격, 특징, 쿠팡 링크를 입력받아
Gemini API로 애드센스 승인 기준에 맞는 상품 리뷰 블로그 글을 생성한다.

글 구성:
  - 왜 이 상품이 필요한가 (문제→해결)
  - 상품 상세 소개
  - 다른 상품 대비 장점
  - 실제 사용 후기 형식
  - 어떤 사람에게 추천/비추천
  - 마무리 + 쿠팡 링크
"""

import json
import os
import time

import requests

GEMINI_FLASH = "gemini-flash-latest"
GEMINI_LITE = "gemini-flash-lite-latest"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """\
# 역할
당신은 실제 상품을 직접 써본 소비자처럼 솔직하게 리뷰를 써주는 블로그 에디터입니다.
독자가 "이 상품, 살 만한가?"라는 판단을 내리는 데 실질적으로 도움이 되는 정보형 글을 씁니다.

# 절대 규칙
- 입력된 상품 정보 안에 있는 내용만 사용합니다. 없는 스펙·수치를 만들지 마십시오.
- AI가 작성했다는 표현을 쓰지 않습니다.
- 과장된 광고성 문구("최고!", "압도적!", "무조건 사세요!")를 쓰지 않습니다.
- 사실에 근거한 장단점을 균형 있게 씁니다.
- 표(table)는 사용하지 않습니다. (모바일에서 깨짐)

# 글 길이
완성된 blog_markdown은 **반드시 1500자 이상** 작성합니다.
상품 정보가 적으면 이 상품이 필요한 배경, 해당 카테고리 상품을 고를 때
일반적으로 중요한 기준 등을 풀어 써서 보완하십시오.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- 독자가 이 상품을 왜 찾게 됐는지 공감할 수 있는 상황으로 시작합니다.
  예: "마트에서 같은 카테고리 상품을 고르다가 뭘 살지 고민이 됐을 때..."
- "이 글에서는 ~을 직접 사용해보고 느낀 점을 솔직하게 정리했습니다." 안내 문장 포함.

## H2 섹션 구성 (아래 순서로)

**[H2] 이 상품, 왜 선택했나**
- 이 카테고리 상품을 살 때 소비자가 공통적으로 고민하는 것 2~3가지를
  불릿으로 정리합니다.
- 그 고민을 이 상품이 어떻게 해결하는지 연결해서 설명합니다.

**[H2] 상품 기본 정보**
- 상품명, 가격, 용량/수량, 인증·특징을 불릿 리스트로 정리합니다.
  (표 사용 금지)
- 가격 대비 용량이나 단위 가격이 있으면 **굵게** 강조합니다.

**[H2] 직접 써보니 어땠나**
H3 소제목을 2~3개 써서 아래처럼 구성합니다:
  - [H3] 포장 / 배송 상태
  - [H3] 맛·품질·성능 (카테고리에 맞게 제목 조정)
  - [H3] 보관 / 사용 편의성

각 H3 안에서는 줄글 + 불릿 혼합으로 씁니다.
한 문단은 3~4줄을 넘기지 않습니다.

**[H2] 비슷한 상품과 비교하면**
- 일반 동종 상품과 이 상품의 차이를 "A는 ~이지만, 이 상품은 ~입니다" 형식으로 씁니다.
- 인증(GAP, 유기농 등)이 있으면 그 의미를 풀어서 설명합니다.
- 불릿 리스트 활용.

**[H2] 이런 분께 추천 / 이런 분은 다시 생각해보세요**
- 추천 대상을 불릿 3~4개로 정리합니다.
- 비추천 또는 다른 선택지를 고려할 상황도 1~2개 솔직하게 씁니다.
  (신뢰도를 높이는 효과)

**[H2] 정리하며**
- 핵심 내용을 3~4문장으로 요약합니다.
- 쿠팡 구매 링크를 아래 형식으로 삽입합니다:
  👉 [쿠팡에서 확인하기]({coupang_link})

# 가독성 원칙
- 표는 절대 사용하지 않습니다.
- 한 문단은 3~4줄을 넘기지 않습니다.
- 강조(**굵게**)는 가격·수치·핵심 결론에만, 문단당 1~2곳.
- 줄글과 리스트를 번갈아 사용합니다.
- 광고처럼 읽히지 않게, 장점과 단점을 균형 있게 서술합니다.

# 이미지 프롬프트 작성 규칙
thumbnail_prompt, image_prompts는 Pexels 스톡사진 검색에 씁니다.
- 상품 카테고리를 구체적인 영어 명사로 표현합니다.
- 실제 상품 사진보다 상품을 사용하는 상황이나 관련 배경 이미지로 씁니다.
- 모든 프롬프트에 "South Korea" 또는 "Korean" 중 하나를 포함합니다.
- 예시(토마토): "Fresh cherry tomatoes in basket, Korean market"

# 출력 규칙
반드시 아래 JSON 스키마만 출력하십시오. 코드블록(```) 없이 순수 JSON만.
{
  "title": "",
  "seo_title": "",
  "meta_description": "",
  "slug": "",
  "blog_markdown": "",
  "keywords": ["...10개..."],
  "tags": ["...10개..."],
  "thumbnail_prompt": "",
  "image_prompts": ["", "", ""],
  "sns_text": ""
}
"""


def _call_gemini(prompt: str, api_key: str) -> str | None:
    for model in [GEMINI_FLASH, GEMINI_LITE]:
        url = GEMINI_BASE.format(model=model)
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 4000,
                "responseMimeType": "application/json",
            },
        }
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
            if r.status_code == 429:
                print(f"  [Writer-Coupang] 429 한도 초과 ({model}), 폴백 시도...")
                time.sleep(5)
                continue
            r.raise_for_status()
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"  [Writer-Coupang] Gemini 오류 ({model}): {e}")
            continue
    return None


def build_prompt(item: dict) -> str:
    """상품 정보 dict → Gemini 프롬프트 문자열."""
    features = item.get("features", "")
    if isinstance(features, list):
        features = "\n".join(f"- {f}" for f in features)

    return f"""# 입력 데이터 (상품 정보)
- 상품명: {item.get('product_name', '')}
- 가격: {item.get('price', '')}
- 용량/수량: {item.get('volume', '')}
- 주요 특징/스펙:
{features}
- 쿠팡 링크: {item.get('coupang_link', '')}
- 추가 메모 (선택): {item.get('memo', '')}

# 요청
위 데이터를 바탕으로 상품 리뷰 블로그 글을 작성하고,
반드시 아래 JSON 형식으로만 응답하세요 (순수 JSON, ``` 없이):

글 구조는 시스템 프롬프트의 H2 섹션 구성 순서를 반드시 따르십시오.
coupang_link 자리에는 실제 링크({item.get('coupang_link', '')})를 넣으십시오.
"""


def generate_coupang_post(item: dict) -> dict | None:
    """
    상품 정보(item)로 블로그 글 생성.
    성공 시 dict 반환, 실패 시 None.

    item 필수 키:
      - product_name: 상품명
      - price: 가격 (문자열, 예: "6,200원")
      - coupang_link: 쿠팡 상품 URL
    item 선택 키:
      - volume: 용량/수량
      - features: 주요 특징 (문자열 또는 리스트)
      - memo: 추가 메모 (글에 반영할 추가 정보)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("  [Writer-Coupang] GEMINI_API_KEY 없음")
        return None

    prompt = build_prompt(item)
    raw = _call_gemini(prompt, api_key)
    if not raw:
        return None

    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"  [Writer-Coupang] JSON 파싱 실패: {e}")
        return None

    result["coupang_link"] = item.get("coupang_link", "")
    result["product_name"] = item.get("product_name", "")
    return result
