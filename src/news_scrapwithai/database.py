"""
SQLite 데이터베이스 관리 모듈 (database.py)
기사(articles), 보고서(reports), 매핑(report_articles), 대화(chat_messages) 테이블 관리
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from news_scrapwithai.config import DATA_DIR

DB_PATH = DATA_DIR / "news.db"


class NewsDatabase:
    """SQLite 기반 뉴스 아카이브 및 AI 브리핑 데이터베이스 관리자"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """데이터베이스 커넥션 생성 (Row 팩토리 활성화)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 외래키 제약조건 활성화
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_tables(self) -> None:
        """핵심 4대 테이블 및 인덱스 초기화"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 뉴스 기사 마스터 테이블 (link 고유키로 중복 방지)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT,
                    link TEXT UNIQUE,
                    originallink TEXT,
                    pub_date TEXT,
                    press TEXT,
                    category TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. 인덱스 생성 (날짜 및 카테고리 검색 가속)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_pubdate ON articles(pub_date);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
            """)

            # 3. AI 보고서 마스터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    period TEXT NOT NULL,
                    article_count INTEGER DEFAULT 0,
                    user_instructions TEXT,
                    report_md TEXT NOT NULL,
                    file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. 보고서 - 기사 간 다대다(N:M) 연결 테이블 (Junction Table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS report_articles (
                    report_id INTEGER,
                    article_id INTEGER,
                    PRIMARY KEY (report_id, article_id),
                    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
                );
            """)

            # 5. 사용자 - AI 챗봇 실시간 지시 및 대화 이력 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()

    def save_articles(self, articles: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        수집된 기사 리스트를 저장 (INSERT OR IGNORE를 통한 중복 자동 스킵)
        :return: (신규 저장된 기사 수, 중복되어 건너뛴 기사 수)
        """
        if not articles:
            return 0, 0

        inserted_count = 0
        skipped_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for art in articles:
                title = art.get("title", "")
                content = art.get("content", "")
                link = art.get("link") or art.get("originallink", "")
                orig = art.get("originallink", "")
                pub_date = art.get("pubDate", "")
                press = art.get("press", "언론사")
                category = art.get("category", "")

                cursor.execute("""
                    INSERT OR IGNORE INTO articles (title, content, link, originallink, pub_date, press, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (title, content, link, orig, pub_date, press, category))

                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1

            conn.commit()

        return inserted_count, skipped_count

    def save_report(
        self,
        title: str,
        period: str,
        article_count: int,
        user_instructions: str,
        report_md: str,
        file_path: str,
        article_links: List[str],
    ) -> int:
        """보고서를 저장하고 포함된 기사들을 report_articles에 매핑"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. reports 테이블 삽입
            cursor.execute("""
                INSERT INTO reports (title, period, article_count, user_instructions, report_md, file_path)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (title, period, article_count, user_instructions, report_md, file_path))
            report_id = cursor.lastrowid

            # 2. 링크를 기반으로 article_id들을 찾아 매핑 테이블에 저장
            if article_links and report_id:
                placeholders = ",".join("?" for _ in article_links)
                cursor.execute(f"SELECT id, link FROM articles WHERE link IN ({placeholders})", article_links)
                rows = cursor.fetchall()
                for r in rows:
                    cursor.execute("""
                        INSERT OR IGNORE INTO report_articles (report_id, article_id)
                        VALUES (?, ?);
                    """, (report_id, r["id"]))

            conn.commit()
            return report_id or 0

    def add_chat_message(self, role: str, content: str) -> None:
        """챗봇 대화 메시지 기록"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (role, content)
                VALUES (?, ?);
            """, (role, content))
            conn.commit()

    def get_chat_history(self, limit: int = 50) -> List[Dict[str, str]]:
        """최근 챗봇 대화 히스토리 반환"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM chat_messages
                ORDER BY id ASC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def clear_chat_history(self) -> None:
        """챗봇 대화 히스토리 초기화"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages;")
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """데이터베이스 누적 요약 통계"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM articles;")
            total_articles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM reports;")
            total_reports = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(collected_at) FROM articles;")
            last_collected = cursor.fetchone()[0] or "-"

            return {
                "total_articles": total_articles,
                "total_reports": total_reports,
                "last_collected": last_collected,
            }
