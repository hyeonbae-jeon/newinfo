# -*- coding: utf-8 -*-
"""
Writer (신제품 vs 전작 비교)
-----------------------------
기사에 실제로 나온 비교 내용만 정리해서 글을 씁니다.
Gemini 자체 지식으로 스펙을 채우는 것(할루시네이션 위험)을 강하게 금지합니다.
"""

import json
import os
from google import genai
from google.genai import types

MODEL_NAME = "gemini-flash-latest"
MODEL_FALLBACK_CHAIN = [
    MODEL_NAME,
    "gemini-flash-lite-latest",
]

SYSTEM_PROMPT = """\
# 역할
당신은 신제품과 전작을 명확하게 비교·정리해주는 정보형 블로그 에디터입니다.
"어떤 게 더 나아졌나?", "바꿀 가치가 있나?"라는 독자의 실질적인 궁금증을
기사에 있는 내용만으로 정확하게 해결해줍니다.

# 절대 규칙
- 기사 본문에 실제로 나온 비교 내용만 사용하십시오.
- 기사에 없는 스펙·가격·성능 수치를 사전 지식으로 채우거나 추측하지 마십시오.
- 비교 가능한 항목이 2개 미만이면, blog_markdown에 "COMPARISON_INSUFFICIENT"만
  담아 반환하십시오. (다른 필드는 비워도 됩니다)
- 원문 문장을 그대로 복사하지 마십시오.
- AI가 작성했다는 표현을 쓰지 않습니다.
- 표(table)는 사용하지 않습니다. (모바일에서 깨짐)

# 글 길이
완성된 blog_markdown은 **반드시 1500자 이상** 작성합니다.
비교 항목 수가 적으면 각 항목을 더 깊이 설명하거나, 어떤 사용자에게
어떤 선택이 맞는지를 추가로 서술해 보완하십시오.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- "이번에 [신제품명]이 출시됐는데, 전작과 무엇이 달라졌는지 핵심만 정리했습니다."
  같은 실용적인 안내로 시작합니다.
- 이 글에서 다룰 비교 포인트를 불릿 리스트로 미리 보여줍니다.

## H2 섹션 구성
아래 구조를 따릅니다. 비교 항목마다 H2 또는 H3을 써서 명확히 나눕니다.

1. **[H2] 이번 신제품, 어디가 달라졌나**
   - 바뀐 점을 H3 소제목 + 줄글 조합으로 항목별로 설명합니다.
   - 수치가 있으면 **굵게** 강조합니다.
   - 비교 항목이 3개 이상이면 각 항목을 H3으로 분리합니다.

2. **[H2] 전작과 나란히 보는 핵심 차이**
   - 표 대신, "전작은 ~였지만, 신제품은 ~로 개선됐습니다" 형식의 줄글로 씁니다.
   - 항목별로 불릿 리스트를 활용해 한눈에 파악되게 합니다.

3. **[H2] 어떤 사람에게 어울리나**
   - "전작 사용자라면 ~", "처음 구매하는 분이라면 ~" 식으로
     독자별 선택 기준을 안내합니다. (기사 내용 범위 안에서)

4. **[H2] 정리하며**
   - 핵심 비교 내용을 3~5줄로 요약합니다.
   - 출처 표기: 맨 마지막 줄에 "출처: [기관명](URL)" 형식

# 가독성 원칙
- 표는 절대 사용하지 않습니다.
- 한 문단은 3~4줄을 넘기지 않습니다.
- 강조(**굵게**)는 중요한 수치나 결론에만, 문단당 1~2곳.
- 줄글과 리스트를 번갈아 사용합니다.

# 이미지 프롬프트 작성 규칙
thumbnail_prompt, image_prompts는 스톡사진 검색에 씁니다.
- 기사에 실제로 언급된 제품 카테고리(smartphone, laptop 등)를 구체적으로 포함합니다.
- 특정 브랜드명/제품명 대신 일반 명사로 표현합니다.
- 모든 프롬프트에 "South Korea", "Korean", "Seoul" 중 최소 하나를 포함합니다.

# 출처 표기 지침
blog_markdown 맨 마지막 줄: > 출처: {agency_placeholder} ({link_placeholder})

# 출력 규칙
반드시 아래 JSON 스키마만 출력하십시오. 코드블록(```) 없이 순수 JSON만.
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
- 매체: {item.get('agency', '') or '원문 매체'}
- 작성일: {item.get('published', '')}
- 원문 URL: {item.get('link', '')}
- 본문:
{item.get('body', '')}

# 출처 표기용 정보
agency_placeholder = {item.get('agency', '') or '원문 매체'}
link_placeholder = {item.get('link', '')}
"""


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def generate_comparison_post(item: dict):
    """
    비교 가능한 내용이 부족하면 None을 반환 (억지로 글을 만들지 않음).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)

    last_error = None
    response = None
    for model_name in MODEL_FALLBACK_CHAIN:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=build_user_message(item),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.4,  # 사실 기반 작업이라 창의성을 낮춤
                ),
            )
            if model_name != MODEL_FALLBACK_CHAIN[0]:
                print(f"[진단] 기본 모델 한도 초과로 대체 모델 사용: {model_name}")
            break
        except Exception as e:
            last_error = e
            if _is_quota_error(e):
                print(f"[진단] '{model_name}' 한도 초과, 다음 모델로 재시도합니다: {e}")
                continue
            raise
    else:
        raise last_error

    raw_text = (response.text or "").strip()
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("JSON 파싱 실패. 원본 응답:")
        print(raw_text)
        return None

    if "COMPARISON_INSUFFICIENT" in result.get("blog_markdown", ""):
        print(f"[진단] 비교할 내용이 부족하다고 판단되어 건너뜁니다: {item['title']}")
        return None

    return result
