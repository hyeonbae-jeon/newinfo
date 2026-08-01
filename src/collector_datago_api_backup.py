# -*- coding: utf-8 -*-
"""
Collector
---------
정책브리핑 RSS 서비스가 2026년 7월 1일부로 종료되어,
공공데이터포털(data.go.kr)의 공식 Open API로 보도자료를 수집합니다.

- API: 문화체육관광부_정책브리핑_보도자료_API
- 요청주소: http://apis.data.go.kr/1371000/pressReleaseService/pressReleaseList
- 사용하려면 data.go.kr 가입 + 이 API 활용신청(자동승인) 후 발급받은
  서비스키(인증키)를 DATA_GO_KR_SERVICE_KEY 환경변수/Secret으로 등록해야 합니다.

주의: 공공데이터포털 API마다 실제 응답 필드명이 조금씩 다르고 문서만으로는
100% 확신하기 어려워서, 이 코드는 item의 모든 필드를 유연하게 읽어들이고
[진단] 로그로 실제 필드 구조를 출력합니다. 처음 실행 후 로그를 보고
필드 매칭(TITLE_KEYS 등)을 다듬으면 됩니다.
"""

import hashlib
import json
import os
import xml.etree.ElementTree as ET

import requests

API_URL = "http://apis.data.go.kr/1371000/pressReleaseService/pressReleaseList"
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed.json")

# 실제 필드명을 확정하기 전까지, 이름에 아래 키워드가 포함된 필드를 후보로 사용
TITLE_KEYS = ["title", "제목", "sj"]
BODY_KEYS = ["content", "body", "내용", "cn"]
DATE_KEYS = ["date", "dt", "일자", "regdate", "ymd"]
AGENCY_KEYS = ["dept", "org", "agency", "부처", "ministry", "instt"]
ID_KEYS = ["id", "no", "seq", "nttid", "contentid"]


def _find_field(item: dict, keywords):
    """item(dict)의 key들 중, keywords 중 하나라도 포함된 첫 번째 값을 반환."""
    for key, value in item.items():
        key_lower = key.lower()
        if any(kw.lower() in key_lower for kw in keywords):
            return value
    return ""


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


def _make_unique_key(item: dict) -> str:
    """항목의 고유 식별자. id성 필드가 있으면 그걸 쓰고, 없으면 내용 해시로 대체."""
    id_value = _find_field(item, ID_KEYS)
    if id_value:
        return str(id_value)
    raw = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def fetch_raw_items(num_rows: int = 10, page_no: int = 1):
    """API를 호출해 item들을 dict 리스트로 반환 (필드명 그대로 보존)."""
    service_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")
    if not service_key:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY 환경변수가 설정되어 있지 않습니다.")

    params = {
        "serviceKey": service_key,
        "pageNo": page_no,
        "numOfRows": num_rows,
    }

    res = requests.get(API_URL, params=params, timeout=15)
    print(f"[진단] API 응답 상태코드: {res.status_code}")
    print(f"[진단] 응답 원문 앞부분(500자): {res.text[:500]}")
    res.raise_for_status()

    root = ET.fromstring(res.content)

    # 오류 응답(인증키 오류 등)인 경우를 대비한 확인
    result_code = root.findtext(".//resultCode")
    result_msg = root.findtext(".//resultMsg")
    if result_code and result_code != "00":
        print(f"[진단] API 오류 응답: resultCode={result_code}, resultMsg={result_msg}")
        return []

    items = []
    for item_el in root.iter("item"):
        item = {child.tag: (child.text or "").strip() for child in item_el}
        items.append(item)

    print(f"[진단] 파싱된 item 개수: {len(items)}")
    if items:
        print(f"[진단] 첫 item 필드 예시: {items[0]}")

    return items


def collect_new_releases(max_items: int = 5):
    """
    Open API에서 보도자료 목록을 가져와, 아직 처리하지 않은 것만 반환.
    반환 형식: [{title, link, published, agency, body}, ...]
    (link는 실제 URL이 없을 수도 있어, 대신 고유 식별자를 그대로 넣습니다)
    """
    processed = load_processed()

    try:
        raw_items = fetch_raw_items(num_rows=max_items * 2)  # 이미 처리한 것 걸러낼 여유분
    except requests.RequestException as e:
        print(f"[진단] API 요청 자체가 실패했습니다: {e}")
        return [], processed

    new_items = []
    for item in raw_items:
        unique_key = _make_unique_key(item)
        if unique_key in processed:
            continue

        title = _find_field(item, TITLE_KEYS) or "(제목 없음)"
        body = _find_field(item, BODY_KEYS)
        published = _find_field(item, DATE_KEYS)
        agency = _find_field(item, AGENCY_KEYS)

        if not body:
            # 본문 필드를 못 찾았으면, item 전체를 "키: 값" 형태로 덤프해서 대신 사용
            # (Gemini가 필요한 정보를 스스로 추려낼 수 있도록)
            body = "\n".join(f"{k}: {v}" for k, v in item.items() if v)

        new_items.append({
            "title": title,
            "link": unique_key,  # 실제 URL이 아닐 수 있음 (진단 후 개선 가능)
            "published": published,
            "agency": agency,
            "body": body,
        })

        if len(new_items) >= max_items:
            break

    return new_items, processed


if __name__ == "__main__":
    items, _ = collect_new_releases()
    print(f"신규 보도자료 {len(items)}건 발견")
    for it in items:
        print("-", it["title"])
