# -*- coding: utf-8 -*-
"""
Main (여행 코스 파이프라인)
----------------------------
GitHub Actions workflow_dispatch 입력값으로 여행 조건을 받아
Collector -> Writer -> Publisher 순서로 여행 코스 블로그 글을 생성·발행한다.

스케줄 자동 실행 없음 — 수동으로만 실행 (workflow_dispatch).
data/processed_travel.json으로 동일 여행지+일정 중복 발행을 방지한다.
"""

import datetime
import json
import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from collector_travel import collect_destination
from writer_travel import generate_travel_post
from publisher import publish_post

PROCESSED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed_travel.json"
)
PUBLISH_AS_DRAFT = True


def load_processed() -> dict:
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_processed(data: dict):
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_env_item() -> dict:
    """
    GitHub Actions inputs → 여행 조건 dict 변환.
    필수: DESTINATION, DURATION
    선택: DESTINATION_EN, THEME, BUDGET
    """
    destination = os.environ.get("DESTINATION", "").strip()
    duration = os.environ.get("DURATION", "").strip()

    if not destination or not duration:
        print("오류: DESTINATION과 DURATION은 필수입니다.")
        sys.exit(1)

    return {
        "destination": destination,
        "destination_en": os.environ.get("DESTINATION_EN", destination).strip(),
        "duration": duration,
        "theme": os.environ.get("THEME", "관광, 맛집").strip(),
        "budget": os.environ.get("BUDGET", "중간").strip(),
    }


def main():
    item = parse_env_item()
    # 중복 방지 키: 여행지 + 일정 + 테마 조합
    key = f"{item['destination']}_{item['duration']}_{item['theme']}"

    processed = load_processed()
    if key in processed:
        print(f"이미 발행된 코스입니다: {key}")
        print(f"기존 post_id: {processed[key].get('post_id')}")
        print("재발행하려면 data/processed_travel.json에서 해당 항목을 삭제하세요.")
        sys.exit(0)

    print(f"[여행 코스] 시작: {item['destination']} {item['duration']} / 테마: {item['theme']} / 예산: {item['budget']}")

    try:
        # 1. Wikipedia 수집
        print("  Wikipedia 데이터 수집 중...")
        wiki = collect_destination(item["destination"], item["destination_en"])

        # 2. 글 생성
        print("  Gemini 글 작성 중...")
        blog_post = generate_travel_post(item, wiki)
        if not blog_post:
            print("글 생성 실패.")
            sys.exit(1)

        # 3. 발행
        result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
        post_id = result.get("id")
        post_url = result.get("url", "(초안)")
        print(f"  발행 완료 (post_id={post_id}): {post_url}")

        # 4. 처리 기록 저장
        processed[key] = {
            "post_id": post_id,
            "title": blog_post.get("title", item["destination"]),
            "destination": item["destination"],
            "duration": item["duration"],
            "theme": item["theme"],
            "budget": item["budget"],
            "wiki_url": wiki.get("wiki_url", ""),
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }
        save_processed(processed)
        print("  처리 기록 저장 완료.")

    except Exception as e:
        print(f"오류 발생: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
