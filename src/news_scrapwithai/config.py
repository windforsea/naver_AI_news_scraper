"""
환경 설정 및 인증 정보 관리 모듈 (config.py)
"""

import os
from pathlib import Path
from typing import Dict, Tuple
from dotenv import find_dotenv, load_dotenv

# 프로젝트 루트 디렉터리
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 데이터 및 보고서 저장 경로
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

# 디렉터리 자동 생성
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def load_environment() -> None:
    """프로젝트 루트의 .env 파일 로드"""
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        dotenv_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=True)


def get_naver_credentials() -> Tuple[str, Dict[str, str]]:
    """
    네이버 API 키를 로드하고 NCP API HUB 또는 Developers 규격에 맞는 URL과 헤더 반환
    """
    load_environment()

    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise ValueError(".env 파일에 NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 설정되어 있지 않습니다.")

    # 네이버 클라우드 플랫폼(NAVER API HUB) 판별 (10자리 소문자/숫자 조합)
    if len(client_id) == 10 and client_id.isalnum() and not any(c.isupper() for c in client_id):
        api_url = "https://naverapihub.apigw.ntruss.com/search/v1/news"
        headers = {
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
        }
    else:
        api_url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }

    return api_url, headers


def get_openai_api_key() -> str:
    """OpenAI API 키 반환"""
    load_environment()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(".env 파일에 OPENAI_API_KEY가 설정되어 있지 않습니다.")
    return api_key
