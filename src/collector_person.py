# -*- coding: utf-8 -*-
"""
Collector (인물 분석 - Wikipedia 기반)
---------------------------------------
Wikipedia API로 최근 주목받는 인물 데이터를 수집한다.
구글 뉴스에서 화제 인물 이름을 뽑고 → Wikipedia에서 상세 정보를 보완하는 구조.

흐름:
  1. 구글 뉴스 RSS에서 '화제 인물' 관련 기사 수집 → 인물 이름 후보 추출
  2. Wikipedia API로 해당 인물 정보(요약, 생애, 경력 등) 조회
  3. data/processed_persons.json에 없는 신규 인물만 반환
"""

import json
import os
import re
import time
from urllib.parse import quote

import feedparser
import requests

PROCESSED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed_persons.json"
)

# 화제 인물 관련 구글 뉴스 검색 키워드
SEARCH_QUERIES = [
    "화제의 인물",
    "인물 조명",
    "주목받는 인물",
    "누구 프로필",
    "인물 분석",
]

POLITICAL_KEYWORDS = [
    "대통령", "국회", "정당", "여야", "국민의힘", "민주당", "조국혁신당",
    "개혁신당", "진보당", "탄핵", "정치권", "총선", "대선", "국정감사",
    "청와대", "여의도", "정치인", "의원", "선거", "정부여당", "야당",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BlogBot/1.0)"
}

WIKI_SUMMARY_URL = "https://ko.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_SEARCH_URL = "https://ko.wikipedia.org/w/api.php"
WIKI_EN_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


def _build_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"


def _is_political(title: str) -> bool:
    return any(kw in title for kw in POLITICAL_KEYWORDS)


def load_processed() -> dict:
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_processed(data: dict):
    os.makedirs(os.path.dirname(PROCESSED_PATH), exist_ok=True)
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _extract_names_from_title(title: str) -> list[str]:
    """기사 제목에서 인물 이름 후보를 추출한다.
    한국어 이름(2~4글자 한글), 영문 이름(First Last 패턴)을 잡는다."""
    candidates = []

    # 한국어 이름 패턴: 2~4글자 한글 (조사 앞에 오는 경우)
    ko_names = re.findall(r"([가-힣]{2,4})(?:씨|의|이|가|은|는|을|를|과|와|도|에|로|으로)", title)
    candidates.extend(ko_names)

    # 영문 이름 패턴: 대문자로 시작하는 2단어
    en_names = re.findall(r"([A-Z][a-z]+\s[A-Z][a-z]+)", title)
    candidates.extend(en_names)

    # 따옴표/괄호 속 이름 (짧은 것)
    quoted = re.findall(r"""['"\u201c\u201d]([가-힣A-Za-z\s]{2,10})['"\u201c\u201d]""", title)
    candidates.extend(quoted)

    return list(dict.fromkeys(candidates))  # 순서 유지 중복 제거


def _search_wikipedia_ko(name: str) -> dict | None:
    """한국어 위키피디아에서 인물 검색 후 요약 정보 반환."""
    # 검색으로 정확한 문서 제목 찾기
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srnamespace": "0",
        "srlimit": "3",
        "format": "json",
        "utf8": "1",
    }
    try:
        r = requests.get(WIKI_SEARCH_URL, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_title = results[0]["title"]
    except Exception:
        return None

    # 요약 API로 상세 정보 가져오기
    try:
        url = WIKI_SUMMARY_URL.format(title=quote(page_title))
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        # 인물 문서인지 확인 (description에 직업/역할 표현이 있는지)
        description = data.get("description", "")
        extract = data.get("extract", "")
        if not extract or len(extract) < 100:
            return None

        return {
            "title": page_title,
            "description": description,
            "extract": extract[:4000],  # Gemini 전달용 (너무 길면 자름)
            "thumbnail_url": (data.get("thumbnail") or {}).get("source", ""),
            "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "lang": "ko",
        }
    except Exception:
        return None


def _search_wikipedia_en(name: str) -> dict | None:
    """영어 위키피디아에서 인물 검색 (한국어 위키에 없을 때 폴백)."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srnamespace": "0",
        "srlimit": "3",
        "format": "json",
    }
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php", params=params, headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_title = results[0]["title"]
    except Exception:
        return None

    try:
        url = WIKI_EN_SUMMARY_URL.format(title=quote(page_title))
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        extract = data.get("extract", "")
        if not extract or len(extract) < 100:
            return None

        return {
            "title": page_title,
            "description": data.get("description", ""),
            "extract": extract[:4000],
            "thumbnail_url": (data.get("thumbnail") or {}).get("source", ""),
            "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "lang": "en",
        }
    except Exception:
        return None


def _collect_person_candidates() -> list[dict]:
    """구글 뉴스 RSS에서 인물 후보 이름을 뽑고, Wikipedia 데이터와 합쳐 반환."""
    seen_names: set[str] = set()
    candidates: list[dict] = []

    for query in SEARCH_QUERIES:
        url = _build_rss_url(query)
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            if _is_political(title):
                continue

            names = _extract_names_from_title(title)
            for name in names:
                if name in seen_names or len(name) < 2:
                    continue
                seen_names.add(name)

                # 한국어 Wikipedia 먼저 시도, 없으면 영어
                wiki = _search_wikipedia_ko(name) or _search_wikipedia_en(name)
                if not wiki:
                    continue

                candidates.append({
                    "name": name,
                    "news_title": title,
                    "news_link": entry.get("link", ""),
                    "wiki": wiki,
                })
                time.sleep(0.3)  # Wikipedia API 부하 방지

        time.sleep(1)

    return candidates


def collect_new_persons(max_items: int = 2) -> tuple[list[dict], dict]:
    """신규 인물만 골라 반환. (processed에 없는 인물 중 Wikipedia 정보가 충분한 것)"""
    processed = load_processed()
    candidates = _collect_person_candidates()

    new_items = []
    for person in candidates:
        name = person["name"]
        if name in processed:
            continue
        new_items.append(person)
        if len(new_items) >= max_items:
            break

    print(f"[Collector-Person] 후보 {len(candidates)}명 중 신규 {len(new_items)}명 선정")
    return new_items, processed
