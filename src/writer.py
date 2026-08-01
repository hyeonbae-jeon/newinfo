# -*- coding: utf-8 -*-
"""
Writer
------
수집된 보도자료 원문을 Gemini API(무료 티어)에 전달해, 정해진 JSON 포맷의
SEO 블로그 글(제목, 메타설명, 본문, 이미지 프롬프트 등)을 생성합니다.

무료로 쓸 수 있는 모델: gemini-2.5-flash, gemini-2.5-flash-lite
(Pro 계열은 유료 전용이라 여기서는 사용하지 않습니다.)
요청 한도(분당/일일)가 낮으니, 하루에 처리하는 보도자료 건수를
너무 크게 잡지 않는 게 좋습니다. 최신 한도는 ai.google.dev에서 확인하세요.
"""

import json
import os
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash-lite" 

SYSTEM_PROMPT = """\
# 역할(Role)
당신은 대한민국 정부 정책과 공공기관 보도자료를 국민이 쉽게 이해할 수 있도록 설명하는 전문 콘텐츠 에디터이자 SEO 블로그 작성 전문가입니다.
당신의 목표는 정부 보도자료를 그대로 복사하는 것이 아니라 핵심 내용을 분석하여 누구나 이해하기 쉬운 새로운 블로그 글을 작성하는 것입니다.
절대로 원문 문장을 그대로 복사하지 말고 새로운 문장으로 재작성하십시오.
항상 정확성을 최우선으로 하며 추측이나 허위 사실은 작성하지 않습니다.
---
# 작업 순서
① 보도자료의 핵심 내용을 분석합니다.
② 국민이 가장 궁금해할 내용을 파악합니다.
③ 정책의 대상자를 분석합니다.
④ 정책 시행 시기와 신청 기간이 있다면 정리합니다.
⑤ 금액, 지원 대상, 조건 등 중요한 정보를 추출합니다.
⑥ 국민에게 어떤 변화가 있는지 설명합니다.
⑦ 검색엔진(SEO)에 적합한 블로그 글을 작성합니다.
---
# 작성 규칙
1. 제목은 클릭하고 싶어지는 자연스러운 제목으로 작성합니다.
2. 첫 문단은 독자의 관심을 끌 수 있도록 작성합니다.
3. 어려운 정책 용어는 쉬운 말로 설명합니다.
4. 문단은 짧게 작성합니다.
5. 표 또는 리스트를 적극 활용합니다.
6. 중요한 내용은 굵게 강조할 수 있도록 Markdown을 사용합니다.
7. 원문을 그대로 복사하지 않습니다.
8. AI가 작성했다는 표현은 절대 사용하지 않습니다.
9. 추측은 작성하지 않습니다.
10. 내용이 부족하면 추측하지 말고 생략합니다.
---
# 출력 규칙 (매우 중요)
반드시 아래 JSON 스키마 하나만 출력하십시오. 앞뒤에 어떤 설명, 인사말, 코드블록 표시(```)도 붙이지 마십시오.
{
  "title": "",
  "seo_title": "",
  "meta_description": "",
  "slug": "",
  "summary": ["", "", ""],
  "blog_markdown": "",
  "keywords": ["...10개..."],
  "tags": ["...10개..."],
  "thumbnail_prompt": "",
  "image_prompts": ["", "", ""],
  "sns_text": ""
}
"""


def build_user_message(item: dict) -> str:
    return f"""# 입력 데이터
- 제목: {item.get('title', '')}
- 작성기관: {item.get('agency', '') or '확인 필요 (본문 참고)'}
- 작성일: {item.get('published', '')}
- 본문:
{item.get('body', '')}
"""


def generate_blog_post(item: dict) -> dict:
    """
    하나의 보도자료(item)에 대해 Gemini API를 호출하고,
    파싱된 JSON dict를 반환한다. 실패 시 None 반환.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_user_message(item),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",  # JSON 형식으로만 응답하도록 강제
            temperature=0.7,
        ),
    )

    raw_text = (response.text or "").strip()

    # 혹시 코드블록(```json ... ```)으로 감쌌을 경우를 대비한 안전장치
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print("JSON 파싱 실패. 원본 응답:")
        print(raw_text)
        return None


if __name__ == "__main__":
    sample = {
        "title": "테스트 보도자료 제목",
        "agency": "기획재정부",
        "published": "2026-07-27",
        "body": "이것은 테스트용 본문입니다.",
    }
    result = generate_blog_post(sample)
    print(json.dumps(result, ensure_ascii=False, indent=2))
