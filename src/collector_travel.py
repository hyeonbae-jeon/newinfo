# -*- coding: utf-8 -*-
"""
Collector (여행 코스 - Wikipedia 기반)
----------------------------------------
여행지명으로 Wikipedia API를 호출해 기본 정보와 주요 관광지 데이터를 수집한다.
한국어 Wikipedia 우선, 없으면 영어 Wikipedia 폴백.
"""

import os
import time
from urllib.parse import quote

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BlogBot/1.0)"}
WIKI_KO_SEARCH = "https://ko.wikipedia.org/w/api.php"
WIKI_KO_SUMMARY = "https://ko.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_EN_SEARCH = "https://en.wikipedia.org/w/api.php"
WIKI_EN_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


def _search_wiki(name: str, lang: str = "ko") -> str | None:
    """위키피디아 검색 → 가장 관련성 높은 문서 제목 반환."""
    base = WIKI_KO_SEARCH if lang == "ko" else WIKI_EN_SEARCH
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
        r = requests.get(base, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
        return results[0]["title"] if results else None
    except Exception:
        return None


def _fetch_summary(title: str, lang: str = "ko") -> dict | None:
    """위키피디아 요약 API → 본문 추출."""
    url_tmpl = WIKI_KO_SUMMARY if lang == "ko" else WIKI_EN_SUMMARY
    try:
        r = requests.get(
            url_tmpl.format(title=quote(title)),
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        extract = data.get("extract", "")
        if not extract or len(extract) < 100:
            return None
        return {
            "title": title,
            "description": data.get("description", ""),
            "extract": extract[:5000],
            "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "lang": lang,
        }
    except Exception:
        return None


def _fetch_wiki_sections(title: str, lang: str = "ko") -> str:
    """위키피디아 전체 본문에서 관광지·볼거리 관련 섹션 추출."""
    base = WIKI_KO_SEARCH if lang == "ko" else WIKI_EN_SEARCH
    params = {
        "action": "query",
        "prop": "extracts",
        "titles": title,
        "exsentences": "60",
        "exlimit": "1",
        "explaintext": "1",
        "format": "json",
        "utf8": "1",
    }
    try:
        r = requests.get(base, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            return page.get("extract", "")[:6000]
    except Exception:
        pass
    return ""


def collect_destination(destination: str, destination_en: str) -> dict:
    """
    여행지 정보를 Wikipedia에서 수집해 반환.

    반환 dict:
      - summary: 여행지 요약 (한글 또는 영문)
      - full_text: 관광지·명소 관련 본문
      - wiki_url: Wikipedia 링크
      - lang: 수집된 언어
    """
    # 한국어 Wikipedia 먼저 시도
    ko_title = _search_wiki(destination, lang="ko")
    if ko_title:
        summary = _fetch_summary(ko_title, lang="ko")
        if summary:
            full_text = _fetch_wiki_sections(ko_title, lang="ko")
            summary["full_text"] = full_text
            print(f"[Collector-Travel] 한국어 Wikipedia 수집 완료: {ko_title}")
            return summary

    # 영어 Wikipedia 폴백
    time.sleep(0.5)
    en_title = _search_wiki(destination_en or destination, lang="en")
    if en_title:
        summary = _fetch_summary(en_title, lang="en")
        if summary:
            full_text = _fetch_wiki_sections(en_title, lang="en")
            summary["full_text"] = full_text
            print(f"[Collector-Travel] 영어 Wikipedia 수집 완료: {en_title}")
            return summary

    print(f"[Collector-Travel] Wikipedia 데이터 없음: {destination}")
    return {
        "title": destination,
        "description": "",
        "extract": "",
        "full_text": "",
        "wiki_url": "",
        "lang": "none",
    }
