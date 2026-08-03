# -*- coding: utf-8 -*-
"""
Collector (신제품 vs 전작 비교)
--------------------------------
Gemini의 웹 검색(grounding)은 무료가 아니라서, 스펙을 Gemini가 스스로
기억으로 채우게 하면 할루시네이션(부정확한 정보) 위험이 큽니다.

그래서 이 파이프라인은 "기자가 이미 전작과 비교해서 써놓은 기사"만
골라서 수집합니다. Gemini에게는 기사에 있는 비교 내용만 정리하게 하고,
없는 스펙을 추측해서 채우지 않도록 writer_comparison.py에서 강하게 지시합니다.
"""

import json
import os
import time
from urllib.parse import quote

import feedparser
import requests

# 트렌딩 이슈 collector와 크롤링 로직을 공유 (중복 구현 방지)
from collector import fetch_article_body, resolve_final_url, HEADERS

SEARCH_QUERIES = [
    "전작 비교",
    "이전 모델과 비교",
    "신제품 비교 스펙",
    "달라진 점 비교",
]

PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed_comparison.json")


def _build_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"


def load_processed():
    if not os.path.exists(PROCESSED_PATH):
        return {}
    with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    raw = data.get("processed", [])
    if isinstance(raw, list):
        return {url: {"post_id": None} for url in raw}
    return raw


def save_processed(processed_dict):
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump({"processed": processed_dict}, f, ensure_ascii=False, indent=2)


def collect_new_comparisons(max_items: int = 3):
    """
    '전작과 비교' 관련 키워드로 검색해, 아직 처리하지 않은 기사만 반환.
    반환 형식: [{title, link, published, agency, body}, ...]
    """
    processed = load_processed()

    all_entries = []
    seen_google_links = set()

    for query in SEARCH_QUERIES:
        rss_url = _build_rss_url(query)
        try:
            rss_res = requests.get(rss_url, headers=HEADERS, timeout=15)
            rss_res.raise_for_status()
            feed = feedparser.parse(rss_res.content)
            print(f"[진단] 검색어 '{query}' 상태코드: {rss_res.status_code}, 항목 수: {len(feed.entries)}")
        except requests.RequestException as e:
            print(f"[진단] 검색어 '{query}' 요청 실패: {e}")
            continue

        for entry in feed.entries:
            google_link = entry.get("link", "")
            if google_link and google_link not in seen_google_links:
                seen_google_links.add(google_link)
                all_entries.append(entry)

        time.sleep(1)

    print(f"[진단] 검색어 {len(SEARCH_QUERIES)}개 합산, 중복 제거 후 전체 항목 수: {len(all_entries)}")

    new_items = []
    skipped_already_processed = 0

    for entry in all_entries:
        google_link = entry.get("link", "")
        if not google_link:
            continue

        real_url = resolve_final_url(google_link)

        if real_url in processed:
            skipped_already_processed += 1
            continue

        if "google.com" in real_url:
            continue

        title = entry.get("title", "").strip()
        published = entry.get("published", "")
        agency = ""
        if hasattr(entry, "source") and entry.source:
            agency = entry.source.get("title", "")

        body = fetch_article_body(real_url)
        if not body or len(body) < 200:
            # 비교 기사는 정보량이 어느 정도 있어야 의미가 있어서,
            # 본문이 너무 짧으면(크롤링 실패 등) 건너뛴다.
            continue

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

    print(f"[진단] 이미 처리됨으로 건너뜀: {skipped_already_processed}건")
    print(f"[진단] 필터링 후 신규 항목 수: {len(new_items)}")
    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_comparisons()
    print(f"신규 비교 기사 {len(items)}건 발견")
    for it in items:
        print("-", it["title"], it["link"])
