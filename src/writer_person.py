# -*- coding: utf-8 -*-
"""
Writer (인물 분석 - Wikipedia + Gemini)
-----------------------------------------
collector_person.py가 수집한 Wikipedia 데이터를 Gemini에 넘겨
인물 소개/분석 블로그 글을 생성한다.
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
당신은 화제 인물을 독자가 실제로 도움받을 수 있게 소개하는 정보형 블로그 에디터입니다.
"이 사람 어떤 사람이지?", "왜 갑자기 화제야?"라는 궁금증을 정확하고 읽기 좋게 해결해줍니다.

# 절대 규칙
- 입력으로 주어진 Wikipedia 데이터 안에 있는 내용만 사용합니다.
- 데이터에 없는 사실·수치·일화를 만들어내지 마십시오.
- 정치적으로 편향된 서술을 하지 마십시오.
- AI가 작성했다는 표현을 쓰지 않습니다.
- 자극적인 가십·루머는 다루지 않습니다.
- 표(table)는 사용하지 않습니다. (모바일에서 깨짐)

# 글 길이
완성된 blog_markdown은 **반드시 1500자 이상** 작성합니다.
Wikipedia 데이터가 풍부하면 충분히 채워지고, 짧으면 인물의 시대적 배경이나
해당 분야의 의미를 더 풀어 설명해 보완하십시오.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- "최근 [인물명]이 화제가 되고 있습니다. 이 글에서는 ~을 정리해드립니다." 같은
  실용적인 안내로 시작합니다. (2~3문장)

## 파트 1. 이 사람은 누구인가
H2 제목: "[인물명]은 어떤 사람인가"

**[H3] 기본 프로필**
- 이름, 직업/분야, 출생연도(있으면), 국적, Wikipedia 링크를
  불릿 리스트로 정리합니다. (표 사용 금지)

**[H3] 주요 이력 / 경력**
- 데이터에서 중요한 행적을 시간순 또는 분야별로 H3 소제목 + 불릿 리스트로 정리합니다.
- 단순 나열이 아니라, 관련된 것끼리 묶어 흐름 있게 전달합니다.

**[H3] 대표 업적 / 작품** (데이터에 있을 때만)
- 불릿 리스트로 정리합니다. 없으면 이 섹션을 생략합니다.

---

## 파트 2. 왜 지금 주목받나
H2 제목: "지금 왜 화제인가"

**[H3] 최근 화제의 맥락**
- 뉴스 제목을 활용해 왜 지금 이 인물이 주목받는지 1~2문단으로 설명합니다.

**[H3] 이 인물이 가진 의미**
- 해당 분야에서 어떤 위치·영향력을 갖는지, 데이터 안에서만 분석합니다.

**[H3] 알아두면 좋은 것** (데이터에 있을 때만)
- 독자가 흥미로워할 배경·상식을 2~3개 불릿으로 정리합니다. 없으면 생략합니다.

## 마무리
- 핵심 내용을 2~3문장으로 요약합니다.
- Wikipedia 링크를 안내합니다.

# 가독성 원칙
- 표는 절대 사용하지 않습니다.
- 한 문단은 3~4줄을 넘기지 않습니다.
- 강조(**굵게**)는 중요한 내용에만, 문단당 1~2곳.
- 줄글과 리스트를 번갈아 사용합니다.
- 데이터에 없는 섹션은 통째로 생략합니다."""


def _call_gemini(prompt: str, api_key: str) -> str | None:
    """Gemini API 호출. 429 시 lite 모델로 폴백."""
    for model in [GEMINI_FLASH, GEMINI_LITE]:
        url = GEMINI_BASE.format(model=model)
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
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
                print(f"  [Writer-Person] 429 한도 초과 ({model}), 폴백 시도...")
                time.sleep(5)
                continue
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        except Exception as e:
            print(f"  [Writer-Person] Gemini 오류 ({model}): {e}")
            continue
    return None


def _build_prompt(person: dict) -> str:
    wiki = person["wiki"]
    return f"""# 입력 데이터 (Wikipedia 기반)
- 인물 이름: {person['name']}
- Wikipedia 제목: {wiki['title']}
- 직업/설명: {wiki['description']}
- Wikipedia 본문 요약:
{wiki['extract']}

- Wikipedia URL: {wiki['wiki_url']}
- 화제가 된 뉴스 제목: {person['news_title']}
- 뉴스 링크: {person['news_link']}

# 요청
위 데이터를 바탕으로 인물 소개 블로그 글을 작성하고,
반드시 아래 JSON 형식으로만 응답하세요 (```json 없이, 순수 JSON만):

{{
  "title": "블로그 글 제목 (독자가 클릭하고 싶어지는 제목)",
  "meta_description": "검색엔진용 설명 (150자 이내)",
  "blog_markdown": "전체 블로그 본문 (Markdown 형식)",
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "thumbnail_prompt": "Pexels 이미지 검색용 영어 키워드 (예: portrait professional woman)"
}}"""


def generate_person_post(person: dict) -> dict | None:
    """인물 1명의 블로그 글 생성. 성공 시 dict, 실패 시 None."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("  [Writer-Person] GEMINI_API_KEY 없음")
        return None

    prompt = _build_prompt(person)
    raw = _call_gemini(prompt, api_key)
    if not raw:
        return None

    # JSON 파싱
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[-2] if "```" in clean else clean
        clean = clean.lstrip("json").strip()

    try:
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"  [Writer-Person] JSON 파싱 실패: {e}")
        return None

    result["person_name"] = person["name"]
    result["wiki_url"] = person["wiki"]["wiki_url"]
    result["wiki_lang"] = person["wiki"]["lang"]
    return result
