# -*- coding: utf-8 -*-
"""
Collector (Google News 기반 - 일반 트렌딩 이슈)
------------------------------------------------
정부/공공기관 발표가 아니라, 사람들이 관심 가질만한 일반 트렌딩 이슈
(연예/사회/화제)를 구글 뉴스에서 수집합니다. 특정 도메인으로 제한하지 않고
구글 뉴스 전체 헤드라인 + 화제성 키워드 검색을 함께 사용합니다.

주의:
- 구글 뉴스 RSS는 공식 지원 API가 아니라 검색/피드 결과를 RSS로 보여주는
  방식이라 가끔 형식이 바뀔 수 있습니다.
- 링크가 구글의 암호화된 리다이렉트 주소로 오기 때문에, googlenewsdecoder로
  실제 원문 주소를 디코딩합니다.
- 다양한 언론사 사이트를 대상으로 하므로, 본문 크롤링은 여러 선택자를
  시도하고 실패하면 <p> 태그 전체를 모으는 범용 방식으로 폴백합니다.
"""

import json
import os
import time
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1

# 사람들이 관심 가질만한 일반 트렌딩 이슈(연예/사회/화제) 위주로 수집.
# 1) 구글 뉴스 '전체 헤드라인' 피드 (도메인 제한 없음, 실시간 화제성 이슈 위주)
# 2) 화제/이슈 키워드로 보완 검색
TOP_HEADLINES_URL = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"

SEARCH_QUERIES = [
    "화제",
    "이슈",
    "논란",
    "화제의 인물",
]


def _build_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"

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
    "div#articleBody",           # 네이버 뉴스 등
    "div#article-view-content-div",  # 네이버 뉴스
    "div.article_view",
    "div.news_end",
    "div#articeBody",
    "div.article-body",
    "div.art_txt",
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
    """구글 뉴스의 암호화된 리다이렉트 링크를 실제 원문 주소로 디코딩."""
    try:
        result = new_decoderv1(google_link, interval=1)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
        print(f"[진단] 디코딩 실패 응답: {result}")
    except Exception as e:
        print(f"[진단] 링크 디코딩 중 오류: {e}")
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

    # 특정 선택자로 못 찾으면, 사이트 구조에 상관없이 <p> 태그를 전부 모아서 시도
    # (완벽하진 않지만 대부분의 뉴스 사이트에서 본문 문단은 <p>로 되어있는 경우가 많음)
    paragraphs = soup.find_all("p")
    if paragraphs:
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        if len(text) > 100:
            return text

    body = soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""


def collect_new_releases(max_items: int = 5):
    """
    여러 키워드로 구글 뉴스 검색 RSS를 조회해 korea.kr 관련 글을 찾고,
    아직 처리하지 않은 것만 반환.
    반환 형식: [{title, link, published, agency, body}, ...]
    """
    processed = load_processed()

    # 여러 검색어의 결과를 하나로 합치되, 구글 링크 기준으로 중복 제거
    all_entries = []
    seen_google_links = set()

    # 1) 전체 헤드라인(화제성 이슈) 피드
    rss_urls = [("전체 헤드라인", TOP_HEADLINES_URL)]
    rss_urls += [(query, _build_rss_url(query)) for query in SEARCH_QUERIES]

    for label, rss_url in rss_urls:
        try:
            rss_res = requests.get(rss_url, headers=HEADERS, timeout=15)
            rss_res.raise_for_status()
            feed = feedparser.parse(rss_res.content)
            print(f"[진단] '{label}' 상태코드: {rss_res.status_code}, 항목 수: {len(feed.entries)}")
        except requests.RequestException as e:
            print(f"[진단] '{label}' 요청 실패: {e}")
            continue

        for entry in feed.entries:
            google_link = entry.get("link", "")
            if google_link and google_link not in seen_google_links:
                seen_google_links.add(google_link)
                all_entries.append(entry)

        time.sleep(1)  # 구글 요청 사이 짧은 딜레이

    print(f"[진단] 검색 {len(rss_urls)}개 합산, 중복 제거 후 전체 항목 수: {len(all_entries)}")

    new_items = []
    skipped_already_processed = 0
    sample_shown = 0

    for entry in all_entries:
        google_link = entry.get("link", "")
        if not google_link:
            continue

        real_url = resolve_final_url(google_link)

        if sample_shown < 3:
            print(f"[진단] 구글링크: {google_link}")
            print(f"[진단]   -> 변환된 실제 주소: {real_url}")
            sample_shown += 1

        if real_url in processed:
            skipped_already_processed += 1
            continue

        # 구글 리다이렉트가 아예 안 풀린 경우(여전히 google.com)만 건너뜀.
        # 이제 특정 도메인(korea.kr)으로 제한하지 않음 — 일반 트렌딩 이슈이므로.
        if "google.com" in real_url:
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

    print(f"[진단] 이미 처리됨으로 건너뜀: {skipped_already_processed}건")
    print(f"[진단] 필터링 후 신규 항목 수: {len(new_items)}")
    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_releases()
    print(f"신규 보도자료 {len(items)}건 발견")
    for it in items:
        print("-", it["title"], it["link"])
