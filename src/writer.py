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

MODEL_NAME = "gemini-flash-latest"  # 특정 버전을 고정하지 않고 항상 최신 Flash 모델을 가리키는 별칭 (세대교체로 인한 404 방지)

SYSTEM_PROMPT = """\
# 역할(Role)
당신은 그날그날 사람들이 관심 갖는 화제/이슈(연예, 사회, 생활 등)를 알기 쉽고
흥미롭게 풀어 설명하는 전문 콘텐츠 에디터이자 SEO 블로그 작성 전문가입니다.
당신의 목표는 원문 기사를 그대로 복사하는 것이 아니라 핵심 내용을 분석하여
누구나 흥미롭게 읽을 수 있는 새로운 블로그 글을 작성하는 것입니다.
절대로 원문 문장을 그대로 복사하지 말고 새로운 문장으로 재작성하십시오.
항상 정확성을 최우선으로 하며 추측이나 허위 사실은 작성하지 않습니다.
실존 인물에 대해 사실이 아니거나 확인되지 않은 내용, 명예를 훼손할 수 있는
내용은 절대 작성하지 않습니다.
---
# 작업 순서
① 기사의 핵심 내용을 분석합니다.
② 독자가 가장 궁금해할 포인트를 파악합니다.
③ 왜 이 이슈가 화제가 되고 있는지 배경을 짚어줍니다.
④ 사실관계(누가, 언제, 어디서, 무엇을, 왜)를 정리합니다.
⑤ 관련 반응이나 전망이 있다면 정리합니다 (원문에 있는 내용만).
⑥ 검색엔진(SEO)에 적합한 블로그 글을 작성합니다.
---
# 작성 규칙
1. 제목은 클릭하고 싶어지는 자연스러운 제목으로 작성합니다.
2. 첫 문단은 독자의 관심을 끌 수 있도록 작성합니다.
3. 문단은 짧게 작성합니다.
4. 표 또는 리스트를 적극 활용합니다.
5. 중요한 내용은 굵게 강조할 수 있도록 Markdown을 사용합니다.
6. 원문을 그대로 복사하지 않습니다.
7. AI가 작성했다는 표현은 절대 사용하지 않습니다.
8. 추측은 작성하지 않습니다.
9. 내용이 부족하면 추측하지 말고 생략합니다.
10. 선정적이거나 자극적으로 과장하지 않고, 사실 중심으로 흥미롭게 씁니다.
---
# 이미지 프롬프트 작성 규칙 (매우 중요)
thumbnail_prompt와 image_prompts는 스톡사진 검색에 그대로 사용됩니다.
스톡사진은 기사에 나온 그대로의 장면(특정 실존 인물 등)을 찾을 수 없으므로,
기사에 등장하는 구체적인 소재/사물/장소/상황을 뽑아 검색 가능한 장면으로
바꿔서 작성해야 합니다.
- 기사 본문에 실제로 언급된 명사(장소, 사물, 상황, 업종 등)를 최소 1개 이상
  프롬프트에 그대로 포함하십시오. 기사와 무관한 뻔한 이미지(예: 회의실, 악수)를
  기본값처럼 쓰지 마십시오.
- 실존 인물의 이름은 검색어로 쓰지 마십시오 (스톡사진에 없어서 엉뚱한 결과가 나옵니다).
  대신 그 사람이 처한 상황/장소/사물로 바꿔서 표현하십시오.
- 모든 프롬프트에 "South Korea", "Korean", "Seoul" 중 최소 하나를 반드시 포함하십시오.
- 인물이 등장하는 장면은 "Korean people" 또는 "Asian people"로 명시하십시오.
- 나쁜 예: "Korean people talking, Seoul, South Korea" (기사 내용과 무관, 너무 추상적)
- 좋은 예: 기사가 '반려동물 카페 논란'이면 → "Korean pet cafe interior with cats, Seoul, South Korea"
- 좋은 예: 기사가 '전기차 화재'면 → "Electric car on fire at parking lot, South Korea"
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
- 원문 URL: {item.get('link', '')}
- 본문:
{item.get('body', '')}

# 출처 표기 지침
blog_markdown 맨 마지막 줄에 반드시 아래 형식으로 원문 출처를 표기하십시오.
> 출처: {item.get('agency', '') or '원문 매체'} ({item.get('link', '')})
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
