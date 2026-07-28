# 정부 정책 자동 블로그 봇 (gov-policy-blog-bot)

정책브리핑(korea.kr) 보도자료를 매일 자동으로 수집 → 분석 → SEO 블로그 글 생성 → Blogger 초안 등록까지 처리하는 GitHub Actions 자동화 파이프라인입니다.

## 전체 흐름

```
[GitHub Actions 스케줄, 매일 09:00 KST]
        │
        ▼
collector.py   : korea.kr RSS에서 신규 보도자료 감지 + 원문 크롤링
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

## 준비물 (5가지 Secret)

GitHub 저장소 **Settings > Secrets and variables > Actions > New repository secret**에서 아래 5개를 등록해야 합니다.

| Secret 이름 | 설명 | 발급 방법 |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API 키 (무료 티어) | [Google AI Studio](https://aistudio.google.com/apikey)에서 발급 |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | 아래 "Blogger 연동 준비" 참고 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 보안 비밀 | 위와 동일 |
| `GOOGLE_REFRESH_TOKEN` | Blogger API 접근용 리프레시 토큰 | `get_refresh_token.py` 실행 결과 |
| `BLOGGER_BLOG_ID` | 내 Blogger 블로그의 ID(숫자) | 아래 참고 |

> **Gemini API 키 발급**: [Google AI Studio](https://aistudio.google.com/apikey)에 접속해 Google 계정으로 로그인 후 "Create API key" 버튼만 누르면 바로 발급됩니다. 별도 결제 등록 없이 무료 티어로 바로 사용 가능합니다.
>
> **무료 티어 주의사항**: 무료 티어는 분당/일일 요청 수 제한이 있고, Pro 계열 모델은 유료 전용입니다(2026년 기준 Flash·Flash-Lite 계열만 무료). 이 프로젝트는 기본적으로 `gemini-2.5-flash`를 사용하며, 한도가 자주 걸린다면 `src/writer.py`의 `MODEL_NAME`을 `gemini-2.5-flash-lite`로 바꾸고 `main.py`의 `MAX_ITEMS_PER_RUN`을 줄이세요. 정확한 최신 한도는 [ai.google.dev](https://ai.google.dev)에서 확인하는 걸 추천드립니다.

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
3. 위 5개 Secret 등록
4. **Actions** 탭에서 `Auto Blog Publish` 워크플로우 확인 → `Run workflow` 버튼으로 수동 테스트 먼저 실행

## 4. 실행 주기 변경

`.github/workflows/publish.yml`의 `cron: "0 0 * * *"` 부분을 수정하면 됩니다.
(cron은 UTC 기준이라 한국시간 -9시간으로 계산해서 입력)

## 5. 운영 시 주의사항

- **처음엔 반드시 초안(draft) 모드로 운영**하세요. `src/main.py`의 `PUBLISH_AS_DRAFT = True`를 그대로 두고, Blogger에서 몇 개 글을 직접 검수한 뒤 문제없으면 `False`로 바꿔 자동 공개 발행하세요.
- `MAX_ITEMS_PER_RUN`으로 1회 실행당 처리 건수를 제한해 Gemini 무료 티어 요청 한도 초과와 크롤링 부하를 조절할 수 있습니다.
- `collector.py`의 본문 추출 선택자(`CONTENT_SELECTORS`)는 korea.kr 페이지 구조에 따라 조정이 필요할 수 있습니다. 실제 페이지 HTML을 열어 본문이 들어있는 태그를 확인 후 필요시 선택자를 추가/수정하세요.
- 이미지 생성(`thumbnail_prompt`, `image_prompts`)은 현재 프롬프트만 생성하며, 실제 이미지 생성/업로드 연동은 포함되어 있지 않습니다. 필요하면 별도 이미지 생성 API 연동을 추가할 수 있습니다.

## 로컬 테스트 방법

```
pip install -r requirements.txt
export GEMINI_API_KEY=...
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
export GOOGLE_REFRESH_TOKEN=...
export BLOGGER_BLOG_ID=...
python src/main.py
```
