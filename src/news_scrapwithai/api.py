"""
pywebview 백엔드 브리지 API 모듈 (api.py)
"""

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from news_scrapwithai.ai_reporter import NewsReportGenerator
from news_scrapwithai.config import DATA_DIR, REPORTS_DIR
from news_scrapwithai.scraper import NaverNewsCollector


class NewsAppApi:
    """프론트엔드 JavaScript와 비동기 통신하는 파이썬 백엔드 API 브리지"""

    def __init__(self) -> None:
        self.collector = NaverNewsCollector()
        self.reporter = NewsReportGenerator()

        # 최근 수집 및 분석 상태
        self.articles: List[Dict[str, Any]] = []
        self.last_csv_path: Optional[str] = None
        self.last_report: Optional[Dict[str, Any]] = None
        self.start_date_str: str = ""
        self.end_date_str: str = ""

        # 진행 상태 추적 딕셔너리
        self.status = {
            "is_running": False,
            "step": "idle",
            "progress": 0,
            "message": "준비 완료",
            "article_count": 0,
            "error": "",
        }

    def start_pipeline(
        self,
        start_date: str,
        end_date: str,
        query: str = "",  # IT/과학 전체 수집이 기본
        max_items: int = 30,
    ) -> Dict[str, Any]:
        """
        네이버 뉴스 IT/과학(sid1=105) 전체 수집 및 AI 보고서 생성 파이프라인
        """
        if self.status["is_running"]:
            return {"success": False, "error": "이미 다른 작업이 진행 중입니다."}

        self.start_date_str = start_date
        self.end_date_str = end_date

        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            dt_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception as e:
            return {"success": False, "error": f"날짜 형식 오류 (YYYY-MM-DD): {e}"}

        if dt_start > dt_end:
            return {"success": False, "error": "시작일이 종료일보다 늦을 수 없습니다."}

        self.status = {
            "is_running": True,
            "step": "scraping",
            "progress": 0,
            "message": "네이버 뉴스 [IT/과학] 섹션 기사 수집 시작...",
            "article_count": 0,
            "error": "",
        }

        thread = threading.Thread(
            target=self._run_pipeline_worker,
            args=(dt_start, dt_end, max_items),
            daemon=True,
        )
        thread.start()

        return {"success": True, "message": "작업이 시작되었습니다."}

    def _run_pipeline_worker(self, dt_start, dt_end, max_items: int) -> None:
        """백그라운드 워커 스레드"""
        try:
            # 1. 네이버 뉴스 [IT/과학] 섹션 기사 수집 및 크롤링
            def progress_callback(info: Dict[str, Any]):
                self.status["progress"] = info.get("progress", self.status["progress"])
                self.status["message"] = info.get("message", self.status["message"])
                if "count" in info:
                    self.status["article_count"] = info["count"]

            df_news = self.collector.collect_section_news(
                start_date=dt_start,
                end_date=dt_end,
                max_target=max_items,
                progress_callback=progress_callback,
            )

            if df_news.empty:
                self.status.update({
                    "is_running": False,
                    "step": "done",
                    "progress": 100,
                    "message": "지정된 날짜의 IT/과학 뉴스가 없습니다.",
                    "article_count": 0,
                })
                self.articles = []
                return

            # 2. CSV 저장
            csv_path = self.collector.save_csv(df_news, dt_start, dt_end)
            self.last_csv_path = str(csv_path)
            self.articles = df_news.to_dict(orient="records")

            # 3. gpt-5.6-luna 3대 카테고리 분석 보고서 생성
            self.status.update({
                "step": "reporting",
                "progress": 92,
                "message": f"IT/과학 기사 {len(df_news)}건 수집 완료! gpt-5.6-luna 3대 카테고리 분석 중...",
            })

            report_res = self.reporter.generate_report(
                articles=self.articles,
                start_date_str=self.start_date_str,
                end_date_str=self.end_date_str,
            )

            if not report_res.get("success"):
                self.status.update({
                    "is_running": False,
                    "step": "error",
                    "error": report_res.get("error", "AI 보고서 생성 실패"),
                    "message": "AI 보고서 생성 중 오류 발생",
                })
                return

            self.last_report = report_res

            # 4. 완료
            self.status.update({
                "is_running": False,
                "step": "done",
                "progress": 100,
                "message": f"🎉 전체 작업 완료! IT/과학 기사 {len(df_news)}건 수집 및 AI 보고서 저장 완료",
            })

        except Exception as e:
            self.status.update({
                "is_running": False,
                "step": "error",
                "error": str(e),
                "message": f"작업 중 예외 발생: {str(e)}",
            })

    def get_status(self) -> Dict[str, Any]:
        """프론트엔드 진행 상황 폴링"""
        return self.status

    def get_results(self) -> Dict[str, Any]:
        """수집 결과 데이터 및 보고서 반환"""
        return {
            "articles": self.articles,
            "csv_path": self.last_csv_path,
            "report": self.last_report,
            "period": f"{self.start_date_str} ~ {self.end_date_str}" if self.start_date_str != self.end_date_str else self.start_date_str,
        }

    def open_folder(self, folder_type: str) -> Dict[str, Any]:
        """폴더 열기 (data 또는 reports)"""
        target_dir = DATA_DIR if folder_type == "data" else REPORTS_DIR
        try:
            if os.name == "nt":
                os.startfile(str(target_dir))
            return {"success": True, "path": str(target_dir)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_file(self, file_path: str) -> Dict[str, Any]:
        """특정 파일 시스템 열기"""
        try:
            if os.name == "nt" and os.path.exists(file_path):
                os.startfile(file_path)
                return {"success": True}
            return {"success": False, "error": "파일을 찾을 수 없습니다."}
        except Exception as e:
            return {"success": False, "error": str(e)}
