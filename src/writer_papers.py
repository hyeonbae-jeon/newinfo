# -*- coding: utf-8 -*-
"""
Writer (국립공원 논문 소개)
----------------------------
papers.json에 이미 들어있는 AI 분석 결과(3줄요약, 연구목적, 핵심결과,
실무 적용방안, 적용가능성 점수, 관련 법령, 현장점검 체크리스트 등)를
블로그 글 형식으로 재구성합니다.

이미 신뢰할 수 있는 분석 데이터가 있으므로, Gemini에게는 "제공된 데이터를
읽기 쉬운 글로 재구성"하는 역할만 맡기고, 데이터에 없는 내용을
새로 지어내는 것은 금지합니다.
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
당신은 학술 논문을 국립공원/자연보전 실무자와 일반 독자가 흥미롭게 읽을 수
있도록 소개하고 분석하는 전문 콘텐츠 에디터입니다.

# 절대 규칙 (매우 중요)
- 입력으로 주어지는 JSON 데이터(이미 AI가 분석해둔 결과)에 있는 내용만
  사용해서 글을 재구성하십시오. 데이터에 없는 사실, 수치, 사례를
  당신이 새로 만들어내지 마십시오.
- 다만 이미 주어진 데이터를 자연스러운 문장으로 재구성하고, 왜 이 연구가
  의미 있는지 흥미를 끄는 방식으로 설명하는 것은 허용됩니다 (창작이 아니라 재구성).
- 원문 abstract를 그대로 복사하지 말고 새로운 문장으로 재작성하십시오.
- AI가 작성했다는 표현은 사용하지 않습니다.

# 작성 규칙
1. 제목은 논문 주제를 흥미롭게 소개하는 자연스러운 제목으로 작성합니다
   (논문 제목을 그대로 쓰지 말고, 독자가 클릭하고 싶어지게).
2. 첫 문단에서 이 논문이 왜 지금 국립공원 관리에 중요한지 흥미를 끌게 시작합니다.
3. 아래 순서로 Markdown 섹션(H2)을 구성합니다.
   - 이 논문, 한눈에 보기 (3줄 요약 활용)
   - 연구는 무엇을 다루었나 (연구목적 + 핵심결과)
   - 우리 국립공원에 어떻게 적용할 수 있을까 (실무 적용방안)
   - 적용 가능성 평가 (점수와 그 이유 — "5점 만점에 O점"처럼 명시)
   - 현장에서 확인해볼 체크리스트 (field_checklist를 리스트로)
   - 관련 법령 (있는 경우만)
   - 적용 시 주의할 점 (cautions)
4. 표 또는 리스트를 적극 활용합니다.
5. 중요한 내용은 **굵게** 강조합니다.
6. 관련 법령이나 체크리스트가 데이터에 없으면 해당 섹션은 통째로 생략합니다.

# 이미지 프롬프트 작성 규칙
thumbnail_prompt, image_prompts는 스톡사진 검색에 쓰입니다.
- related_work_areas, tags에 나온 소재(예: 탐방로, 생태계, 산불, 야생동물 등)를
  구체적인 영어 명사로 바꿔 사용하십시오.
- 모든 프롬프트에 "South Korea", "Korean national park", "Seoul" 중
  최소 하나를 포함하십시오.
- 예시: "Hiking trail through forest, Korean national park" /
  "Wildlife camera trap in forest, South Korea"

# 출처 표기 지침
blog_markdown 맨 마지막 줄에 반드시 아래 형식으로 원문 논문 출처를 표기하십시오.
> 원문 논문: {title_placeholder} ({year_placeholder}, {journal_placeholder}) - {link_placeholder}

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


def build_user_message(paper: dict) -> str:
    analysis = paper.get("ai_analysis", {})
    link = paper.get("oa_url") or paper.get("openalex_url") or paper.get("doi", "")

    return f"""# 입력 데이터 (papers.json의 분석 결과)
- 논문 제목(원문): {paper.get('title', '')}
- 논문 제목(한글): {analysis.get('title_ko', '')}
- 저자: {', '.join(paper.get('authors', []) or [])}
- 발행연도: {paper.get('year', '')}
- 저널: {paper.get('journal', '')}
- 원문 링크: {link}

- 3줄 요약: {json.dumps(analysis.get('summary_3lines', []), ensure_ascii=False)}
- 연구 목적: {analysis.get('research_purpose', '')}
- 핵심 결과: {json.dumps(analysis.get('key_findings', []), ensure_ascii=False)}
- 실무 적용방안: {json.dumps(analysis.get('practical_applications', []), ensure_ascii=False)}
- 한국 국립공원 적용가능성 점수(5점 만점): {analysis.get('korea_np_applicability_score', '')}
- 적용가능성 평가 이유: {analysis.get('korea_np_applicability_reason', '')}
- 관련 업무 분야: {json.dumps(analysis.get('related_work_areas', []), ensure_ascii=False)}
- 관련 법령: {json.dumps(analysis.get('related_laws', []), ensure_ascii=False)}
- 현장점검 체크리스트: {json.dumps(analysis.get('field_checklist', []), ensure_ascii=False)}
- 실무 활용도 점수(5점 만점): {analysis.get('practical_utility_score', '')}
- 적용 시 주의사항: {json.dumps(analysis.get('cautions', []), ensure_ascii=False)}
- 태그: {json.dumps(analysis.get('tags', []), ensure_ascii=False)}

# 출처 표기용 정보
title_placeholder = {analysis.get('title_ko', '') or paper.get('title', '')}
year_placeholder = {paper.get('year', '')}
journal_placeholder = {paper.get('journal', '')}
link_placeholder = {link}
"""


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def generate_paper_post(paper: dict):
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
                contents=build_user_message(paper),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.6,
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
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print("JSON 파싱 실패. 원본 응답:")
        print(raw_text)
        return None
