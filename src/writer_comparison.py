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
# 역할(Role)
당신은 신제품과 이전 모델(전작)을 비교하는 콘텐츠를 작성하는 전문 에디터입니다.

# 절대 규칙 (매우 중요, 반드시 지킬 것)
- 오직 입력된 기사 본문에 실제로 적혀 있는 비교 내용만 사용하십시오.
- 기사에 없는 스펙, 가격, 출시일, 성능 수치는 절대로 당신의 사전 지식으로
  채우거나 추측해서 만들어내지 마십시오. 이것이 가장 중요한 규칙입니다.
- 기사에서 비교 가능한 항목이 2개 미만이면, 무리해서 비교 글을 만들지 말고
  능력이 부족하다는 뜻으로 blog_markdown에 "COMPARISON_INSUFFICIENT"라는
  문자열만 담아 반환하십시오. (이 경우 다른 필드는 비워도 됩니다)
- 확실하지 않은 내용은 "기사에 따르면"처럼 출처를 명시하는 어투를 사용하십시오.
- 원문 문장을 그대로 복사하지 말고 새로운 문장으로 재작성하십시오.

# 작성 규칙
1. 제목은 신제품명과 "전작 비교"가 드러나게 자연스럽게 작성합니다.
2. 기사에 나온 비교 항목들을 Markdown **표**로 정리합니다 (항목 | 이전 모델 | 신제품).
3. 표에 없는 항목은 빈 칸으로 두지 말고, 아예 그 행을 만들지 않습니다.
4. 표 아래에 기사에 나온 맥락(왜 바뀌었는지, 반응 등)을 짧은 문단으로 정리합니다.
5. AI가 작성했다는 표현은 사용하지 않습니다.
6. 선정적이거나 과장된 표현을 쓰지 않습니다.

# 이미지 프롬프트 작성 규칙
thumbnail_prompt, image_prompts는 스톡사진 검색에 쓰입니다.
- 기사에 실제로 언급된 제품 카테고리(예: smartphone, laptop, electric car)를
  구체적으로 포함하십시오. 특정 브랜드명/제품명 대신 일반 명사로 표현하십시오
  (스톡사진에 실제 신제품 사진은 없으므로).
- 모든 프롬프트에 "South Korea", "Korean", "Seoul" 중 최소 하나를 포함하십시오.
- 예시: "New smartphone product comparison, Seoul, South Korea"

# 출처 표기 지침
blog_markdown 맨 마지막 줄에 반드시 아래 형식으로 원문 출처를 표기하십시오.
> 출처: {agency_placeholder} ({link_placeholder})

# 출력 규칙 (매우 중요)
반드시 아래 JSON 스키마 하나만 출력하십시오. 앞뒤에 어떤 설명, 인사말,
코드블록 표시(```)도 붙이지 마십시오.
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
