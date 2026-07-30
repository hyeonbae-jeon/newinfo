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


def fetch_article_body(url: str) -> str:
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
            if len(text) > 100:
                return text

    body = soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""


def collect_new_releases(max_items: int = 5):
    processed = load_processed()

    try:
        rss_res = requests.get(RSS_URL, headers=HEADERS, timeout=10)
        rss_res.raise_for_status()
        feed = feedparser.parse(rss_res.content)
        print(f"[진단] RSS HTTP 상태코드: {rss_res.status_code}")
    except requests.RequestException as e:
        print(f"[진단] RSS 요청 자체가 실패했습니다: {e}")
        return [], processed

    print(f"[진단] feed.bozo(파싱 오류 여부): {feed.bozo}")
    if feed.bozo:
        print(f"[진단] 파싱 오류 내용: {feed.get('bozo_exception')}")
    print(f"[진단] RSS에서 읽은 전체 항목 수: {len(feed.entries)}")
    print(f"[진단] 이미 처리된 것으로 기록된 항목 수: {len(processed)}")

    new_items = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link or link in processed:
            continue

        title = entry.get("title", "").strip()
        published = entry.get("published", "")
        agency = entry.get("author", "") or entry.get("category", "") or ""

        body = fetch_article_body(link)
        if not body:
            body = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(strip=True)

        new_items.append({
            "title": title,
            "link": link,
            "published": published,
            "agency": agency,
            "body": body,
        })

        time.sleep(1)

        if len(new_items) >= max_items:
            break

    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_releases()
    print(f"신규 보도자료 {len(items)}건 발견")
    for it in items:
        print("-", it["title"], it["link"])
