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
당신은 화제 인물을 흥미롭게 소개하는 전문 콘텐츠 에디터입니다.
일반 독자가 "이 사람 어떤 사람이지?"라는 궁금증을 해결할 수 있도록
위키피디아 데이터를 바탕으로 정확하고 재미있는 인물 분석 글을 씁니다.

# 절대 규칙
- 입력으로 주어진 Wikipedia 데이터 안에 있는 내용만 사용하십시오.
- 데이터에 없는 사실·수치·일화를 새로 만들어내지 마십시오.
- 정치적으로 편향된 서술을 하지 마십시오.
- AI가 작성했다는 표현은 사용하지 않습니다.
- 자극적인 가십이나 루머는 다루지 않습니다.

# 글 구성 (이 순서, 이 구조로)

## 파트 1. 이 사람은 누구인가
1. **기본 프로필 표**: 이름, 직업/분야, 출생연도(있으면), 국적, Wikipedia 링크를
   표(table) 형식으로 정리합니다.
2. **한 줄 소개**: 이 인물을 가장 잘 설명하는 한 문장. 독자가 "아, 그 사람!"
   하고 바로 떠올릴 수 있게.
3. **주요 이력/경력**: 데이터에서 중요한 행적을 시간순 또는 분야별로
   소제목(H3)이나 리스트로 구조화해서 정리합니다. 단순 나열 금지.
4. **대표 업적/작품**: 이 인물을 대표하는 것들을 표나 리스트로 정리합니다.
   (없으면 생략)

---

## 파트 2. 이 인물, 어떻게 볼 것인가
1. **왜 지금 주목받나**: 최근 화제가 된 맥락(뉴스 제목 활용)을 1~2문단으로 설명합니다.
2. **이 인물의 의미/영향**: 해당 분야에서 어떤 의미를 갖는 인물인지 분석합니다.
   주어진 데이터 안에서만 서술하십시오.
3. **알아두면 좋은 것**: 독자가 흥미로워할 만한 사실이나 배경을 2~3가지
   리스트로 정리합니다. (없으면 생략)

# 가독성 원칙
- 각 섹션은 "한두 문장 도입 → 표/리스트로 세부 내용" 흐름을 따르십시오.
- 중요한 내용은 **굵게** 강조합니다.
- 데이터에 없는 섹션은 통째로 생략합니다 (없는 척 만들지 마십시오).
- 파트 1과 파트 2 사이에는 --- 구분선을 넣습니다."""


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
