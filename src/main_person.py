# -*- coding: utf-8 -*-
"""
Main (인물 분석 파이프라인)
----------------------------
Collector -> Writer -> Publisher 순서로 인물 소개 콘텐츠 파이프라인을 실행한다.
data/processed_persons.json으로 중복(이미 소개한 인물)을 관리한다.
"""

import datetime
import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from collector_person import collect_new_persons, save_processed
from writer_person import generate_person_post
from publisher import publish_post

PUBLISH_AS_DRAFT = True

_raw_max_items = os.environ.get("MAX_ITEMS_PER_RUN", "2")
try:
    MAX_ITEMS_PER_RUN = max(1, min(5, int(_raw_max_items)))
except ValueError:
    MAX_ITEMS_PER_RUN = 2


def main():
    new_items, processed = collect_new_persons(max_items=MAX_ITEMS_PER_RUN)

    if not new_items:
        print("신규로 소개할 인물이 없습니다. 종료합니다.")
        return

    print(f"신규 인물 {len(new_items)}명 처리를 시작합니다.")

    for person in new_items:
        name = person["name"]
        print(f"\n[처리 중] {name}")
        try:
            blog_post = generate_person_post(person)
            if not blog_post:
                print("  -> 글 생성 실패. 건너뜁니다.")
                continue

            result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
            post_id = result.get("id")
            print(f"  -> 발행 완료 (post_id={post_id}): {result.get('url', '(초안)')} ")

            processed[name] = {
                "post_id": post_id,
                "title": blog_post.get("title", name),
                "wiki_url": person["wiki"]["wiki_url"],
                "updated_at": datetime.datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"  -> 오류 발생, 건너뜁니다: {e}")
            traceback.print_exc()
            continue

    save_processed(processed)
    print("\n처리 완료 목록을 저장했습니다.")


if __name__ == "__main__":
    main()
