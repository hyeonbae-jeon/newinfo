# -*- coding: utf-8 -*-
"""
Writer (여행 코스 - Gemini)
-----------------------------
Wikipedia 수집 데이터 + 여행 조건(일정/테마/예산)을 Gemini에 넘겨
애드센스 승인 기준에 맞는 여행 코스 블로그 글을 생성한다.
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
당신은 실제 여행 경험을 바탕으로 독자가 바로 참고할 수 있는 여행 코스 블로그 글을
작성하는 에디터입니다. 입력된 Wikipedia 데이터와 여행 조건을 바탕으로
실용적이고 읽기 좋은 여행 가이드를 작성합니다.

# 절대 규칙
- 입력된 Wikipedia 데이터와 조건 안에 있는 내용만 사용합니다.
- 없는 식당명, 숙소명, 가격을 구체적으로 만들어내지 마십시오.
  (예: "○○ 호텔"처럼 특정 업체명을 지어내지 말고 "중급 호텔 기준" 식으로 표현)
- AI가 작성했다는 표현을 쓰지 않습니다.
- 표(table)는 사용하지 않습니다. (모바일에서 깨짐)
- 과장된 광고성 문구를 쓰지 않습니다.

# 글 길이
완성된 blog_markdown은 **반드시 2000자 이상** 작성합니다.
여행 코스 글은 일정별로 충분히 풀어써야 독자에게 실질적인 도움이 됩니다.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- "○○ 여행을 계획 중이라면 이 글 하나로 코스를 잡을 수 있습니다." 같은
  실용적인 안내로 시작합니다.
- 이 글에서 다룰 내용(일정, 테마, 예산대)을 2~3줄로 요약합니다.
- 여행지 기본 소개를 2~3문단으로 씁니다. (Wikipedia extract 활용)

## H2: 여행 전 알아두면 좋은 것
- 여행지의 기후·베스트 시즌을 1~2문장으로 씁니다.
- 이동 수단, 언어, 화폐, 시차 등 실용 정보를 불릿 리스트로 정리합니다.
  (Wikipedia 데이터 기반, 없는 내용은 생략)

## H2: [일정]일 코스 — 테마 중심으로
일정(duration)에 맞게 Day별로 H3 섹션을 나눕니다.

각 Day 구성:
  **[H3] Day N — 이날의 핵심 키워드**
  - 오전 / 오후 / 저녁으로 나눠 장소와 활동을 줄글 + 불릿으로 씁니다.
  - 각 장소마다 "왜 가면 좋은지" 1~2문장을 꼭 씁니다.
  - 이동 방법(도보/지하철/버스 등)을 간단히 언급합니다.
  - 구체적인 식당명은 지어내지 말고 "현지 시장 먹거리", "골목 카페" 식으로 표현합니다.

## H2: 예산 가이드 ({budget} 기준)
- 숙소 / 식비 / 교통 / 입장료로 나눠 불릿 리스트로 정리합니다.
- 구체적인 금액보다 "1박 기준 중급 호텔 약 XX~XX만원대" 식의 범위로 표현합니다.
- {budget}이 "저렴하게"면 절약 팁, "프리미엄"이면 고급 옵션을 위주로 씁니다.

## H2: 이런 분께 추천하는 코스예요
- 이 코스가 맞는 여행자 유형을 불릿 3~4개로 씁니다.
- 맞지 않는 유형도 1~2개 솔직하게 씁니다. (신뢰도 향상)

## H2: 여행 준비 체크리스트
- 출발 전 챙겨야 할 것들을 체크리스트(- [ ] 항목) 형식으로 씁니다.
- 비자, 환전, 교통카드, 유심/포켓와이파이, 여행자보험 등
  여행지 특성에 맞게 구성합니다.

## 마무리
- 이 코스의 핵심을 2~3문장으로 정리합니다.
- Wikipedia 출처 링크를 아래 형식으로 표기합니다:
  > 참고: [Wikipedia - {destination}]({wiki_url})

# 가독성 원칙
- 표는 절대 사용하지 않습니다.
- 한 문단은 3~4줄을 넘기지 않습니다.
- 강조(**굵게**)는 장소명, 핵심 팁에만, 문단당 1~2곳.
- 줄글과 리스트를 번갈아 사용합니다.
- Day별 섹션은 충분히 길게 — 각 Day마다 최소 200자 이상 씁니다."""


def _call_gemini(prompt: str, api_key: str) -> str | None:
    for model in [GEMINI_FLASH, GEMINI_LITE]:
        url = GEMINI_BASE.format(model=model)
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 6000,
                "responseMimeType": "application/json",
            },
        }
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=body,
                timeout=90,
            )
            if r.status_code == 429:
                print(f"  [Writer-Travel] 429 한도 초과 ({model}), 폴백 시도...")
                time.sleep(5)
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"  [Writer-Travel] Gemini 오류 ({model}): {e}")
            continue
    return None


def build_prompt(item: dict, wiki: dict) -> str:
    destination = item.get("destination", "")
    duration = item.get("duration", "")
    theme = item.get("theme", "")
    budget = item.get("budget", "중간")

    # 일정 숫자 파싱 (예: "2박3일" → days=3, nights=2)
    import re
    nights = re.search(r"(\d+)박", duration)
    days = re.search(r"(\d+)일", duration)
    nights_n = int(nights.group(1)) if nights else 1
    days_n = int(days.group(1)) if days else nights_n + 1

    return f"""# 여행 조건
- 여행지: {destination}
- 일정: {duration} ({nights_n}박 {days_n}일, Day 1~{days_n}로 구성)
- 테마: {theme}
- 예산: {budget}

# Wikipedia 수집 데이터
- 여행지 설명: {wiki.get('description', '')}
- Wikipedia 요약:
{wiki.get('extract', '')}

- 추가 본문 (관광지·명소 정보):
{wiki.get('full_text', '')}

- Wikipedia URL: {wiki.get('wiki_url', '')}

# 요청
위 데이터와 여행 조건을 바탕으로 여행 코스 블로그 글을 작성하고,
반드시 아래 JSON 형식으로만 응답하세요 (순수 JSON, ``` 없이):

{{
  "title": "블로그 글 제목 (예: 오사카 2박3일 코스 — 맛집·쇼핑 완전 정복)",
  "seo_title": "검색엔진 최적화 제목 (60자 이내)",
  "meta_description": "검색엔진용 설명 (150자 이내)",
  "slug": "url-friendly-slug",
  "blog_markdown": "전체 블로그 본문 (Markdown, 2000자 이상)",
  "keywords": ["키워드1", "키워드2", "...10개"],
  "tags": ["태그1", "태그2", "...10개"],
  "thumbnail_prompt": "Pexels 썸네일 검색용 영어 키워드",
  "image_prompts": ["Day1용 영어 키워드", "Day2용 영어 키워드", "마무리용 영어 키워드"],
  "sns_text": "SNS 공유용 짧은 문구 (100자 이내)"
}}"""


def generate_travel_post(item: dict, wiki: dict) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("  [Writer-Travel] GEMINI_API_KEY 없음")
        return None

    prompt = build_prompt(item, wiki)
    raw = _call_gemini(prompt, api_key)
    if not raw:
        return None

    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"  [Writer-Travel] JSON 파싱 실패: {e}")
        return None

    result["destination"] = item.get("destination", "")
    result["duration"] = item.get("duration", "")
    result["wiki_url"] = wiki.get("wiki_url", "")
    return result
