# -*- coding: utf-8 -*-
"""
Collector
---------
대한민국 정책브리핑(korea.kr) RSS에서 신규 보도자료를 수집하고,
원문 링크에 접속해 본문 텍스트까지 가져옵니다.

- RSS: https://www.korea.kr/rss/pressrelease.xml (보도자료 통합 피드)
- 이미 처리한 글은 data/processed.json에 URL(guid) 기준으로 기록해 중복 방지
"""

import json
import os
import time
import feedparser
import requests
from bs4 import BeautifulSoup

RSS_URL = "https://www.korea.kr/rss/pressrelease.xml"
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# 본문이 들어있을 가능성이 높은 후보 선택자들 (사이트 구조가 바뀔 수 있어 여러 개를 시도)
CONTENT_SELECTORS = [
    "div.article_cont",
    "div#article_cont",
    "div.view_con",
    "div.cont_area",
    "div#content",
    "article",
]


def load_processed():
    """이미 처리한 글 목록(guid/link 집합)을 불러온다."""
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


def fetch_article_body(url: str) -> str:
    """원문 URL에 접속해 본문 텍스트를 최대한 추출한다. 실패하면 빈 문자열 반환."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(res.text, "html.parser")

    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if len(text) > 100:  # 너무 짧으면 본문이 아닐 가능성이 높음
                return text

    # 후보 선택자로 못 찾으면 전체 텍스트에서 대략 추출 (최후 수단)
    body = soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""


def collect_new_releases(max_items: int = 5):
    """
    RSS를 읽어 아직 처리하지 않은 보도자료 목록을 반환한다.
    반환 형식: [{title, link, published, agency, body}, ...]
    """
    processed = load_processed()
    feed = feedparser.parse(RSS_URL)

    new_items = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link or link in processed:
            continue

        title = entry.get("title", "").strip()
        published = entry.get("published", "")
        # RSS 항목에 부처명이 포함된 카테고리/저자 필드가 있는 경우가 있어 시도해본다
        agency = entry.get("author", "") or entry.get("category", "") or ""

        body = fetch_article_body(link)
        if not body:
            # 본문을 못 가져왔으면 RSS 요약(summary)이라도 사용
            body = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(strip=True)

        new_items.append({
            "title": title,
            "link": link,
            "published": published,
            "agency": agency,
            "body": body,
        })

        time.sleep(1)  # 원문 서버에 과도한 요청을 피하기 위한 딜레이

        if len(new_items) >= max_items:
            break

    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_releases()
    print(f"신규 보도자료 {len(items)}건 발견")
    for it in items:
        print("-", it["title"], it["link"])
