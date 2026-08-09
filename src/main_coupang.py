# -*- coding: utf-8 -*-
"""
Main (쿠팡 상품 리뷰 파이프라인)
----------------------------------
GitHub Actions workflow_dispatch 입력값으로 상품 정보를 받아
Writer → Publisher 순서로 블로그 글을 생성·발행한다.

스케줄 자동 실행 없음 — 수동으로만 실행 (workflow_dispatch).
data/processed_coupang.json으로 동일 상품 중복 발행을 방지한다.
"""

import datetime
import json
import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from writer_coupang import generate_coupang_post
from publisher import publish_post

PROCESSED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed_coupang.json"
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
    GitHub Actions inputs → 상품 정보 dict 변환.
    필수: PRODUCT_NAME, PRICE, COUPANG_LINK
    선택: VOLUME, FEATURES (줄바꿈으로 구분), MEMO
    """
    product_name = os.environ.get("PRODUCT_NAME", "").strip()
    price = os.environ.get("PRICE", "").strip()
    coupang_link = os.environ.get("COUPANG_LINK", "").strip()

    if not product_name or not coupang_link:
        print("오류: PRODUCT_NAME과 COUPANG_LINK는 필수입니다.")
        sys.exit(1)

    features_raw = os.environ.get("FEATURES", "").strip()
    features = [line.strip() for line in features_raw.splitlines() if line.strip()]

    return {
        "product_name": product_name,
        "price": price,
        "volume": os.environ.get("VOLUME", "").strip(),
        "features": features,
        "coupang_link": coupang_link,
        "memo": os.environ.get("MEMO", "").strip(),
    }


def main():
    item = parse_env_item()
    product_name = item["product_name"]

    processed = load_processed()
    if product_name in processed:
        print(f"이미 발행된 상품입니다: {product_name}")
        print(f"기존 post_id: {processed[product_name].get('post_id')}")
        print("재발행하려면 data/processed_coupang.json에서 해당 항목을 삭제하세요.")
        sys.exit(0)

    print(f"[쿠팡 리뷰] 글 생성 시작: {product_name}")

    try:
        blog_post = generate_coupang_post(item)
        if not blog_post:
            print("글 생성 실패.")
            sys.exit(1)

        result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
        post_id = result.get("id")
        post_url = result.get("url", "(초안)")
        print(f"발행 완료 (post_id={post_id}): {post_url}")

        processed[product_name] = {
            "post_id": post_id,
            "title": blog_post.get("title", product_name),
            "coupang_link": item["coupang_link"],
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }
        save_processed(processed)
        print("처리 기록 저장 완료.")

    except Exception as e:
        print(f"오류 발생: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
