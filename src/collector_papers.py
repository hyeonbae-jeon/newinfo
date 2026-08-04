# -*- coding: utf-8 -*-
"""
Collector (국립공원 논문 소개)
-------------------------------
사용자가 만든 국립공원 AI 지식 플랫폼(papers.json)에서 이미 AI가 분석해둔
논문 데이터를 가져와, 아직 블로그에 소개하지 않은 논문 중
"한국 국립공원 적용 가능성 점수"가 높은 순으로 골라옵니다.

이 파이프라인은 뉴스 크롤링이 필요 없습니다 — 이미 정제된 데이터를
그대로 활용하기 때문에 다른 두 파이프라인보다 더 안정적입니다.
"""

import json
import os

import requests

PAPERS_JSON_URL = "https://hyeonbae-jeon.github.io/bukhansan/papers.json"
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed_papers.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def load_processed():
    if not os.path.exists(PROCESSED_PATH):
        return {}
    with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    raw = data.get("processed", [])
    if isinstance(raw, list):
        return {pid: {"post_id": None} for pid in raw}
    return raw


def save_processed(processed_dict):
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump({"processed": processed_dict}, f, ensure_ascii=False, indent=2)


def fetch_all_papers():
    print(f"[진단] papers.json 요청 중: {PAPERS_JSON_URL}")
    res = requests.get(PAPERS_JSON_URL, headers=HEADERS, timeout=60)
    res.raise_for_status()
    data = res.json()
    papers = data.get("papers", [])
    print(f"[진단] 전체 논문 수: {len(papers)}, 메타: {data.get('meta', {}).get('analyzed')}건 분석 완료")
    return papers


def collect_new_papers(max_items: int = 2, min_applicability: int = 4):
    """
    ai_analysis가 있고 아직 소개하지 않은 논문 중,
    korea_np_applicability_score(적용 가능성 점수) -> practical_utility_score(실무 활용도)
    순으로 정렬해서 상위 max_items개를 반환.
    반환 형식: [{id, title, title_ko, ai_analysis, ...papers.json의 원본 필드들}, ...]
    """
    processed = load_processed()

    try:
        papers = fetch_all_papers()
    except requests.RequestException as e:
        print(f"[진단] papers.json 요청 실패: {e}")
        return [], processed

    candidates = []
    for paper in papers:
        paper_id = paper.get("id")
        if not paper_id or paper_id in processed:
            continue

        analysis = paper.get("ai_analysis")
        if not analysis:
            continue  # 아직 AI 분석이 안 된 논문은 제외

        score = analysis.get("korea_np_applicability_score", 0)
        if score < min_applicability:
            continue

        candidates.append(paper)

    # 적용 가능성 점수 -> 실무 활용도 점수 순으로 정렬 (둘 다 높은 논문 우선)
    candidates.sort(
        key=lambda p: (
            p["ai_analysis"].get("korea_np_applicability_score", 0),
            p["ai_analysis"].get("practical_utility_score", 0),
        ),
        reverse=True,
    )

    selected = candidates[:max_items]
    print(f"[진단] 조건(점수 {min_applicability}점 이상) 충족 미소개 논문: {len(candidates)}건 중 {len(selected)}건 선택")

    return selected, processed


if __name__ == "__main__":
    items, _ = collect_new_papers()
    print(f"신규 소개 대상 논문 {len(items)}건")
    for it in items:
        print("-", it["ai_analysis"].get("title_ko", it["title"]))
