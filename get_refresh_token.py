# -*- coding: utf-8 -*-
"""
get_refresh_token.py
---------------------
Blogger API를 GitHub Actions(서버 환경)에서 자동으로 쓰려면
'refresh_token'이 필요합니다. 이 스크립트는 최초 1회, 본인 PC에서
직접 실행해서 refresh_token을 발급받는 용도입니다.

사전 준비:
1. Google Cloud Console(console.cloud.google.com)에서 프로젝트 생성
2. "API 및 서비스 > 라이브러리"에서 Blogger API 사용 설정
3. "API 및 서비스 > OAuth 동의 화면" 구성 (테스트 모드로 충분)
4. "사용자 인증 정보 > OAuth 클라이언트 ID 만들기" -> 애플리케이션 유형: 데스크톱 앱
5. 다운로드한 client_id, client_secret을 아래 CLIENT_ID / CLIENT_SECRET에 입력

실행: python get_refresh_token.py
-> 브라우저가 열리며 구글 로그인 -> 권한 허용
-> 터미널에 refresh_token이 출력됨 -> 이 값을 GitHub Secrets에 저장
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/blogger"]

CLIENT_ID = "여기에_발급받은_클라이언트_ID_입력"
CLIENT_SECRET = "여기에_발급받은_클라이언트_보안비밀_입력"

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n===== 아래 값을 GitHub Secrets에 등록하세요 =====")
    print("GOOGLE_CLIENT_ID     =", CLIENT_ID)
    print("GOOGLE_CLIENT_SECRET =", CLIENT_SECRET)
    print("GOOGLE_REFRESH_TOKEN =", creds.refresh_token)
