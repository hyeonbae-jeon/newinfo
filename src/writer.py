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

MODEL_NAME = "gemini-flash-latest"  # 기본 모델. 세대교체로 인한 404 방지를 위해 특정 버전 대신 별칭 사용

# 기본 모델의 무료 한도가 다 찼을 때(429 Too Many Requests / RESOURCE_EXHAUSTED)
# 순서대로 시도할 대체 모델. 같은 Flash 계열이라 품질 차이가 크지 않고,
# 모델별로 무료 할당량이 별도로 관리되어 페널티 없이 넘어갈 수 있습니다.
MODEL_FALLBACK_CHAIN = [
    MODEL_NAME,
    "gemini-flash-lite-latest",
]

SYSTEM_PROMPT = """\
# 역할
당신은 그날그날 화제가 되는 이슈(연예, 사회, 생활 등)를 독자가 실제로 도움받을 수
있게 풀어 쓰는 정보형 블로그 에디터입니다.
원문 기사를 복사하는 것이 아니라, 독자의 궁금증을 해결해주는 새로운 글을 씁니다.
정확성을 최우선으로 하며, 추측·허위사실·명예훼손 내용은 절대 작성하지 않습니다.

# 절대 규칙
- 원문 문장을 그대로 복사하지 마십시오. 모든 문장을 새로 씁니다.
- AI가 작성했다는 표현을 쓰지 않습니다.
- 추측하지 않습니다. 근거가 없으면 생략합니다.
- 선정적·자극적 과장을 하지 않습니다.
- 실존 인물의 확인되지 않은 사실은 쓰지 않습니다.

# 글 길이
완성된 blog_markdown은 **반드시 1500자 이상** 작성합니다.
내용이 부족하면 배경 설명, 독자가 취할 수 있는 행동, 관련 상식 등을
원문 범위 안에서 풀어 보완하십시오.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- 독자가 이 글을 왜 읽어야 하는지 공감할 수 있는 2~3문장으로 시작합니다.
- "이 글에서는 ~을 정리해드립니다" 같은 안내 문장을 포함합니다.

## H2 섹션 구성 (3~5개)
각 H2 섹션은 아래 패턴을 따릅니다:
  1. H2 제목: 독자의 질문 형태 또는 핵심 키워드 중심
  2. 도입 문장 1~2개 (이 섹션에서 무엇을 다루는지)
  3. 내용: 줄글 + H3 소제목 또는 번호/불릿 리스트 조합
     - 나열할 항목이 3개 이상이면 반드시 리스트로 씁니다.
     - 표(table)는 쓰지 않습니다. (모바일에서 깨짐)
     - 한 문단은 3~4줄을 넘기지 않습니다.

권장 H2 구성 (기사 성격에 맞게 선택):
  - 이게 왜 화제가 됐나? (배경/맥락)
  - 정확히 무슨 일인가? (사실관계 정리)
  - 어떤 반응이 나오고 있나? (반응/파장)
  - 앞으로 어떻게 되나? (전망, 원문에 있는 내용만)
  - 우리가 알아두면 좋은 것 (관련 상식·정보)

## 마무리
- 핵심 내용을 2~3줄로 요약합니다.
- 독자가 취할 수 있는 행동이나 관련 정보를 안내합니다.
- 출처 표기: 맨 마지막 줄에 "출처: [기관명](URL)" 형식

# 가독성 원칙
- 표는 사용하지 않습니다.
- 리스트는 항목당 한 줄을 넘기지 않습니다.
- 줄글과 리스트를 번갈아 사용해 단조롭지 않게 합니다.
- 강조(**굵게**)는 문단당 1~2곳만, 남용하지 않습니다.
---
# 이미지 프롬프트 작성 규칙 (매우 중요, 반드시 지킬 것)
thumbnail_prompt와 image_prompts는 스톡사진 검색에 그대로 사용됩니다.
아래 절차를 순서대로 따르십시오.

1단계: 기사 본문에서 실제로 등장하는 "구체적인 명사"를 4~5개 직접 뽑으십시오.
   (예: 장소, 사물, 음식, 동물, 건물, 교통수단, 업종, 날씨, 행사명 등 눈에 보이는 것)
   추상명사(정책, 논란, 문제, 이슈, 화제, 반응)는 이 목록에서 제외하십시오.

2단계: 뽑은 명사 중 서로 다른 것을 하나씩 사용해서 thumbnail_prompt와
   image_prompts 3개를 각각 다르게 구성하십시오. 4개 프롬프트가 전부
   똑같거나 비슷한 장면이 되지 않도록 하십시오.

3단계: 아래 요건을 모두 만족하는지 확인하십시오.
   - "South Korea", "Korean", "Seoul" 중 최소 하나 포함
   - 인물이 등장하면 "Korean people" 또는 "Asian people"로 명시
   - 실존 인물의 이름은 쓰지 않음 (스톡사진에 없어서 엉뚱한 결과가 나옴)
   - 기사 내용과 무관한 뻔한 이미지(회의실, 악수, 노트북 타이핑)를
     기본값처럼 쓰지 않음 — 반드시 1단계에서 뽑은 명사를 반영

나쁜 예 (추상적, 기사 내용과 무관): "Korean people talking, Seoul, South Korea"
좋은 예 (기사가 '반려동물 카페 논란'): "Korean pet cafe interior with cats, Seoul, South Korea"
좋은 예 (기사가 '폭염 계곡 인파'): "Crowded valley stream in summer heat, South Korea"
좋은 예 (기사가 '전기차 화재'): "Electric car on fire at parking lot, South Korea"
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


def _is_quota_error(exc: Exception) -> bool:
    """한도 초과(429/RESOURCE_EXHAUSTED)로 인한 오류인지 판별."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def generate_blog_post(item: dict) -> dict:
    """
    하나의 보도자료(item)에 대해 Gemini API를 호출하고,
    파싱된 JSON dict를 반환한다. 실패 시 None 반환.
    기본 모델의 무료 한도가 다 찬 경우, MODEL_FALLBACK_CHAIN의 다음 모델로
    자동 재시도한다.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)

    last_error = None
    for model_name in MODEL_FALLBACK_CHAIN:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=build_user_message(item),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",  # JSON 형식으로만 응답하도록 강제
                    temperature=0.7,
                ),
            )
            if model_name != MODEL_FALLBACK_CHAIN[0]:
                print(f"[진단] 기본 모델 한도 초과로 대체 모델 사용: {model_name}")
            break  # 성공하면 반복 종료
        except Exception as e:
            last_error = e
            if _is_quota_error(e):
                print(f"[진단] '{model_name}' 한도 초과, 다음 모델로 재시도합니다: {e}")
                continue
            raise  # 한도 문제가 아닌 다른 오류는 그대로 올려서 main.py에서 처리
    else:
        # 체인의 모든 모델이 한도 초과인 경우
        raise last_error

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
