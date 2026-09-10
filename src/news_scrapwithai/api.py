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

    def start_collect(
        self,
        start_date: str,
        end_date: str,
        max_items: int = 30,
    ) -> Dict[str, Any]:
        """
        [1단계: 기사 수집 및 DB 적재] 네이버 뉴스 IT/과학(섹션 105) 기사만 수집하여 SQLite DB 및 CSV에 저장
        """
        if self.status["is_running"]:
            return {"success": False, "error": "이미 다른 작업이 진행 중입니다."}

        self.start_date_str = start_date
        self.end_date_str = end_date
        self.last_report = None

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
            target=self._run_collect_worker,
            args=(dt_start, dt_end, max_items),
            daemon=True,
        )
        thread.start()

        return {"success": True, "message": "기사 수집이 시작되었습니다."}

    def _run_collect_worker(self, dt_start, dt_end, max_items: int) -> None:
        """기사 수집 전용 백그라운드 워커 (AI 호출 없음)"""
        try:
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
                    "message": "지정된 날짜에 수집된 IT/과학 뉴스가 없습니다.",
                    "article_count": 0,
                })
                self.articles = []
                return

            self.articles = df_news.to_dict(orient="records")

            # DB 영구 적재 (INSERT OR IGNORE)
            inserted, skipped = self.db.save_articles(self.articles)

            # CSV 저장
            csv_path = self.collector.save_csv(df_news, dt_start, dt_end)
            self.last_csv_path = str(csv_path)

            self.status.update({
                "is_running": False,
                "step": "done",
                "progress": 100,
                "message": f"🎉 기사 {len(df_news)}건 수집 완료 (DB 신규 {inserted}건, 기존 중복 {skipped}건)",
                "article_count": len(self.articles),
            })

        except Exception as e:
            self.status.update({
                "is_running": False,
                "step": "error",
                "error": str(e),
                "message": f"기사 수집 중 예외 발생: {str(e)}",
            })

    def start_report(
        self,
        start_date: str,
        end_date: str,
        max_items: int = 30,
    ) -> Dict[str, Any]:
        """
        [2단계: AI 보고서 생성]
        선택된 날짜의 기사가 DB에 있으면 즉시 읽어오고, 없으면 수집하여 DB 적재 후 보고서 생성
        """
        if self.status["is_running"]:
            return {"success": False, "error": "이미 다른 작업이 진행 중입니다."}

        self.start_date_str = start_date
        self.end_date_str = end_date
        self.last_report = None

        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            dt_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception as e:
            return {"success": False, "error": f"날짜 형식 오류 (YYYY-MM-DD): {e}"}

        if dt_start > dt_end:
            return {"success": False, "error": "시작일이 종료일보다 늦을 수 없습니다."}

        self.status = {
            "is_running": True,
            "step": "reporting",
            "progress": 5,
            "message": "DB 아카이브 확인 및 AI 보고서 준비 중...",
            "article_count": 0,
            "error": "",
        }

        thread = threading.Thread(
            target=self._run_report_worker,
            args=(dt_start, dt_end, max_items),
            daemon=True,
        )
        thread.start()

        return {"success": True, "message": "보고서 생성이 시작되었습니다."}

    def _run_report_worker(self, dt_start, dt_end, max_items: int) -> None:
        """AI 보고서 생성 백그라운드 워커 (DB 우선 캐시 / 미존재 시 자동 수집 및 DB 저장 후 작성)"""
        try:
            # 1. DB에서 해당 기간 기사 우선 조회 (Cache-First)
            db_articles = self.db.get_articles_by_date_range(self.start_date_str, self.end_date_str, max_items)

            if db_articles and len(db_articles) > 0:
                self.articles = db_articles
                self.status["progress"] = 30
                self.status["message"] = f"DB에서 기사 {len(db_articles)}건을 즉시 로드했습니다! AI 보고서 작성 중..."
            else:
                # 2. DB에 기사가 없으면 네이버 뉴스에서 자동 수집 후 DB 적재
                self.status.update({
                    "step": "scraping",
                    "progress": 10,
                    "message": "DB에 해당 기간 기사가 없어 네이버 뉴스 수집을 먼저 진행합니다...",
                })

                def progress_callback(info: Dict[str, Any]):
                    pct = min(60, int(10 + (info.get("progress", 0) * 0.5)))
                    self.status["progress"] = pct
                    self.status["message"] = info.get("message", self.status["message"])

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
                        "message": "해당 날짜에 수집된 기사가 없어 보고서를 생성할 수 없습니다.",
                        "article_count": 0,
                    })
                    self.articles = []
                    return

                self.articles = df_news.to_dict(orient="records")
                inserted, skipped = self.db.save_articles(self.articles)
                csv_path = self.collector.save_csv(df_news, dt_start, dt_end)
                self.last_csv_path = str(csv_path)

            # 3. AI 보고서 작성
            self.status.update({
                "step": "reporting",
                "progress": 70,
                "message": f"기사 {len(self.articles)}건 종합 및 gpt-5.6-luna 브리핑 보고서 작성 중...",
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
            self.active_instruction = None  # 지시사항 1회 소모 완료

            # 4. 생성된 보고서 및 다대다 매핑 DB 저장
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

            self.status.update({
                "is_running": False,
                "step": "done",
                "progress": 100,
                "message": f"🎉 AI 브리핑 보고서 작성 완료! ({len(self.articles)}건 기사 분석)",
            })

        except Exception as e:
            self.status.update({
                "is_running": False,
                "step": "error",
                "error": str(e),
                "message": f"보고서 생성 중 예외 발생: {str(e)}",
            })

    def start_pipeline(
        self,
        start_date: str,
        end_date: str,
        query: str = "",
        max_items: int = 30,
    ) -> Dict[str, Any]:
        """기존 파이프라인 호환용 래퍼 (보고서 생성 실행)"""
        return self.start_report(start_date, end_date, max_items)

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
