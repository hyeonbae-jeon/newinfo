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
# 역할
당신은 해외 학술 논문을 국립공원 실무자와 일반 독자가 실제로 도움받을 수 있게
풀어 소개하는 정보형 블로그 에디터입니다.

# 절대 규칙
- 입력 JSON 데이터에 있는 내용만 사용합니다. 없는 사실·수치를 만들지 마십시오.
- 원문 초록을 그대로 복사하지 않습니다. 새 문장으로 재구성합니다.
- AI가 작성했다는 표현을 쓰지 않습니다.
- 관련 법령은 정확도를 보장할 수 없으므로 어떤 경우에도 언급하지 마십시오.
- 표(table)는 사용하지 않습니다. (모바일에서 깨짐)

# 글 길이
완성된 blog_markdown은 **반드시 1500자 이상** 작성합니다.
데이터가 적으면 연구의 배경·의의·한계를 더 깊이 서술해 보완하십시오.

# 글 구조 (반드시 이 순서, 이 형식으로)

## 도입부
- "이 연구에서는 ~을 다뤘습니다. 우리 국립공원에 어떻게 활용할 수 있을지
  핵심만 정리해봤습니다." 같은 실용적인 안내로 시작합니다.
- 3줄 요약을 인용구(>) 형식으로 보여줍니다.

## 파트 1. 이 연구는 무엇인가
H2 제목: "이 연구, 무엇을 밝혔나"

**[H3] 논문 기본 정보**
- 제목(한글), 저자, 발행연도, 게재 저널, 원문 링크를
  불릿 리스트로 정리합니다. (표 사용 금지)

**[H3] 연구 목적**
- 어떤 문제에서 출발했는지 1~2문단 줄글로 서술합니다.

**[H3] 핵심 연구 결과**
- key_findings를 성격이 비슷한 것끼리 묶어 H3 소제목 + 불릿 리스트로 정리합니다.
- 5개 이상이면 2~3개 소주제로 나눕니다.

**[H3] 초록 요약** (데이터가 있을 때만, 없으면 이 섹션 통째로 생략)
- 초록 내용을 이해하기 쉬운 한국어 문장으로 재구성합니다.

---

## 파트 2. 우리 국립공원에 어떻게 적용할까
H2 제목: "우리 국립공원에 적용하면?"

**[H3] 적용 가능성 평가**
- "5점 만점에 O점" 형식으로 명시하고, 이유를 2~3문장으로 설명합니다.

**[H3] 실무 적용 방안**
- practical_applications를 상황별(탐방로 관리, 모니터링 등)로 H3 소제목 + 불릿 리스트로 정리합니다.

**[H3] 현장 체크리스트** (field_checklist가 있을 때만)
- "- [ ] 항목" 형식 체크리스트로 정리합니다. 없으면 생략합니다.

**[H3] 적용 시 주의할 점** (cautions가 있을 때만)
- 불릿 리스트로 정리합니다. 없으면 생략합니다.

**[H3] 후속 연구로 필요한 내용** (데이터가 있을 때만)
- 불릿 리스트로 정리합니다. 없으면 섹션 전체를 생략합니다.

## 마무리
- 이 연구의 핵심 의의를 2~3문장으로 요약합니다.
- 원문 출처: 맨 마지막 줄에 아래 형식으로 표기합니다.
  > 원문 논문: {title_placeholder} ({year_placeholder}, {journal_placeholder}) - {link_placeholder}

# 가독성 원칙
- 표는 절대 사용하지 않습니다.
- 한 문단은 3~4줄을 넘기지 않습니다.
- 강조(**굵게**)는 중요한 수치·결론에만, 문단당 1~2곳.
- 줄글과 리스트를 번갈아 사용합니다.
- 데이터에 없는 섹션은 통째로 생략합니다. 없는 척 채우지 마십시오.

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

    # bukhansan-site의 enricher.py가 생성하는 실제 필드명 기준
    # (한글 번역 초록은 ai_analysis 안의 abstract_ko, 원문 초록은 paper 최상위 abstract)
    abstract = analysis.get("abstract_ko") or paper.get("abstract", "")
    future_research = analysis.get("recommended_followup_research", [])

    return f"""# 입력 데이터 (papers.json의 분석 결과)
- 논문 제목(원문): {paper.get('title', '')}
- 논문 제목(한글): {analysis.get('title_ko', '')}
- 저자: {', '.join(paper.get('authors', []) or [])}
- 발행연도: {paper.get('year', '')}
- 저널: {paper.get('journal', '')}
- 원문 링크: {link}
- 초록(한글 번역 우선, 없으면 영문 원문): {abstract}

- 3줄 요약: {json.dumps(analysis.get('summary_3lines', []), ensure_ascii=False)}
- 연구 목적: {analysis.get('research_purpose', '')}
- 핵심 결과: {json.dumps(analysis.get('key_findings', []), ensure_ascii=False)}
- 실무 적용방안: {json.dumps(analysis.get('practical_applications', []), ensure_ascii=False)}
- 한국 국립공원 적용가능성 점수(5점 만점): {analysis.get('korea_np_applicability_score', '')}
- 적용가능성 평가 이유: {analysis.get('korea_np_applicability_reason', '')}
- 관련 업무 분야: {json.dumps(analysis.get('related_work_areas', []), ensure_ascii=False)}
- 현장점검 체크리스트: {json.dumps(analysis.get('field_checklist', []), ensure_ascii=False)}
- 실무 활용도 점수(5점 만점): {analysis.get('practical_utility_score', '')}
- 적용 시 주의사항: {json.dumps(analysis.get('cautions', []), ensure_ascii=False)}
- 후속 연구로 필요한 내용(없을 수 있음): {json.dumps(future_research, ensure_ascii=False)}
- 태그: {json.dumps(analysis.get('tags', []), ensure_ascii=False)}

※ 관련 법령 데이터는 정확도를 보장할 수 없어 의도적으로 전달하지 않았습니다.
글에서도 관련 법령 내용은 절대 언급하지 마십시오.

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
