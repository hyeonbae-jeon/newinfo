# -*- coding: utf-8 -*-
"""
Publisher
---------
생성된 블로그 JSON(blog_markdown 등)을 Blogger API v3를 통해
초안(draft) 또는 즉시 발행으로 등록합니다.
Pexels 무료 스톡사진에서 관련 이미지를 찾아 자동으로 삽입합니다.

필요한 환경변수:
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- GOOGLE_REFRESH_TOKEN
- BLOGGER_BLOG_ID
- PEXELS_API_KEY (없으면 이미지 삽입만 건너뛰고 글은 정상 발행됨)
"""

import os
import markdown as md_lib  # pip install markdown (마크다운 -> HTML 변환)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from image_finder import search_photo, build_image_html

SCOPES = ["https://www.googleapis.com/auth/blogger"]


def get_blogger_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("blogger", "v3", credentials=creds)


def insert_images(html_content: str, blog_post: dict) -> str:
    """
    썸네일 이미지는 맨 위에, 본문 이미지(최대 3개)는 <h2> 섹션 사이사이에 끼워넣는다.
    검색에 실패한 이미지는 조용히 건너뛴다 (글 발행 자체는 항상 되게).
    """
    title = blog_post.get("title", "")

    # 1) 썸네일: 맨 위에 삽입
    thumbnail_query = blog_post.get("thumbnail_prompt") or title
    thumbnail_photo = search_photo(thumbnail_query)
    thumbnail_html = build_image_html(thumbnail_photo, alt_text=title)

    # 2) 본문 이미지: <h2> 태그 기준으로 섹션을 나눠서 그 사이에 삽입
    image_prompts = blog_post.get("image_prompts", [])[:3]
    sections = html_content.split("<h2")

    # split 결과: sections[0]은 첫 h2 이전 내용, 이후는 각 "...</h2>...>" 조각
    rebuilt = [sections[0]]
    for idx, section in enumerate(sections[1:], start=1):
        rebuilt.append("<h2" + section)
        # 섹션이 끝난 뒤, 남은 이미지 프롬프트가 있으면 하나씩 삽입
        prompt_idx = idx - 1
        if prompt_idx < len(image_prompts):
            photo = search_photo(image_prompts[prompt_idx])
            rebuilt.append(build_image_html(photo, alt_text=image_prompts[prompt_idx]))

    body_with_images = "".join(rebuilt)
    return thumbnail_html + body_with_images


def publish_post(blog_post: dict, is_draft: bool = True):
    """
    blog_post: writer.generate_blog_post()가 반환한 dict
    is_draft: True면 임시저장(검수 후 수동 발행 추천), False면 바로 공개 발행
    """
    blog_id = os.environ["BLOGGER_BLOG_ID"]
    service = get_blogger_service()

    html_content = md_lib.markdown(
        blog_post.get("blog_markdown", ""), extensions=["tables", "fenced_code"]
    )

    html_content = insert_images(html_content, blog_post)

    body = {
        "kind": "blogger#post",
        "title": blog_post.get("title", "제목 없음"),
        "content": html_content,
        "labels": blog_post.get("tags", [])[:10],
    }

    request = service.posts().insert(blogId=blog_id, body=body, isDraft=is_draft)
    result = request.execute()
    return result


if __name__ == "__main__":
    sample_post = {
        "title": "테스트 발행 제목",
        "blog_markdown": "# 테스트\n\n이것은 **테스트** 글입니다.\n\n## 소제목\n\n내용",
        "tags": ["테스트"],
        "thumbnail_prompt": "korean government policy meeting",
        "image_prompts": ["seoul city hall"],
    }
    res = publish_post(sample_post, is_draft=True)
    print("발행 결과:", res.get("url"))
