# -*- coding: utf-8 -*-
"""
Main (신제품 vs 전작 비교)
---------------------------
Collector -> Writer -> Publisher 순서로 비교 콘텐츠 파이프라인을 실행한다.
트렌딩 이슈 파이프라인(main.py)과는 완전히 분리되어, 별도의
data/processed_comparison.json으로 중복을 관리한다.
"""

import datetime
import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from collector_comparison import collect_new_comparisons, save_processed
from writer_comparison import generate_comparison_post
from publisher import publish_post

PUBLISH_AS_DRAFT = True

_raw_max_items = os.environ.get("MAX_ITEMS_PER_RUN", "3")
try:
    MAX_ITEMS_PER_RUN = max(1, min(10, int(_raw_max_items)))
except ValueError:
    MAX_ITEMS_PER_RUN = 3
print(f"[진단] 이번 실행 최대 처리 건수: {MAX_ITEMS_PER_RUN}")


def main():
    new_items, processed = collect_new_comparisons(max_items=MAX_ITEMS_PER_RUN)

    if not new_items:
        print("신규 비교 대상 기사가 없습니다. 종료합니다.")
        return

    print(f"신규 비교 대상 기사 {len(new_items)}건 처리를 시작합니다.")

    for item in new_items:
        print(f"\n[처리 중] {item['title']}")
        try:
            blog_post = generate_comparison_post(item)
            if not blog_post:
                print("  -> 비교 글 생성 불가(내용 부족 또는 JSON 오류). 건너뜁니다.")
                # 부족한 걸로 판단된 것도 재시도 방지를 위해 처리 완료로 기록
                processed[item["link"]] = {
                    "post_id": None,
                    "title": item["title"],
                    "published": item.get("published", ""),
                    "updated_at": datetime.datetime.utcnow().isoformat(),
                    "skipped_reason": "insufficient_comparison_data",
                }
                continue

            result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
            post_id = result.get("id")
            print(f"  -> 발행 완료 (post_id={post_id}): {result.get('url', '(초안)')}")

            processed[item["link"]] = {
                "post_id": post_id,
                "title": blog_post.get("title", item["title"]),
                "published": item.get("published", ""),
                "updated_at": datetime.datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"  -> 오류 발생, 이 건은 건너뜁니다: {e}")
            traceback.print_exc()
            continue

    save_processed(processed)
    print("\n처리 완료 목록을 저장했습니다.")


if __name__ == "__main__":
    main()
