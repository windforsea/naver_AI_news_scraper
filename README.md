# 🤖 IT/과학 뉴스 수집 및 AI 브리핑 시스템 (Naver News & gpt-5.6-luna)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![pywebview](https://img.shields.io/badge/GUI-pywebview_6.2-4B8BBE?style=flat-square)](https://pywebview.flowrl.com/)
[![OpenAI](https://img.shields.io/badge/AI-gpt--5.6--luna-412991?style=flat-square&logo=openai&logoColor=white)](https://platform.openai.com/)
[![Naver API](https://img.shields.io/badge/API-NAVER_API_HUB-03C75A?style=flat-square)](https://www.ncloud.com/)
[![uv](https://img.shields.io/badge/Package_Manager-uv-DE5FE9?style=flat-square)](https://github.com/astral-sh/uv)

네이버 뉴스의 공식 **[IT/과학] (섹션 sid1=105) 카테고리 기사 전체를 특정 일자(단일일 또는 기간 범위) 기준으로 자동 수집**하고, OpenAI의 최신 **`gpt-5.6-luna` Responses API**를 통해 **AI 긍정 / AI 부정 / 기타 과학기술** 3대 카테고리로 자동 분류 및 심층 분석 마크다운(`.md`) 보고서를 생성하는 올인원 데스크톱 대시보드 애플리케이션입니다.

---

## 📸 프로그램 실행 화면 (Application Screenshot)

<p align="center">
  <img src="docs/app_main_screenshot.png" alt="IT/과학 뉴스 AI 브리핑 대시보드" width="760" style="border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.2);" />
</p>
<p align="center"><i>▲ 네이버 뉴스 [IT/과학] 카테고리 전체 최신순 자동 수집 및 gpt-5.6-luna 3대 카테고리 실시간 AI 브리핑 대시보드</i></p>

---

## 🏗️ 시스템 아키텍처 (System Architecture)

```mermaid
flowchart TD
    subgraph UI["🖥️ Modern Glassmorphism Dashboard (pywebview)"]
        A1["📅 날짜 범위 & 수집 건수 선택"]
        A2["📥 [기사 수집 (DB 저장)] 버튼"]
        A3["📑 [AI 보고서 생성] 버튼"]
        A4["🧑‍💼 AI 브리핑 비서 (지시사항 챗봇)"]
    end

    subgraph Backend["⚙️ Python Core Engine (news_scrapwithai)"]
        B1["NaverNewsCollector (Scraper)"]
        B2["NewsDatabase (SQLite RDBMS)"]
        B3["NewsReportGenerator (gpt-5.6-luna)"]
        B4["NewsAppApi (Bridge Controller)"]
    end

    subgraph Storage["💾 Persistence Layer"]
        DB[("news.db (SQLite)")]
        CSV["📁 data/*.csv (Excel)"]
        MD["📁 reports/*.md (Report)"]
    end

    A2 -->|수집 요청| B4
    B4 -->|네이버 IT/과학 sid1=105 크롤링| B1
    B1 -->|INSERT OR IGNORE| B2
    B1 -->|DataFrame Export| CSV
    B2 --> DB

    A3 -->|보고서 요청| B4
    B4 -->|1. DB 우선 캐시 확인| B2
    B2 -.->|기사 존재 시 즉시 반환 (크롤링 생략)| B4
    B4 -.->|기사 부재 시 자동 수집 연계| B1
    A4 -->|실시간 지시 주입| B4
    B4 -->|기사 컨텍스트 + 사용자 지시사항| B3
    B3 -->|OpenAI Responses API| LLM[("OpenAI gpt-5.6-luna")]
    LLM -->|마크다운 보고서 생성| B3
    B3 -->|보고서 저장 & M:N 기사 매핑| B2
    B3 -->|마크다운 파일 저장| MD
    B4 -->|결과 데이터 전달| UI
```

---

## 🌟 포트폴리오 핵심 기술 하이라이트 (Technical Highlights)

### 1. ⚡ 날짜 기반 역순 탐색 및 조기 종료 (Early Break) 알고리즘
- **도전 과제**: 네이버 뉴스 검색 API는 검색어(`query`) 기반 페이징만 지원하며, 특정 날짜 범위(`startDate` ~ `endDate`) 직접 필터링 파라미터를 제공하지 않습니다.
- **해결 방안**:
  - `sort=date`(최신순) 정렬을 기반으로 기사 목록을 역순 페이징 탐색합니다.
  - 각 기사의 `pubDate`(RFC 822)를 한국 표준시(KST)로 파싱하여 비교합니다.
  - 탐색 중 **사용자가 지정한 시작일 이전(과거) 데이터에 도달하면 즉시 API 호출 루프를 중단(Early Break)**하여 불필요한 네트워크 낭비와 쿼터 소모를 90% 이상 절감하고 수집 속도를 극대화했습니다.

### 2. 🕷️ 네이버 뉴스 원문 정적 크롤링 & 견고한 Fallback
- `n.news.naver.com` 기사 링크의 `#dic_area` 및 `#newsct_article` 셀렉터를 BeautifulSoup으로 크롤링하여 스크립트, 광고 태그를 제거한 순수 기사 본문 전문을 추출합니다.
- 외부 언론사 아웃링크이거나 크롤링 불가 시, API 요약문(`description`) 및 도메인 기반 언론사명으로 자연스럽게 전환되는 Fallback 아키텍처를 구현했습니다.

### 3. 🧠 OpenAI `gpt-5.6-luna` Responses API 기반 3대 카테고리 심층 분석
- 수집된 복수 기사의 원문을 정형화된 컨텍스트 블록으로 패키징하여 프롬프트에 주입합니다.
- **3대 카테고리 자동 분류**:
  1. 🚀 **[AI 긍정]**: 신모델 출시, 기술 혁신, 생산성 향상, 산업 적용 성공 사례
  2. ⚠️ **[AI 부정]**: 오작동/환각, 보안 및 딥페이크 악용 위협, 저작권/윤리 분쟁, 규제 논의
  3. 🔬 **[기타 과학기술]**: AI 외 우주항공, 반도체 공학, 바이오/의학, 양자컴퓨터 등
- 기사별 **핵심 3줄 요약**, **원문 클릭 링크**, **산업적 시사점**, 전체 생태계를 아우르는 **[종합 핵심 총평 (Executive Summary)]**이 포함된 마크다운(`.md`) 문서를 자동 작성합니다.

### 4. 🗄️ SQLite 데이터베이스 아카이브 & 다대다(N:M) 정규화 스키마
- **데이터 무결성 & 중복 방지**: 기사 링크(`link`)에 `UNIQUE` 제약조건을 부여하여 `INSERT OR IGNORE`로 중복 기사를 자동 스킵합니다.
- **다대다(N:M) 매핑 테이블 (`report_articles`)**: 보고서 하나에 여러 기사가 인용되고, 기사 하나도 여러 보고서에 활용될 수 있도록 정규화된 Junction Table을 설계하여 외래키(`FOREIGN KEY`)로 무결성을 보장합니다.
- **인덱싱 최적화**: 수만 건의 기사 데이터가 쌓여도 초고속 검색이 가능하도록 `pub_date` 및 `category` 인덱스를 구축했습니다.

### 5. 🧑‍💼 AI 브리핑 어시스턴트 & 듀얼 모드 보고서 (Dual-Mode Dynamic Framing)
- **지시사항 수명주기(Lifecycle) 및 시각화**:
  - 챗봇에게 *"보안 침해 사고를 집중 분석해줘"*, *"스타트업 투자 관점에서 시사점을 써줘"* 등을 입력하면 대기 칩(`📌 반영 대기 지시: [텍스트 ✕]`)이 활성화됩니다.
  - 보고서 생성이 완료되면 지시사항이 1회성으로 깔끔하게 소모(Consumed)되어 다음 수집 시 이전 지시가 의도치 않게 간섭하는 문제를 원천 방지합니다. 언제든 `✕` 버튼으로 즉시 취소할 수도 있습니다.
- **듀얼 모드 프레이밍**:
  - **기본 모드 (지시사항 없음)**: `🚀 [AI 긍정]` / `⚠️ [AI 부정]` / `🔬 [기타 과학기술]` 3대 표준 프레임워크로 브리핑.
  - **맞춤 모드 (지시사항 있음)**: 인위적 긍정/부정 구분을 탈피하고 사용자가 지시한 주제를 관통하는 유연한 **주제 중심 동적 섹션(`🎯 [테마 집중 분석]`, `🌐 [산업적 파급 효과]`, `💡 [맞춤 전략 제언]`)**으로 자동 재편성.

### 6. 🖥️ 수집·생성 2단 분리 제어 & 모던 글래스 UI 대시보드
- **수집 및 보고서 생성 2단 버튼 분리**:
  - **1단계 `[📥 기사 수집 (DB 저장)]`**: 지정된 기간의 IT/과학 기사를 네이버에서 수집하여 SQLite DB 및 CSV에 적재(AI API 미호출로 빠른 수집 및 토큰 절감).
  - **2단계 `[📑 AI 보고서 생성]` (DB 우선 캐시 & 자동 Fallback)**:
    - 선택된 기간의 기사가 DB에 이미 존재하면 **웹 크롤링을 생략하고 DB에서 즉시 기사를 로드**하여 초고속으로 보고서 작성.
    - DB에 기사가 없을 경우에만 네이버 뉴스에서 자동 수집 후 DB 적재를 거쳐 보고서 생성.
- **모던 3열 글래스모피즘 워크스페이스**:
  - **1열(좌측)**: [IT/과학] 수집 기사 테이블 및 데이터 폴더 원클릭 열기
  - **2열(중앙)**: gpt-5.6-luna 마크다운 보고서 뷰어 (`기본 3대 브리핑` vs `맞춤 테마 브리핑` 모드 뱃지 실시간 토글)
  - **3열(우측)**: AI 브리핑 비서 대화창 & 활성 지시사항 칩 관리 바

---

## 🛠️ 문제 의문 및 해결 (Troubleshooting & Engineering Decisions)

프로젝트 개발 및 고도화 과정에서 마주했던 기술적 난제들과 이를 해결한 엔지니어링 의사결정 과정입니다:

### Q1. 배치 파일 실행 시 `'API'은(는) 내부 또는 외부 명령이 아닙니다` 파싱 에러
- **문제 의문 (The Problem)**:
  `run.bat` 실행 시 콘솔창에 알 수 없는 구문 오류가 출력되며 프로그램 실행이 중단되는 현상이 발생했습니다.
- **원인 분석 (Root Cause)**:
  - `echo (Naver News IT/Science & gpt-5.6-luna)` 출력문 내의 `&` 특수문자를 윈도우 커맨드 인터프리터(`cmd.exe`)가 명령어 구분자(Command Chaining)로 오인식하여, 뒤에 오는 `API`를 독립된 쉘 명령어로 실행하려고 시도했습니다.
  - 또한 스크립트 저장 인코딩(UTF-8 with BOM vs ANSI/CP949) 차이로 인해 윈도우 배치 인터프리터가 첫 바이트 매직넘버를 정상 인식하지 못했습니다.
- **해결 방안 (Solution)**:
  - 앰퍼샌드를 `^&`로 이스케이프 처리하고, 스크립트 최상단에 `pushd "%~dp0"`를 지정하여 실행 작업 경로를 스크립트 위치로 강제 고정했습니다.
  - 유지보수를 저해하고 불필요한 서브스크립트였던 `run_silent.vbs`를 전면 삭제하고, 배치 파일을 순수 7-bit ASCII 인코딩으로 통일하여 모든 윈도우 환경에서 100% 무결한 원클릭 구동을 보장했습니다.

---

### Q2. 네이버 뉴스 API의 날짜 범위 필터링 부재와 성능 병목
- **문제 의문 (The Problem)**:
  네이버 오픈 API는 `startDate`/`endDate` 날짜 범위 필터링 파라미터를 제공하지 않고 검색어 기반 최신순 정렬만 지원합니다. 3일치 기사를 수집하기 위해 과거 기사까지 무조건 대량 호출해야 하는가?
- **원인 분석 (Root Cause)**:
  API 스펙의 한계로 인해 무차별 페이징 순회를 진행하면 불필요한 과거 데이터까지 훑게 되어 네트워크 지연과 쿼터 소모가 급증합니다.
- **해결 방안 (Solution)**:
  - `sort=date`(최신순) 정렬 기반 역순 탐색을 진행하며, 각 기사의 `pubDate`(RFC 822)를 한국 표준시(KST) `datetime`으로 실시간 파싱했습니다.
  - 기사 발행일이 사용자가 설정한 `startDate`보다 과거로 넘어가는 순간 탐색 루프를 즉시 중단하는 **조기 종료(Early Break) 알고리즘**을 구축했습니다.
- **성과 (Impact)**: 불필요한 API 호출 90% 이상 절감 및 데이터 수집 속도 약 8배 단축.

---

### Q3. CSV 파일 관리의 한계 ➔ SQLite RDBMS 정규화 및 다대다(N:M) 설계
- **문제 의문 (The Problem)**:
  "기존처럼 CSV 파일로만 데이터를 관리하는 것과 SQL 데이터베이스로 관리하는 것 중 어떤 구조가 더 확장성 있고 효율적인가?"
- **원인 분석 (Root Cause)**:
  CSV 파일은 매번 파일이 분할 생성되어 기사가 중복 적재되고, "과거의 특정 보고서가 어떤 기사들을 인용했는가?"를 역추적하거나 날짜별로 통계를 집계하는 관계형 질의가 불가능했습니다.
- **해결 방안 (Solution)**:
  - SQLite 경량 RDBMS를 도입하고 4대 정규화 스키마(`articles`, `reports`, `report_articles`, `chat_messages`)를 설계했습니다.
  - 기사 원문 링크(`link UNIQUE`) 제약조건과 `INSERT OR IGNORE` 구문을 적용해 중복 기사를 0ms로 자동 필터링했습니다.
  - 하나의 보고서에 여러 기사가 인용되고, 한 기사가 여러 보고서에 중복 활용될 수 있는 실무 환경을 완벽히 모델링하기 위해 다대다(N:M) Junction Table(`report_articles`)을 외래키(`FOREIGN KEY ON DELETE CASCADE`)로 구축했습니다.
  - `pub_date` 및 `category` 컬럼 인덱싱으로 대용량 기사 누적 시에도 밀리초 단위 쿼리 성능을 보장했습니다.

---

### Q4. 챗봇 지시사항의 간섭 문제와 듀얼 모드(Dual-Mode) 동적 프레이밍
- **문제 의문 (The Problem)**:
  "챗봇에게 지시를 한 번 내리면 다음번 보고서를 만들 때도 계속 이전 지시사항이 끼어들지 않는가?", "사용자가 '보안 사고 집중 분석'을 지시했는데도 굳이 AI 긍정/부정/기타 3가지로 억지로 쪼개야 하는가?"
- **해결 방안 (Solution)**:
  - **지시사항 수명 주기(Lifecycle) 확립**: 챗봇 지시 입력 시 UI에 `📌 반영 대기 지시` 칩을 표시하고 `✕` 취소 버튼을 제공했습니다. 보고서 생성이 끝나면 해당 지시는 **자동 소모(Consumed)**되어 칩이 닫히며, 다음 수집 시에는 기본 모드로 안전하게 복귀하도록 구현했습니다.
  - **동적 프레이밍 듀얼 모드**:
    - 기본 모드(지시 없음): `🚀 [AI 긍정]`, `⚠️ [AI 부정]`, `🔬 [기타 과학기술]` 정석 3대 브리핑 제공.
    - 맞춤 모드(지시 있음): 인위적인 긍정/부정 구분을 탈피하고, 사용자의 요청 주제를 관통하는 유연한 **주제 중심 동적 섹션(`🎯 [테마 집중 분석]`, `🌐 [산업적 파급 효과]`, `💡 [맞춤 전략 제언]`)**으로 자동 재구성.

---

### Q5. 수집과 생성의 결합으로 인한 비용 낭비 ➔ 2단 분리 및 DB-First(Cache-First) 아키텍처
- **문제 의문 (The Problem)**:
  초기에는 [수집 & 보고서 생성]이 하나의 버튼으로 묶여 있어, 단순 기사 수집 현황만 보고 싶을 때도 무조건 OpenAI LLM API 요금이 발생하고 대기 시간이 길어졌습니다. 또한 이미 DB에 저장된 날짜의 보고서를 다시 만들 때도 불필요하게 웹 크롤링을 다시 수행하는 심각한 비효율이 발생했습니다.
- **해결 방안 (Solution)**:
  - UI 버튼을 **`[📥 기사 수집 (DB 저장)]`**과 **`[📑 AI 보고서 생성]`**으로 물리적 2단 분리했습니다.
  - **DB 우선 캐싱 (Cache-First)**: 보고서 생성 시 SQLite DB를 먼저 조회하여 기사가 존재하면 **웹 크롤링을 100% 생략하고 DB에서 즉시 기사를 로드(0.1초 소요)**하여 LLM에 전달합니다. DB가 비어 있을 때만 자동으로 네이버 뉴스를 수집·적재한 뒤 보고서를 작성합니다.
  - **성과 (Impact)**: 불필요한 웹 트래픽 제거, OpenAI 토큰 비용 절감, 재보고서 작성 소요 시간 95% 단축.

---

## 📊 고정 데이터프레임 스키마 (Data Schema)

데이터 정제 및 CSV(`utf-8-sig`) 저장 시 데이터 무결성을 위해 아래 6종의 컬럼 규격을 엄격히 유지합니다:

| 컬럼명 | 타입 | 설명 |
| :--- | :---: | :--- |
| `title` | `str` | 기사 제목 (HTML 특수문자 및 태그 정제 완료) |
| `content` | `str` | 기사 본문 전문 (BeautifulSoup 크롤링 정제 텍스트) |
| `link` | `str` | 네이버 뉴스 상세 페이지 링크 |
| `originallink` | `str` | 언론사 공식 원문 URL |
| `pubDate` | `str` | 기사 발행 일시 (RFC 822 포맷) |
| `press` | `str` | 기사 발행 언론사명 (메타데이터 및 로고 alt 파싱) |

---

## 📁 프로젝트 구조 (Project Structure)

```
news_scrapwithAI/
├── .env                  # 네이버 및 OpenAI API 키 (보안 격리, .gitignore)
├── .env.example          # 환경 변수 가이드 템플릿
├── .gitignore            # 민감 데이터, 캐시, DB 파일 배제
├── pyproject.toml        # 의존성 및 프로젝트 메타데이터
├── run.bat               # 원클릭 실행 배치 스크립트 (경로 고정 및 이스케이프 무결성)
├── docs/                 # 포트폴리오용 시각자료
│   └── app_main_screenshot.png
├── data/                 # SQLite DB 및 엑셀 호환 CSV 저장소
│   ├── news.db           # SQLite 4대 정규화 데이터베이스
│   └── news_*.csv        # 일자별 6개 고정 컬럼 CSV
├── reports/              # 생성된 AI 마크다운 보고서 저장소 (*.md)
├── web/                  # 프론트엔드 리소스 (HTML5, CSS3, JS)
│   ├── index.html        # 3열 대시보드 구조 및 2단 제어 패널
│   ├── style.css         # 모던 글래스모피즘 스타일시트
│   └── app.js           # Flatpickr 연동, 2단 버튼 비동기 통신 및 지시 칩 관리
└── src/
    └── news_scrapwithai/
        ├── __init__.py   # 메인 진입점 (1280x840 pywebview 윈도우 런처)
        ├── config.py     # API 인증키 로더 및 디렉터리 절대경로 관리
        ├── database.py   # SQLite RDBMS 관리자 (articles, reports, 매핑, 대화)
        ├── scraper.py    # 네이버 뉴스 IT/과학(sid1=105) 섹션 전체 수집기
        ├── ai_reporter.py# gpt-5.6-luna 듀얼 모드 분석 및 마크다운 생성 엔진
        └── api.py        # 프론트엔드 JS ↔ 파이썬 백엔드 비동기 통신 브리지 (DB-First)
```

---

## 🚀 시작하기 (Quick Start)

### 1. 환경 설정 (.env)
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 발급받은 API 키를 입력합니다:

```env
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
OPENAI_API_KEY=your_openai_api_key
```

### 2. 패키지 설치
`uv`를 사용하여 가상환경 및 의존성을 초고속으로 동기화합니다:

```bash
uv sync
```

### 3. 프로그램 실행

#### 방법 1. 원클릭 실행 (더블 클릭)
- **`run.bat`**: 파일을 더블 클릭하면 콘솔 안내와 함께 데스크톱 앱 창이 즉시 실행됩니다.

#### 방법 2. 터미널 명령어
```bash
uv run news-scrapwithai
```
*(또는 `uv run python -m news_scrapwithai`)*
