# -*- coding: utf-8 -*-
"""
Image Finder (Pexels)
----------------------
무료 스톡사진 사이트 Pexels에서 키워드로 관련 사진을 검색합니다.
- 무료 API, 시간당 200회 / 월 20,000회 한도
- 키 발급: https://www.pexels.com/api/ (가입 후 즉시 발급)

Pexels 이용 약관상 사진을 쓸 때는 가능하면 출처(사진작가/Pexels) 표기를 해야 합니다.
"""

import os
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def search_photo(query: str, orientation: str = "landscape"):
    """
    query로 사진을 검색해 1장을 반환.
    반환: {"url": 이미지주소, "photographer": 작가명, "photographer_url": 작가페이지, "pexels_url": 사진페이지} 또는 None
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("[진단] PEXELS_API_KEY가 설정되어 있지 않아 이미지 삽입을 건너뜁니다.")
        return None

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "orientation": orientation}

    try:
        res = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except requests.RequestException as e:
        print(f"[진단] Pexels 요청 실패: {e}")
        return None

    photos = data.get("photos", [])
    if not photos:
        print(f"[진단] Pexels에서 '{query}' 검색 결과 없음")
        return None

    photo = photos[0]
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
