"""
pywebview 백엔드 브리지 API 모듈 (api.py)
데이터베이스 연동 및 AI 비서 챗봇 실시간 지시 통신 지원
"""

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from news_scrapwithai.ai_reporter import NewsReportGenerator
from news_scrapwithai.config import DATA_DIR, REPORTS_DIR
from news_scrapwithai.database import NewsDatabase
from news_scrapwithai.scraper import NaverNewsCollector


class NewsAppApi:
    """프론트엔드 JavaScript와 비동기 통신하는 파이썬 백엔드 API 브리지"""

    def __init__(self) -> None:
        self.collector = NaverNewsCollector()
        self.reporter = NewsReportGenerator()
        self.db = NewsDatabase()

        # 최근 수집 및 분석 상태
        self.articles: List[Dict[str, Any]] = []
        self.last_csv_path: Optional[str] = None
        self.last_report: Optional[Dict[str, Any]] = None
        self.start_date_str: str = ""
        self.end_date_str: str = ""
        self.active_instruction: Optional[str] = None  # 이번 보고서 생성에 반영될 활성 지시사항

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
        query: str = "",
        max_items: int = 30,
    ) -> Dict[str, Any]:
        """
        네이버 뉴스 IT/과학 전체 수집 ➔ DB 적재(중복 자동 스킵) ➔ 사용자 지시 반영 AI 보고서 생성 파이프라인
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

            self.articles = df_news.to_dict(orient="records")

            # 2. 데이터베이스 영구 적재 (INSERT OR IGNORE 중복 방지)
            inserted, skipped = self.db.save_articles(self.articles)

            # 3. 엑셀 호환 CSV 저장 (호환성 유지)
            csv_path = self.collector.save_csv(df_news, dt_start, dt_end)
            self.last_csv_path = str(csv_path)

            # 4. 사용자 지시사항(챗봇 히스토리 및 활성 지시)을 종합한 AI 보고서 생성
            self.status.update({
                "step": "reporting",
                "progress": 90,
                "message": f"수집 완료(DB 신규 {inserted}건, 기존 {skipped}건)! AI 보고서 작성 중...",
            })

            chat_history = self.db.get_chat_history()
            current_instruction = self.active_instruction
            report_res = self.reporter.generate_report(
                articles=self.articles,
                start_date_str=self.start_date_str,
                end_date_str=self.end_date_str,
                chat_history=chat_history,
                active_instruction=current_instruction,
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
            # 활성 지시사항 소모 완료(Consumed) 처리
            self.active_instruction = None

            # 5. 생성된 보고서 및 다대다 매핑(report_articles) DB 저장
            article_links = [a.get("link") for a in self.articles if a.get("link")]
            report_id = self.db.save_report(
                title=f"IT/과학 뉴스 브리핑 ({report_res.get('period')})",
                period=report_res.get("period", ""),
                article_count=len(self.articles),
                user_instructions=report_res.get("user_instructions", ""),
                report_md=report_res.get("report_md", ""),
                file_path=report_res.get("file_path", ""),
                article_links=article_links,
            )
            report_res["db_report_id"] = report_id

            # 6. 전체 파이프라인 완료
            self.status.update({
                "is_running": False,
                "step": "done",
                "progress": 100,
                "message": f"🎉 완료! 기사 {len(df_news)}건 수집(신규 {inserted}건), DB 및 보고서 저장 완료",
            })

        except Exception as e:
            self.status.update({
                "is_running": False,
                "step": "error",
                "error": str(e),
                "message": f"작업 중 예외 발생: {str(e)}",
            })

    # --------------------------------------------------------------------------
    # 챗봇 대화 및 실시간 지시사항 API
    # --------------------------------------------------------------------------
    def send_chat(self, user_text: str) -> Dict[str, Any]:
        """사용자의 맞춤 지시사항 및 질문을 접수하고 AI 비서 피드백 생성 (활성 지시로 등록)"""
        text = user_text.strip() if user_text else ""
        if not text:
            return {"success": False, "error": "내용을 입력해주세요."}

        try:
            # 1. 사용자 메시지 DB 저장 및 활성 지시사항으로 등록
            self.db.add_chat_message("user", text)
            self.active_instruction = text

            # 2. AI 응답 생성
            history = self.db.get_chat_history()
            reply = self.reporter.chat_respond(
                user_message=text,
                chat_history=history[:-1],  # 방금 추가된 마지막 메시지 이전 히스토리
                current_article_count=len(self.articles),
            )

            # 3. AI 응답 DB 저장
            self.db.add_chat_message("assistant", reply)

            return {
                "success": True,
                "reply": reply,
                "history": self.db.get_chat_history(),
                "active_instruction": self.active_instruction,
            }
        except Exception as e:
            return {"success": False, "error": f"AI 비서 응답 실패: {str(e)}"}

    def clear_active_instruction(self) -> Dict[str, bool]:
        """반영 대기 중인 활성 지시사항 해제 (표준 3대 브리핑으로 복귀)"""
        self.active_instruction = None
        return {"success": True}

    def get_active_instruction(self) -> Dict[str, Any]:
        """현재 반영 대기 중인 활성 지시사항 반환"""
        return {"success": True, "active_instruction": self.active_instruction}

    def get_chat_history(self) -> Dict[str, Any]:
        """대화 히스토리 목록 반환"""
        return {"success": True, "history": self.db.get_chat_history()}

    def clear_chat_history(self) -> Dict[str, bool]:
        """대화 히스토리 및 활성 지시사항 초기화"""
        self.db.clear_chat_history()
        self.active_instruction = None
        return {"success": True}

    def get_db_stats(self) -> Dict[str, Any]:
        """데이터베이스 누적 통계 반환"""
        return self.db.get_stats()

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
            "db_stats": self.db.get_stats(),
            "active_instruction": self.active_instruction,
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
