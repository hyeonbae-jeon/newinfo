# -*- coding: utf-8 -*-
"""
Main
----
Collector -> Writer -> Publisher 순서로 전체 파이프라인을 실행하고,
처리한 글 목록을 data/processed.json에 갱신한다.

GitHub Actions에서 스케줄 실행되는 진입점 스크립트.
"""

import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from collector import collect_new_releases, save_processed
from writer import generate_blog_post
from publisher import publish_post

# 처음엔 반드시 True로 두고, 몇 번 검수해서 품질을 확인한 뒤 False로 바꾸는 것을 추천
PUBLISH_AS_DRAFT = True

# 한 번 실행에 처리할 최대 보도자료 건수 (API 비용/부하 조절용)
MAX_ITEMS_PER_RUN = 3


def main():
    new_items, processed = collect_new_releases(max_items=MAX_ITEMS_PER_RUN)

    if not new_items:
        print("신규 보도자료가 없습니다. 종료합니다.")
        return

    print(f"신규 보도자료 {len(new_items)}건 처리를 시작합니다.")

    for item in new_items:
        print(f"\n[처리 중] {item['title']}")
        try:
            blog_post = generate_blog_post(item)
            if not blog_post:
                print("  -> 블로그 글 생성 실패 (JSON 파싱 오류). 건너뜁니다.")
                continue

            result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
            print(f"  -> 발행 완료: {result.get('url', '(URL 없음, 초안일 수 있음)')}")

            # 성공한 건만 처리 완료 목록에 추가 (실패하면 다음 실행에서 재시도)
            processed.add(item["link"])

        except Exception as e:
            print(f"  -> 오류 발생, 이 건은 건너뜁니다: {e}")
            traceback.print_exc()
            continue

    save_processed(processed)
    print("\n처리 완료 목록을 저장했습니다.")


if __name__ == "__main__":
    main()
