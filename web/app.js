/**
 * 프론트엔드 인터랙션 및 pywebview 통신 스크립트 (app.js)
 */

document.addEventListener("DOMContentLoaded", () => {
  let datePickerInstance = null;
  let pollInterval = null;
  let currentReportData = null;

  // DOM 요소
  const dateInput = document.getElementById("date-range");
  const maxItemsSelect = document.getElementById("max-items");
  const runBtn = document.getElementById("run-btn");
  const appStatusBadge = document.getElementById("app-status-badge");

  const progressWrap = document.getElementById("progress-wrap");
  const progressMsg = document.getElementById("progress-msg");
  const progressPct = document.getElementById("progress-pct");
  const progressBarFill = document.getElementById("progress-bar-fill");

  const articleCountBadge = document.getElementById("article-count-badge");
  const statPeriod = document.getElementById("stat-period");
  const statCsv = document.getElementById("stat-csv");
  const newsTbody = document.getElementById("news-tbody");

  const reportContainer = document.getElementById("report-container");
  const reportEmpty = document.getElementById("report-empty");
  const reportContent = document.getElementById("report-content");

  const openDataBtn = document.getElementById("open-data-btn");
  const openReportsBtn = document.getElementById("open-reports-btn");
  const copyReportBtn = document.getElementById("copy-report-btn");
  const openFileBtn = document.getElementById("open-file-btn");

  // 1. Flatpickr 달력 초기화 (오늘 날짜 기본 설정, 한국어, 범위 모드)
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];

  datePickerInstance = flatpickr(dateInput, {
    mode: "range",
    locale: "ko",
    dateFormat: "Y-m-d",
    defaultDate: [todayStr, todayStr],
    maxDate: todayStr,
    showMonths: 1,
    onChange: function (selectedDates, dateStr, instance) {
      // 날짜 선택 시 처리
    }
  });

  // 2. [뉴스 수집 & AI 보고서 생성] 원클릭 실행
  runBtn.addEventListener("click", async () => {
    const selectedDates = datePickerInstance.selectedDates;
    if (!selectedDates || selectedDates.length === 0) {
      alert("수집할 날짜를 달력에서 선택해 주세요.");
      return;
    }

    const formatDate = (d) => {
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    };

    const startDateStr = formatDate(selectedDates[0]);
    // 단일 날짜 선택 시(1개만 클릭한 경우) 시작일과 종료일을 동일하게 설정
    const endDateStr = selectedDates.length > 1 ? formatDate(selectedDates[1]) : startDateStr;

    const query = "";
    const maxItems = parseInt(maxItemsSelect.value, 10) || 20;

    // UI 비활성화 및 진행 표시
    setUiRunningState(true);

    try {
      if (window.pywebview && window.pywebview.api) {
        const startRes = await window.pywebview.api.start_pipeline(startDateStr, endDateStr, query, maxItems);
        if (!startRes.success) {
          alert("실행 실패: " + startRes.error);
          setUiRunningState(false);
          return;
        }
        // 상태 폴링 시작 (400ms 주기)
        startStatusPolling();
      } else {
        alert("pywebview 백엔드와 연결되지 않았습니다. 데스크톱 앱 창에서 실행해 주세요.");
        setUiRunningState(false);
      }
    } catch (e) {
      alert("오류 발생: " + e.message);
      setUiRunningState(false);
    }
  });

  // 3. 상태 폴링 함수
  function startStatusPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        if (!window.pywebview || !window.pywebview.api) return;

        const status = await window.pywebview.api.get_status();

        progressMsg.textContent = status.message || "작업 진행 중...";
        const pct = status.progress || 0;
        progressPct.textContent = `${pct}%`;
        progressBarFill.style.width = `${pct}%`;

        if (status.step === "scraping") {
          appStatusBadge.textContent = "뉴스 수집 중";
          appStatusBadge.className = "badge primary";
        } else if (status.step === "reporting") {
          appStatusBadge.textContent = "AI 보고서 작성 중";
          appStatusBadge.className = "badge secondary";
        }

        // 완료 또는 에러 처리
        if (!status.is_running) {
          clearInterval(pollInterval);
          pollInterval = null;

          if (status.step === "done") {
            appStatusBadge.textContent = "작업 완료";
            appStatusBadge.className = "badge secondary";
            await loadAndRenderResults();
          } else if (status.step === "error") {
            appStatusBadge.textContent = "오류 발생";
            appStatusBadge.className = "badge info";
            alert("작업 중 오류: " + status.error);
          }

          setUiRunningState(false);
        }
      } catch (err) {
        console.error("폴링 오류:", err);
      }
    }, 400);
  }

  // 4. 결과 로드 및 렌더링
  async function loadAndRenderResults() {
    try {
      const data = await window.pywebview.api.get_results();
      currentReportData = data;

      const articles = data.articles || [];
      const report = data.report || {};
      const csvPath = data.csv_path || "";
      const period = data.period || "-";

      // 1) 통계 요약 갱신
      articleCountBadge.textContent = `${articles.length}건`;
      statPeriod.textContent = period;
      statCsv.textContent = csvPath ? csvPath.split("\\").pop() : "-";
      statCsv.title = csvPath;

      // 2) 기사 테이블 렌더링
      if (articles.length === 0) {
        newsTbody.innerHTML = `<tr><td colspan="5" class="empty-cell">지정된 기간 내 수집된 기사가 없습니다.</td></tr>`;
      } else {
        let rowsHtml = "";
        articles.forEach((art, idx) => {
          const title = art.title || "제목 없음";
          const press = art.press || "-";
          const link = art.link || art.originallink || "#";
          const pubDate = art.pubDate ? art.pubDate.replace("+0900", "") : "-";

          rowsHtml += `
            <tr>
              <td>${idx + 1}</td>
              <td title="${title}"><strong>${title}</strong></td>
              <td>${press}</td>
              <td style="font-size: 11px; color: #94a3b8;">${pubDate}</td>
              <td>
                <a href="${link}" target="_blank" class="table-link-btn" title="원문 보기">보기</a>
              </td>
            </tr>
          `;
        });
        newsTbody.innerHTML = rowsHtml;
      }

      // 3) 마크다운 보고서 렌더링
      if (report && report.report_md) {
        reportEmpty.style.display = "none";
        reportContent.style.display = "block";
        reportContent.innerHTML = marked.parse(report.report_md);
      } else {
        reportEmpty.style.display = "flex";
        reportContent.style.display = "none";
      }
    } catch (e) {
      console.error("결과 로드 실패:", e);
    }
  }

  // UI 상태 토글
  function setUiRunningState(isRunning) {
    runBtn.disabled = isRunning;
    progressWrap.style.display = isRunning ? "flex" : "none";
    if (isRunning) {
      runBtn.querySelector(".btn-text").textContent = "수집 및 AI 분석 중...";
      runBtn.querySelector(".btn-icon").textContent = "⏳";
    } else {
      runBtn.querySelector(".btn-text").textContent = "뉴스 수집 & AI 보고서 생성";
      runBtn.querySelector(".btn-icon").textContent = "🚀";
    }
  }

  // 5. 폴더 및 파일 열기 버튼
  openDataBtn.addEventListener("click", async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder("data");
    }
  });

  openReportsBtn.addEventListener("click", async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder("reports");
    }
  });

  openFileBtn.addEventListener("click", async () => {
    if (currentReportData && currentReportData.report && currentReportData.report.file_path) {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.open_file(currentReportData.report.file_path);
      }
    } else {
      alert("먼저 생성된 보고서가 필요합니다.");
    }
  });

  // 6. 마크다운 복사
  copyReportBtn.addEventListener("click", async () => {
    if (currentReportData && currentReportData.report && currentReportData.report.report_md) {
      try {
        await navigator.clipboard.writeText(currentReportData.report.report_md);
        alert("📋 마크다운 보고서 내용이 클립보드에 복사되었습니다!");
      } catch (e) {
        alert("복사 실패: " + e.message);
      }
    } else {
      alert("복사할 보고서 내용이 없습니다.");
    }
  });
});
