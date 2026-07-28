# -*- coding: utf-8 -*-
"""
Publisher
---------
생성된 블로그 JSON(blog_markdown 등)을 Blogger API v3를 통해
초안(draft) 또는 즉시 발행으로 등록합니다.

필요한 환경변수:
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- GOOGLE_REFRESH_TOKEN
- BLOGGER_BLOG_ID
"""

import os
import markdown as md_lib  # pip install markdown (마크다운 -> HTML 변환)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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
        "blog_markdown": "# 테스트\n\n이것은 **테스트** 글입니다.",
        "tags": ["테스트"],
    }
    res = publish_post(sample_post, is_draft=True)
    print("발행 결과:", res.get("url"))
