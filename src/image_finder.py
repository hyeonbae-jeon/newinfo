# -*- coding: utf-8 -*-
"""
Image Finder (Pexels)
----------------------
무료 스톡사진 사이트 Pexels에서 키워드로 관련 사진을 검색합니다.
- 무료 API, 시간당 200회 / 월 20,000회 한도
- 키 발급: https://www.pexels.com/api/ (가입 후 즉시 발급)

같은 사진이 계속 반복돼서 나오는 것을 막기 위해, 검색 결과 여러 장 중
최근에 안 쓴 사진을 무작위로 골라 쓰고, 사용한 사진 ID를 기록해둡니다.

Pexels 이용 약관상 사진을 쓸 때는 가능하면 출처(사진작가/Pexels) 표기를 해야 합니다.
"""

import json
import os
import random
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
KOREA_HINT_KEYWORDS = ["korea", "korean", "seoul", "한국", "서울"]

RECENT_IMAGES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "recent_images.json")
RECENT_IMAGES_MAX = 200  # 최근 몇 장까지 "이미 썼음"으로 기억할지


def _load_recent_ids() -> set:
    if not os.path.exists(RECENT_IMAGES_PATH):
        return set()
    try:
        with open(RECENT_IMAGES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("recent_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_recent_ids(recent_ids: set):
    os.makedirs(os.path.dirname(RECENT_IMAGES_PATH), exist_ok=True)
    # 너무 오래된 것부터 잘라내서 파일이 무한정 커지지 않게
    trimmed = list(recent_ids)[-RECENT_IMAGES_MAX:]
    with open(RECENT_IMAGES_PATH, "w", encoding="utf-8") as f:
        json.dump({"recent_ids": trimmed}, f, ensure_ascii=False, indent=2)


def _ensure_korea_context(query: str) -> str:
    """검색어에 한국 관련 키워드가 없으면 'South Korea'를 덧붙여 보정."""
    query_lower = query.lower()
    if any(kw in query_lower for kw in KOREA_HINT_KEYWORDS):
        return query
    return f"{query}, South Korea"


def _search_pexels(query: str, orientation: str, api_key: str):
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 15, "orientation": orientation, "locale": "ko-KR"}
    try:
        res = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("photos", [])
    except requests.RequestException as e:
        print(f"[진단] Pexels 요청 실패: {e}")
        return []


def search_photo(query: str, orientation: str = "landscape"):
    """
    query로 사진을 검색해 1장을 반환 (최근에 안 쓴 사진 위주로 무작위 선택).
    반환: {"url": 이미지주소, "photographer": 작가명, "photographer_url": 작가페이지, "pexels_url": 사진페이지} 또는 None
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("[진단] PEXELS_API_KEY가 설정되어 있지 않아 이미지 삽입을 건너뜁니다.")
        return None

    query = _ensure_korea_context(query)
    print(f"[진단] Pexels 검색어: {query}")

    photos = _search_pexels(query, orientation, api_key)

    # 한국 맥락을 붙였더니 결과가 없으면, 원래 검색어로 한 번 더 시도
    if not photos:
        fallback_query = query.replace(", South Korea", "")
        if fallback_query != query:
            print(f"[진단] 한국 맥락 검색 결과 없음, 폴백 검색어로 재시도: {fallback_query}")
            photos = _search_pexels(fallback_query, orientation, api_key)

    if not photos:
        print(f"[진단] Pexels에서 '{query}' 검색 결과 없음")
        return None

    recent_ids = _load_recent_ids()

    # 최근에 안 쓴 사진들만 후보로 추리고, 다 썼던 거면 어쩔 수 없이 전체에서 선택
    fresh_candidates = [p for p in photos if str(p["id"]) not in recent_ids]
    candidates = fresh_candidates if fresh_candidates else photos

    photo = random.choice(candidates)

    recent_ids.add(str(photo["id"]))
    _save_recent_ids(recent_ids)

    return {
        "url": photo["src"]["large"],
        "photographer": photo.get("photographer", "Pexels"),
        "photographer_url": photo.get("photographer_url", "https://www.pexels.com"),
        "pexels_url": photo.get("url", "https://www.pexels.com"),
    }


def build_image_html(photo: dict, alt_text: str = "") -> str:
    """검색된 사진 정보로 출처 표기가 포함된 이미지 HTML을 생성."""
    if not photo:
        return ""
    return f"""
<figure style="margin:1.5em 0;text-align:center;">
  <img src="{photo['url']}" alt="{alt_text}" style="max-width:100%;height:auto;border-radius:8px;" />
  <figcaption style="font-size:0.85em;color:#888;margin-top:0.4em;">
    Photo by <a href="{photo['photographer_url']}" target="_blank" rel="noopener">{photo['photographer']}</a>
    on <a href="{photo['pexels_url']}" target="_blank" rel="noopener">Pexels</a>
  </figcaption>
</figure>
"""
