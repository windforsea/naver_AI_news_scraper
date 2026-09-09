"""
네이버 뉴스 IT/과학 카테고리(sid1=105) 전체 및 검색 수집기 (scraper.py)
"""

import email.utils
import html
import re
import time
from datetime import date, datetime, time as dtime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from news_scrapwithai.config import DATA_DIR, get_naver_credentials

# KST 타임존 (+09:00)
KST = timezone(timedelta(hours=9))

# 크롤링 요청 헤더
CRAWL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 고정 데이터프레임 컬럼 스키마
NEWS_COLUMNS = ["title", "content", "link", "originallink", "pubDate", "press"]


def clean_html_text(text: str) -> str:
    """HTML 엔티티 디코딩 및 태그 제거"""
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    return text.strip()


def fetch_article_details(link: str, fallback_description: str = "") -> Tuple[str, str]:
    """
    네이버 뉴스 상세 링크(n.news.naver.com) 본문 및 언론사 정적 크롤링
    """
    content = fallback_description
    press = "언론사"

    if not link:
        return content, press

    if "news.naver.com" not in link:
        try:
            domain = urlparse(link).netloc.replace("www.", "")
            press = domain.split(".")[0].upper()
        except Exception:
            press = "원문 언론사"
        return fallback_description, press

    try:
        res = requests.get(link, headers=CRAWL_HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. 언론사명 추출
            logo_tag = soup.select_one(".media_end_head_top_logo img")
            if logo_tag and logo_tag.get("alt"):
                press = logo_tag["alt"].strip()
            else:
                meta_press = soup.select_one("meta[property='og:article:author']")
                if meta_press and meta_press.get("content"):
                    press = meta_press["content"].strip()

            # 2. 기사 본문 추출
            body_tag = soup.select_one("#dic_area, #newsct_article")
            if body_tag:
                for tag in body_tag.find_all(["script", "style", "iframe", "noscript", "em"]):
                    tag.decompose()
                extracted_text = body_tag.get_text(separator="\n", strip=True)
                if extracted_text:
                    content = extracted_text
    except Exception:
        pass

    return content, press


class NaverNewsCollector:
    """네이버 뉴스 IT/과학(sid1=105) 섹션 전체 및 검색 API 수집기"""

    def __init__(self, delay: float = 0.15) -> None:
        self.delay = delay

    def collect_section_news(
        self,
        start_date: date,
        end_date: date,
        max_target: int = 30,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> pd.DataFrame:
        """
        네이버 뉴스 [IT/과학] (sid1=105) 섹션의 기사를 날짜별 최신순으로 직접 수집합니다.
        (사용자 지정 검색어가 아닌 IT/과학 카테고리 전체 기사 수집)
        """
        # 최신 날짜부터 과거 날짜 순으로 날짜 리스트 생성
        date_list: List[date] = []
        curr = end_date
        while curr >= start_date:
            date_list.append(curr)
            curr -= timedelta(days=1)

        results: List[Dict[str, Any]] = []
        seen_links = set()

        if progress_callback:
            progress_callback({
                "status": "start",
                "message": f"네이버 뉴스 [IT/과학] 카테고리 기사 수집 시작 ({start_date} ~ {end_date})",
                "progress": 5,
            })

        for cur_date in date_list:
            date_str = cur_date.strftime("%Y%m%d")
            page = 1
            max_pages_for_date = 10  # 날짜당 최대 10페이지 탐색 (1페이지당 20건)

            while page <= max_pages_for_date and len(results) < max_target:
                url = f"https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=105&date={date_str}&page={page}"
                try:
                    res = requests.get(url, headers=CRAWL_HEADERS, timeout=8)
                except Exception as e:
                    break

                if res.status_code != 200:
                    break

                soup = BeautifulSoup(res.text, "html.parser")
                items = soup.select(".list_body ul li")
                if not items:
                    break

                new_items_on_page = 0

                for li in items:
                    title_tag = li.select_one("dt:not(.photo) a") or li.select_one("dt a")
                    if not title_tag:
                        continue

                    title = clean_html_text(title_tag.get_text(strip=True))
                    link = title_tag.get("href", "")

                    # 중복 기사 스킵
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    new_items_on_page += 1

                    press_tag = li.select_one(".writing")
                    press = clean_html_text(press_tag.get_text(strip=True)) if press_tag else "언론사"

                    date_tag = li.select_one(".date")
                    time_snippet = clean_html_text(date_tag.get_text(strip=True)) if date_tag else ""
                    pub_date_display = f"{cur_date.strftime('%Y-%m-%d')} {time_snippet}".strip()

                    # 상세 본문 크롤링
                    content, extracted_press = fetch_article_details(link)
                    if extracted_press and extracted_press != "언론사":
                        press = extracted_press

                    time.sleep(self.delay)

                    results.append({
                        "title": title,
                        "content": content,
                        "link": link,
                        "originallink": link,
                        "pubDate": pub_date_display,
                        "press": press,
                    })

                    if progress_callback:
                        pct = min(90, int(10 + (len(results) / max_target) * 80))
                        progress_callback({
                            "status": "collecting",
                            "message": f"IT/과학 기사 수집 중 ({len(results)}/{max_target}건): {title[:20]}...",
                            "progress": pct,
                            "count": len(results),
                        })

                    if len(results) >= max_target:
                        break

                # 페이지 내 새로운 기사가 없으면 다음 날짜로 이동
                if new_items_on_page == 0:
                    break

                page += 1
                time.sleep(self.delay)

            if len(results) >= max_target:
                break

        df = pd.DataFrame(results, columns=NEWS_COLUMNS)

        if progress_callback:
            progress_callback({
                "status": "done",
                "message": f"IT/과학 카테고리 총 {len(df)}건 기사 수집 완료!",
                "progress": 95,
                "count": len(df),
            })

        return df

    def save_csv(self, df: pd.DataFrame, start_date: date, end_date: date) -> Path:
        """수집된 DataFrame을 utf-8-sig 인코딩 CSV로 저장"""
        if start_date == end_date:
            date_str = start_date.strftime("%Y%m%d")
        else:
            date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        filename = f"IT과학_뉴스_{date_str}.csv"
        file_path = DATA_DIR / filename
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        return file_path
