"""
IT/과학 뉴스 수집 및 AI 요약 보고서 생성기 메인 진입점
"""

import sys
from pathlib import Path
import webview

from news_scrapwithai.api import NewsAppApi
from news_scrapwithai.config import PROJECT_ROOT


def main() -> None:
    """pywebview 데스크톱 애플리케이션 시작 함수"""
    index_file = PROJECT_ROOT / "web" / "index.html"

    if not index_file.exists():
        print(f"[오류] UI 파일을 찾을 수 없습니다: {index_file}", file=sys.stderr)
        sys.exit(1)

    # JavaScript 통신 API 브리지 객체 생성
    api = NewsAppApi()

    # 1280x840 고해상도 모던 대시보드 윈도우 생성
    webview.create_window(
        title="IT/과학 뉴스 AI 브리핑 시스템 (네이버 뉴스 & gpt-5.6-luna)",
        url=str(index_file),
        js_api=api,
        width=1280,
        height=840,
        min_size=(980, 660),
        resizable=True,
    )

    # Windows WebView2 기반 웹뷰 실행
    webview.start(debug=False)


if __name__ == "__main__":
    main()
