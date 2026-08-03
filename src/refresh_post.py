# -*- coding: utf-8 -*-
"""
Refresh Post
------------
이미 발행한 글 하나를 골라서, 원문을 다시 크롤링 → Gemini로 다시 작성 →
Blogger의 기존 게시물을 업데이트한다 (새 글을 만들지 않고 덮어씀).

사용법 (터미널에서 직접 실행할 때):
    TARGET_URL="https://..." python src/refresh_post.py

GitHub Actions에서는 update_post.yml 워크플로우가 TARGET_URL을
workflow_dispatch 입력값으로 받아 이 스크립트를 실행한다.
"""

import datetime
import os
import sys

sys.path.append(os.path.dirname(__file__))

from collector import fetch_article_body, load_processed, save_processed
from writer import generate_blog_post
from publisher import update_post

# 업데이트할 때도 이미지를 새로 검색해서 넣을지 여부.
# 기존 이미지를 그대로 두고 싶으면 False로.
INSERT_NEW_IMAGES = True


def main():
    target_url = os.environ.get("TARGET_URL", "").strip()
    if not target_url:
        print("[오류] TARGET_URL 환경변수(또는 인자)로 업데이트할 글의 원문 URL을 지정해주세요.")
        sys.exit(1)

    processed = load_processed()
    entry = processed.get(target_url)

    if not entry or not entry.get("post_id"):
        print(f"[오류] processed.json에서 '{target_url}'에 해당하는 post_id를 찾을 수 없습니다.")
        print("       (이 URL로 발행된 적이 없거나, 예전 버전 형식이라 post_id가 비어있을 수 있습니다.)")
        sys.exit(1)

    post_id = entry["post_id"]
    print(f"[진단] 대상 post_id: {post_id}")

    print("[진단] 원문을 다시 크롤링합니다...")
    body = fetch_article_body(target_url)
    if not body:
        print("[오류] 원문 본문을 다시 가져오지 못했습니다. (사이트가 막혔거나 주소가 바뀌었을 수 있음)")
        sys.exit(1)

    item = {
        "title": entry.get("title", ""),
        "link": target_url,
        "published": entry.get("published", ""),
        "agency": "",
        "body": body,
    }

    print("[진단] Gemini로 새 버전 글을 생성합니다...")
    blog_post = generate_blog_post(item)
    if not blog_post:
        print("[오류] 블로그 글 생성에 실패했습니다 (JSON 파싱 오류).")
        sys.exit(1)

    print("[진단] Blogger 게시물을 업데이트합니다...")
    result = update_post(post_id, blog_post, insert_new_images=INSERT_NEW_IMAGES)
    print(f"업데이트 완료: {result.get('url')}")

    entry["title"] = blog_post.get("title", entry.get("title", ""))
    entry["updated_at"] = datetime.datetime.utcnow().isoformat()
    processed[target_url] = entry
    save_processed(processed)


if __name__ == "__main__":
    main()
