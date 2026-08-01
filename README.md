# 정부 정책 자동 블로그 봇 (gov-policy-blog-bot)

정책브리핑(korea.kr) 보도자료 RSS 서비스가 2026년 7월 1일부로 종료되어, 대신 **공공데이터포털(data.go.kr) Open API**로 매일 자동 수집 → 분석 → SEO 블로그 글 생성 → Blogger 초안 등록까지 처리하는 GitHub Actions 자동화 파이프라인입니다.

## 전체 흐름

```
[GitHub Actions 스케줄, 매일 09:00 KST]
        │
        ▼
collector.py   : 공공데이터포털 Open API(문화체육관광부_정책브리핑_보도자료_API)에서 신규 보도자료 수집
        │
        ▼
writer.py      : Gemini API(무료 티어) 호출 → SEO 블로그 JSON 생성
        │
        ▼
publisher.py   : Blogger API로 초안(draft) 등록
        │
        ▼
processed.json : 처리 완료 글 기록 (중복 방지) → 저장소에 자동 커밋
```

## 준비물 (6가지 Secret)

GitHub 저장소 **Settings > Secrets and variables > Actions > New repository secret**에서 아래 6개를 등록해야 합니다.

| Secret 이름 | 설명 | 발급 방법 |
|---|---|---|
| `DATA_GO_KR_SERVICE_KEY` | 보도자료 수집용 공공데이터포털 인증키 | 아래 "공공데이터포털 API 신청" 참고 |
| `GEMINI_API_KEY` | Gemini API 키 (무료 티어) | [Google AI Studio](https://aistudio.google.com/apikey)에서 발급 |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | 아래 "Blogger 연동 준비" 참고 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 보안 비밀 | 위와 동일 |
| `GOOGLE_REFRESH_TOKEN` | Blogger API 접근용 리프레시 토큰 | `get_refresh_token.py` 실행 결과 |
| `BLOGGER_BLOG_ID` | 내 Blogger 블로그의 ID(숫자) | 아래 참고 |

> **Gemini API 키 발급**: [Google AI Studio](https://aistudio.google.com/apikey)에 접속해 Google 계정으로 로그인 후 "Create API key" 버튼만 누르면 바로 발급됩니다. 별도 결제 등록 없이 무료 티어로 바로 사용 가능합니다.
>
> **무료 티어 주의사항**: 무료 티어는 분당/일일 요청 수 제한이 있고, Pro 계열 모델은 유료 전용입니다(2026년 기준 Flash·Flash-Lite 계열만 무료). 이 프로젝트는 기본적으로 `gemini-2.5-flash`를 사용하며, 한도가 자주 걸린다면 `src/writer.py`의 `MODEL_NAME`을 `gemini-2.5-flash-lite`로 바꾸고 `main.py`의 `MAX_ITEMS_PER_RUN`을 줄이세요. 정확한 최신 한도는 [ai.google.dev](https://ai.google.dev)에서 확인하는 걸 추천드립니다.

## 0. 공공데이터포털 API 신청 (최초 1회)

1. [data.go.kr](https://www.data.go.kr) 접속 후 회원가입/로그인
2. 검색창에 **"문화체육관광부_정책브리핑_보도자료_API"** 검색
3. 해당 API 상세페이지에서 **"활용신청"** 클릭
4. 활용 목적 등 간단히 입력 후 신청 (개발계정은 보통 **즉시 자동승인**)
5. 승인 후 **마이페이지 > 개발계정** 에서 발급된 **인증키(서비스키, Encoding 또는 Decoding 값)**를 확인
6. 이 값을 GitHub Secrets에 `DATA_GO_KR_SERVICE_KEY`로 등록

> 개발계정은 하루 요청 가능 트래픽이 제한(보통 1,000건)되어 있지만, 하루 한 번 몇 건만 가져오는 이 프로젝트에는 충분합니다.
>
> **참고**: 이 API의 실제 응답 필드명이 문서만으로는 100% 확정되지 않아서, `collector.py`는 처음 실행 시 `[진단]` 로그로 실제 응답 구조를 출력하도록 만들어져 있습니다. 첫 실행 후 로그를 확인해 필요하면 저에게 공유해주시면 필드 매칭을 다듬어드릴 수 있습니다.

## 1. Blogger 연동 준비 (최초 1회, 로컬 PC에서 진행)

1. [Google Cloud Console](https://console.cloud.google.com) 접속 → 새 프로젝트 생성
2. **API 및 서비스 > 라이브러리** → "Blogger API" 검색 후 사용 설정
3. **API 및 서비스 > OAuth 동의 화면** → User Type: 외부(External) 선택, 테스트 모드로 본인 계정만 추가해도 충분
4. **API 및 서비스 > 사용자 인증 정보 > 사용자 인증 정보 만들기 > OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 생성되면 client_id, client_secret 확인 가능
5. 로컬에 이 프로젝트를 내려받고 파이썬 환경에서:
   ```
   pip install google-auth-oauthlib
   ```
6. `get_refresh_token.py` 파일을 열어 `CLIENT_ID`, `CLIENT_SECRET`에 4번에서 받은 값 입력
7. 실행:
   ```
   python get_refresh_token.py
   ```
   브라우저가 열리며 구글 로그인 → 권한 허용 → 터미널에 `GOOGLE_REFRESH_TOKEN` 값 출력됨
8. 출력된 3개 값(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`)을 GitHub Secrets에 등록

## 2. Blogger 블로그 ID 확인

Blogger 관리 화면 접속 후 주소창 URL에서 확인하거나, 아래 API로 확인 가능합니다.
```
GET https://www.googleapis.com/blogger/v3/blogs/byurl?url=내블로그주소&key=API키
```
또는 Blogger 대시보드 > 설정 > 기본 항목의 "블로그 ID" 확인.

## 3. GitHub 저장소에 코드 올리기

1. GitHub에서 새 저장소 생성 (Private 추천 — API 키 관련 설정이 있으니)
2. 이 폴더 전체를 저장소에 push
3. 위 6개 Secret 등록
4. **Actions** 탭에서 `Auto Blog Publish` 워크플로우 확인 → `Run workflow` 버튼으로 수동 테스트 먼저 실행

## 4. 실행 주기 변경

`.github/workflows/publish.yml`의 `cron: "0 0 * * *"` 부분을 수정하면 됩니다.
(cron은 UTC 기준이라 한국시간 -9시간으로 계산해서 입력)

## 5. 운영 시 주의사항

- **처음엔 반드시 초안(draft) 모드로 운영**하세요. `src/main.py`의 `PUBLISH_AS_DRAFT = True`를 그대로 두고, Blogger에서 몇 개 글을 직접 검수한 뒤 문제없으면 `False`로 바꿔 자동 공개 발행하세요.
- `MAX_ITEMS_PER_RUN`으로 1회 실행당 처리 건수를 제한해 Gemini 무료 티어 요청 한도와 공공데이터포털 API 트래픽 한도를 조절할 수 있습니다.
- `collector.py`의 `TITLE_KEYS`, `BODY_KEYS`, `DATE_KEYS`, `AGENCY_KEYS`는 API 응답의 실제 필드명에 맞춰 조정이 필요할 수 있습니다. 처음 실행 후 `[진단]` 로그에 찍히는 "첫 item 필드 예시"를 보고 다듬으세요.
- 이미지 생성(`thumbnail_prompt`, `image_prompts`)은 현재 프롬프트만 생성하며, 실제 이미지 생성/업로드 연동은 포함되어 있지 않습니다. 필요하면 별도 이미지 생성 API 연동을 추가할 수 있습니다.

## 로컬 테스트 방법

```
pip install -r requirements.txt
export DATA_GO_KR_SERVICE_KEY=...
export GEMINI_API_KEY=...
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
export GOOGLE_REFRESH_TOKEN=...
export BLOGGER_BLOG_ID=...
python src/main.py
```
