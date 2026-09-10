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
        active_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        수집된 기사들과 사용자의 맞춤 지시사항을 종합하여 마크다운 보고서 생성
        - 기본 모드(지시사항 없음): [AI 긍정 / AI 부정 / 기타 과학기술] 3대 프레임워크
        - 맞춤 모드(지시사항 있음): 사용자 요청 주제를 관통하는 테마 중심 유연한 섹션 구성
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

        # 2. 사용자 지시사항 유무에 따른 듀얼 모드 분기
        instruction_text = (active_instruction or "").strip()
        if not instruction_text and chat_history:
            # chat_history 중 마지막 user 메시지가 있다면 그것을 활용
            user_msgs = [m["content"] for m in chat_history if m.get("role") == "user"]
            if user_msgs:
                instruction_text = user_msgs[-1].strip()

        is_custom_mode = bool(instruction_text)
        report_mode = "custom" if is_custom_mode else "standard"

        if is_custom_mode:
            # 맞춤 테마 브리핑 프롬프트
            user_instructions_summary = instruction_text
            user_notes_block = (
                f"\n[★ 사용자 맞춤 최우선 지시사항 (Human Feedback)]:\n"
                f"- 요청 내용: \"{instruction_text}\"\n"
                f"- 지시 지침: 인위적인 긍정/부정 구분을 배제하고, 사용자가 요청한 주제를 심층 조명하는 맞춤 테마 섹션으로 구성할 것.\n"
            )

            system_instructions = (
                "당신은 글로벌 IT/과학 기술 정책 연구원이자 수석 테크 저널리스트입니다. "
                "사용자가 구체적인 분석 방향 및 관심 주제를 지정했으므로, 인위적인 긍정/부정 분류 대신 "
                "사용자의 지시사항을 관통하는 전문적인 테마 중심 마크다운(.md) 보고서를 작성하세요.\n\n"
                "권장 문서 구조:\n"
                "1. '# 📡 [IT/과학 테마 브리핑] ' 으로 시작하는 제목\n"
                "2. '## 🎯 [Executive Summary] 핵심 요약 및 테마 개요' (사용자의 요청 방향과 이를 관통하는 핵심 결론 제시)\n"
                "3. '## 🔍 1. [테마 집중 분석]: ' (사용자 지시사항과 직접 연관된 기사들을 심층 분석, 기사별 [제목](링크), 언론사, 핵심 요약 3줄 불릿, 세부 분석)\n"
                "4. '## 🌐 2. [산업적 파급 효과 및 기술 생태계 영향]' (해당 이슈가 시장, 기업, 기술 생태계에 미치는 파급력 분석)\n"
                "5. '## 📌 3. [동기간 기타 주요 IT/과학 헤드라인]' (지시사항 외에도 해당 기간 수집된 기사 중 주목할 만한 주요 기술 동향 2~3건 간략 정리)\n"
                "6. '## 💡 [종합 시사점 및 전략적 제언]' (사용자의 관점에서 도출되는 미래 전망 및 액션 아이템)\n\n"
                "작성 원칙:\n"
                "- 기사 제목은 반드시 클릭 가능한 마크다운 링크 형식 '[제목](링크)'으로 표기하세요.\n"
                "- 신뢰감 있고 격조 높은 한국어 경어체(~합니다, ~분석됩니다)를 사용하세요."
            )

            user_prompt = f"""[분석 기준 정보]
- 수집 및 분석 기간: {period_display}
- 총 수집 기사 건수: {len(articles)}건
- 분석 요청 일시: {created_at_str}
- 보고서 모드: 사용자 맞춤 테마 브리핑
{user_notes_block}

[수집된 IT/과학 기사 원문 목록]
{articles_text}

사용자의 지시사항("{instruction_text}")을 최우선으로 반영하여 완성도 높은 테마형 마크다운 보고서를 작성해 주세요.
보고서 제목은 '# 📡 [IT/과학 테마 브리핑] {period_display} 심층 분석 보고서' 로 작성해 주세요.
"""

        else:
            # 기본 3대 카테고리 브리핑 프롬프트
            user_instructions_summary = "기본 표준 분석 (추가 지시 없음)"
            user_notes_block = "\n[분석 모드]: 표준 IT/과학 3대 카테고리 종합 브리핑\n"

            system_instructions = (
                "당신은 글로벌 IT/과학 기술 정책 연구원이자 수석 테크 저널리스트입니다. "
                "제공된 뉴스 기사들을 정밀하게 종합하여 공식 브리핑용 고품질 마크다운(.md) 보고서를 작성하세요.\n\n"
                "반드시 아래 3대 카테고리로 명확하게 분류하여 정리해야 합니다:\n"
                "1. 🚀 [AI 긍정]: 인공지능 관련 긍정적 뉴스, 모델 성능 혁신, 산업 도입, 생산성 향상 사례 등\n"
                "2. ⚠️ [AI 부정]: 인공지능 관련 부작용, 보안 위협/해킹, 딥페이크 오남용, 윤리/저작권 논란, 규제 동향 등\n"
                "3. 🔬 [기타 IT & 첨단 과학]: AI 외 일반 IT 기술 및 첨단 과학 (반도체, 양자컴퓨터, 우주항공, 바이오, 로봇 등)\n\n"
                "문서 구조:\n"
                "1. '# 📡 [IT/과학 트렌드 브리핑] {period_display} 기술 동향 보고서' 로 시작\n"
                "2. '## 📊 [Executive Summary] 핵심 총평'\n"
                "3. 각 카테고리별 섹션 ('## 🚀 1. [AI 긍정]', '## ⚠️ 2. [AI 부정]', '## 🔬 3. [기타 IT & 과학]')\n"
                "   - 각 기사별: '[제목](링크)' (언론사), '핵심 요약(3줄 불릿)', '산업적·기술적 시사점'\n"
                "   - 특정 카테고리 기사가 없으면 '해당 기간 내 주요 이슈 없음' 명시\n"
                "4. '## 💡 [종합 시사점 및 미래 전망]'\n\n"
                "작성 원칙:\n"
                "- 기사 제목은 반드시 클릭 가능한 마크다운 링크 형식 '[제목](링크)'으로 표기하세요.\n"
                "- 신뢰감 있고 격조 높은 한국어 경어체(~합니다, ~분석됩니다)를 사용하세요."
            )

            user_prompt = f"""[분석 기준 정보]
- 수집 및 분석 기간: {period_display}
- 총 수집 기사 건수: {len(articles)}건
- 분석 요청 일시: {created_at_str}
- 보고서 모드: 기본 3대 카테고리 브리핑
{user_notes_block}

[수집된 IT/과학 기사 원문 목록]
{articles_text}

위 기사들을 3대 카테고리로 명확히 분류하여 품격 있는 마크다운 보고서를 작성해 주세요.
보고서 제목은 '# 📡 [IT/과학 트렌드 브리핑] {period_display} 기술 동향 보고서' 로 시작해 주세요.
"""

        try:
            # OpenAI Responses API 호출 (gpt-5.6-luna)
            response = self.client.responses.create(
                model=self.model_name,
                instructions=system_instructions,
                input=user_prompt,
            )
            report_md = response.output_text.strip()

            # 마크다운 파일 저장
            file_date_str = (
                start_date_str.replace("-", "")
                if start_date_str == end_date_str
                else f"{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}"
            )
            mode_prefix = "맞춤테마" if is_custom_mode else "기본브리핑"
            filename = f"IT_과학_{mode_prefix}_{file_date_str}.md"
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
                "report_mode": report_mode,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"AI 보고서 생성 실패: {str(e)}",
            }
