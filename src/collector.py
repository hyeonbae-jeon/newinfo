# -*- coding: utf-8 -*-
"""
Collector (Google News 기반)
----------------------------
공공데이터포털 점검 등으로 Open API를 못 쓸 때 쓰는 대체 수집기입니다.
구글 뉴스에서 korea.kr(정책브리핑) 도메인의 최신 글을 검색해서
원문 링크로 들어가 본문을 크롤링합니다.

주의:
- 구글 뉴스 RSS는 공식 지원 API가 아니라 검색 결과를 RSS로 보여주는 방식이라
  가끔 형식이 바뀔 수 있습니다.
- 링크가 구글 리다이렉트 주소로 오는 경우가 많아서, 실제 원문 주소로
  한번 더 따라가는 과정이 필요합니다 (resolve_final_url).
"""

import json
import os
import time
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

# korea.kr 도메인으로 제한해서 구글 뉴스에서 검색
SEARCH_QUERY = "site:korea.kr 보도자료"
GOOGLE_NEWS_RSS_URL = (
    f"https://news.google.com/rss/search?q={quote(SEARCH_QUERY)}&hl=ko&gl=KR&ceid=KR:ko"
)

PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

CONTENT_SELECTORS = [
    "div.article_cont",
    "div#article_cont",
    "div.view_con",
    "div.cont_area",
    "div#content",
    "article",
]


def load_processed():
    if not os.path.exists(PROCESSED_PATH):
        return set()
    with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return set()
    return set(data.get("processed", []))


def save_processed(processed_set):
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump({"processed": sorted(processed_set)}, f, ensure_ascii=False, indent=2)


def resolve_final_url(google_link: str) -> str:
    """구글 뉴스 리다이렉트 링크를 실제 원문 주소로 변환."""
    try:
        res = requests.get(google_link, headers=HEADERS, timeout=10, allow_redirects=True)
        return res.url
    except requests.RequestException:
        return google_link  # 실패하면 원래 링크라도 사용


def fetch_article_body(url: str) -> str:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"[진단] 본문 요청 실패({url}): {e}")
        return ""

    soup = BeautifulSoup(res.text, "html.parser")

    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return text

    body = soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""


def collect_new_releases(max_items: int = 5):
    """
    구글 뉴스 검색 RSS에서 korea.kr 관련 글을 찾아,
    아직 처리하지 않은 것만 반환.
    반환 형식: [{title, link, published, agency, body}, ...]
    """
    processed = load_processed()

    try:
        rss_res = requests.get(GOOGLE_NEWS_RSS_URL, headers=HEADERS, timeout=15)
        rss_res.raise_for_status()
        feed = feedparser.parse(rss_res.content)
        print(f"[진단] 구글뉴스 RSS 상태코드: {rss_res.status_code}")
    except requests.RequestException as e:
        print(f"[진단] 구글뉴스 RSS 요청 실패: {e}")
        return [], processed

    print(f"[진단] feed.bozo: {feed.bozo}")
    print(f"[진단] 검색된 전체 항목 수: {len(feed.entries)}")

    new_items = []
    for entry in feed.entries:
        google_link = entry.get("link", "")
        if not google_link:
            continue

        real_url = resolve_final_url(google_link)

        if real_url in processed:
            continue

        # korea.kr 도메인이 아니면 건너뜀 (검색 필터가 완벽하지 않을 수 있어서)
        if "korea.kr" not in real_url:
            continue

        title = entry.get("title", "").strip()
        published = entry.get("published", "")
        agency = ""
        if hasattr(entry, "source") and entry.source:
            agency = entry.source.get("title", "")

        body = fetch_article_body(real_url)
        if not body:
            body = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(strip=True)

        new_items.append({
            "title": title,
            "link": real_url,
            "published": published,
            "agency": agency,
            "body": body,
        })

        time.sleep(1)

        if len(new_items) >= max_items:
            break

    print(f"[진단] 필터링 후 신규 항목 수: {len(new_items)}")
    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_releases()
    print(f"신규 보도자료 {len(items)}건 발견")
    for it in items:
        print("-", it["title"], it["link"])
