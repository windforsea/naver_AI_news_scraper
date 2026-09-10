"""
OpenAI gpt-5.6-luna 기반 IT/과학 뉴스 분석, 사용자 지시 챗봇 및 마크다운 보고서 생성 모듈 (ai_reporter.py)
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from openai import OpenAI

from news_scrapwithai.config import REPORTS_DIR, get_openai_api_key


class NewsReportGenerator:
    """수집된 뉴스 기사를 3대 카테고리로 분류하고 사용자의 맞춤 지시사항을 반영하여 보고서를 작성하는 AI 생성기"""

    def __init__(self, model_name: str = "gpt-5.6-luna") -> None:
        api_key = get_openai_api_key()
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def chat_respond(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
        current_article_count: int = 0,
    ) -> str:
        """
        사용자가 챗봇에 입력한 보고서 작성 방향성, 강조 요청, 특이 지시사항에 대해 피드백하고 수용하는 대화 메서드
        """
        system_instructions = (
            "당신은 글로벌 IT/과학 기술 정책 분석가이자 AI 브리핑 수석 어시스턴트입니다. "
            "사용자가 전달하는 보고서 작성 방향, 특정 기업/기술 집중 조명, 시사점 관점(투자, 보안, 정책 등) "
            "추가 지시사항을 정확하게 경청하고 수용하세요.\n"
            "당신이 수용한 모든 요구사항은 사용자가 [보고서 생성]을 실행할 때 공식 마크다운 보고서에 100% 직접 반영됩니다.\n"
            "사용자에게 어떤 관점으로 보고서에 반영할 것인지 신뢰감 있고 전문적인 어조(한국어 경어체)로 명확하고 간결하게 답변하세요.\n"
            f"(현재 수집된 기사 수: {current_article_count}건)"
        )

        # 히스토리에 시스템 인스트럭션과 사용자 입력 패키징
        messages_input = []
        for msg in chat_history:
            messages_input.append({"role": msg["role"], "content": msg["content"]})
        messages_input.append({"role": "user", "content": user_message})

        try:
            response = self.client.responses.create(
                model=self.model_name,
                instructions=system_instructions,
                input=messages_input,
            )
            return response.output_text.strip()
        except Exception as e:
            return f"응답 생성 중 오류가 발생했습니다: {str(e)}"

    def generate_report(
        self,
        articles: List[Dict[str, Any]],
        start_date_str: str,
        end_date_str: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        수집된 기사들과 사용자의 챗봇 지시사항(chat_history)을 종합하여 마크다운 보고서 생성
        """
        if not articles:
            return {
                "success": False,
                "error": "분석할 뉴스 기사 데이터가 없습니다.",
            }

        now_dt = datetime.now()
        created_at_str = now_dt.strftime("%Y년 %m월 %d일 %H시 %M분")
        period_display = (
            start_date_str if start_date_str == end_date_str else f"{start_date_str} ~ {end_date_str}"
        )

        # 1. 기사 본문 컨텍스트 구성
        articles_context_blocks = []
        for idx, art in enumerate(articles, start=1):
            title = art.get("title", "")
            press = art.get("press", "언론사")
            link = art.get("link") or art.get("originallink", "")
            content = art.get("content", "")
            content_snippet = content[:1200] if len(content) > 1200 else content

            block = (
                f"[기사 {idx}]\n"
                f"- 제목: {title}\n"
                f"- 언론사: {press}\n"
                f"- 링크: {link}\n"
                f"- 본문 내용:\n{content_snippet}\n"
            )
            articles_context_blocks.append(block)

        articles_text = "\n".join(articles_context_blocks)

        # 2. 사용자의 챗봇 지시사항(Human-in-the-loop) 종합
        user_instructions_summary = ""
        user_notes_block = ""
        if chat_history:
            user_instructions_summary = "; ".join([
                msg["content"] for msg in chat_history if msg.get("role") == "user"
            ])
            user_notes_block = "\n[사용자 실시간 맞춤 요청 및 지시사항 (Human Feedback)]:\n"
            for msg in chat_history:
                role_kr = "사용자 요청" if msg.get("role") == "user" else "AI 비서 피드백"
                user_notes_block += f"- {role_kr}: {msg.get('content')}\n"
        else:
            user_instructions_summary = "기본 표준 분석 (추가 지시 없음)"
            user_notes_block = "\n[사용자 맞춤 요청사항]: 표준 IT/과학 종합 브리핑 기준 작성\n"

        # 3. 시스템 프롬프트
        system_instructions = (
            "당신은 글로벌 IT/과학 기술 정책 연구원이자 수석 테크 저널리스트입니다. "
            "제공된 뉴스 기사들과 사용자의 맞춤 지시사항을 정밀하게 종합하여 공식 브리핑용 고품질 마크다운(.md) 보고서를 작성하세요.\n\n"
            "반드시 아래 3대 카테고리로 명확하게 분류하여 정리해야 합니다:\n"
            "1. 🚀 [AI 긍정]: 인공지능 관련 긍정적 뉴스, 성능 혁신, 버전업/신기술 공개, 산업 적용, 생산성 향상 등\n"
            "2. ⚠️ [AI 부정]: 인공지능 관련 부작용, 보안 위협/해킹, 딥페이크 오남용, 저작권/윤리 분쟁, 규제 논의 등\n"
            "3. 🔬 [기타 과학기술]: AI가 아닌 일반 IT 및 첨단 과학기술 (우주항공, 양자컴퓨터, 반도체 공정, 바이오/의학, 신소재 등)\n\n"
            "작성 원칙:\n"
            "- 사용자가 전달한 맞춤 요청(지시사항)이 있는 경우, 해당 관점을 각 카테고리의 시사점 및 종합 총평에 최우선적으로 반영하세요.\n"
            "- 각 기사별로 [제목(클릭 가능한 마크다운 링크 형식)] 언론사, '핵심 요약(3줄 불릿)', '산업적·기술적 시사점'을 작성하세요.\n"
            "- 특정 카테고리에 해당하는 기사가 없다면 '해당 기간 내 주요 이슈 없음'으로 간결히 명시하세요.\n"
            "- 문서 시작 부분에 [📊 핵심 총평 (Executive Summary)]을 작성하고, 사용자 지시사항이 반영된 포인트를 짚어주세요.\n"
            "- 문서 끝 부분에 [💡 종합 시사점 및 미래 전망]을 작성하세요.\n"
            "- 신뢰감 있고 격조 높은 한국어 경어체(~합니다, ~분석됩니다)를 사용하세요."
        )

        # 4. 사용자 프롬프트
        user_prompt = f"""[분석 기준 정보]
- 수집 및 분석 기간: {period_display}
- 총 수집 기사 건수: {len(articles)}건
- 분석 요청 일시: {created_at_str}
{user_notes_block}

[수집된 IT/과학 기사 원문 목록]
{articles_text}

위 기사들과 사용자 요청사항을 완벽히 반영하여 가독성이 뛰어난 전문 마크다운 보고서를 작성해 주세요.
보고서 제목은 '# 📡 [IT/과학 트렌드 브리핑] {period_display} 기술 동향 보고서' 로 시작해 주세요.
"""

        try:
            # 5. OpenAI Responses API 호출 (gpt-5.6-luna)
            response = self.client.responses.create(
                model=self.model_name,
                instructions=system_instructions,
                input=user_prompt,
            )
            report_md = response.output_text.strip()

            # 6. 마크다운 파일 저장
            file_date_str = (
                start_date_str.replace("-", "")
                if start_date_str == end_date_str
                else f"{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}"
            )
            filename = f"IT_과학_뉴스보고서_{file_date_str}.md"
            file_path = REPORTS_DIR / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_md)

            return {
                "success": True,
                "report_md": report_md,
                "file_path": str(file_path),
                "filename": filename,
                "created_at": created_at_str,
                "period": period_display,
                "article_count": len(articles),
                "user_instructions": user_instructions_summary,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"AI 보고서 생성 실패: {str(e)}",
            }
