# -*- coding: utf-8 -*-
"""
Main (국립공원 논문 소개)
--------------------------
Collector -> Writer -> Publisher 순서로 논문 소개 콘텐츠 파이프라인을 실행한다.
다른 두 파이프라인과 완전히 분리되어, data/processed_papers.json으로
중복(이미 소개한 논문)을 관리한다.
"""

import datetime
import os
import sys
import traceback

sys.path.append(os.path.dirname(__file__))

from collector_papers import collect_new_papers, save_processed
from writer_papers import generate_paper_post
from publisher import publish_post

PUBLISH_AS_DRAFT = True

_raw_max_items = os.environ.get("MAX_ITEMS_PER_RUN", "2")
try:
    MAX_ITEMS_PER_RUN = max(1, min(10, int(_raw_max_items)))
except ValueError:
    MAX_ITEMS_PER_RUN = 2
print(f"[진단] 이번 실행 최대 처리 건수: {MAX_ITEMS_PER_RUN}")

_raw_min_score = os.environ.get("MIN_APPLICABILITY_SCORE", "4")
try:
    MIN_APPLICABILITY_SCORE = max(1, min(5, int(_raw_min_score)))
except ValueError:
    MIN_APPLICABILITY_SCORE = 4


def main():
    new_items, processed = collect_new_papers(
        max_items=MAX_ITEMS_PER_RUN, min_applicability=MIN_APPLICABILITY_SCORE
    )

    if not new_items:
        print("신규로 소개할 논문이 없습니다. 종료합니다.")
        return

    print(f"신규 논문 {len(new_items)}건 처리를 시작합니다.")

    for paper in new_items:
        analysis = paper.get("ai_analysis", {})
        title_ko = analysis.get("title_ko", paper.get("title", ""))
        print(f"\n[처리 중] {title_ko}")
        try:
            blog_post = generate_paper_post(paper)
            if not blog_post:
                print("  -> 글 생성 실패(JSON 오류). 건너뜁니다.")
                continue

            result = publish_post(blog_post, is_draft=PUBLISH_AS_DRAFT)
            post_id = result.get("id")
            print(f"  -> 발행 완료 (post_id={post_id}): {result.get('url', '(초안)')}")

            processed[paper["id"]] = {
                "post_id": post_id,
                "title": blog_post.get("title", title_ko),
                "applicability_score": analysis.get("korea_np_applicability_score"),
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
