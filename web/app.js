/**
 * 프론트엔드 인터랙션 및 pywebview 통신 스크립트 (app.js)
 * 3열 대시보드 및 AI 비서 챗봇 실시간 지시 연동
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
  const dbStatBadge = document.getElementById("db-stat-badge");

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
  const reportModeTag = document.getElementById("report-mode-tag");

  const openDataBtn = document.getElementById("open-data-btn");
  const openReportsBtn = document.getElementById("open-reports-btn");
  const copyReportBtn = document.getElementById("copy-report-btn");
  const openFileBtn = document.getElementById("open-file-btn");

  // 챗봇 및 지시사항 요소
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const initialChatTime = document.getElementById("initial-chat-time");

  const activeInstructionBar = document.getElementById("active-instruction-bar");
  const instructionChipText = document.getElementById("instruction-chip-text");
  const instructionChipRemove = document.getElementById("instruction-chip-remove");

  // 1. 초기 시간 표시
  const now = new Date();
  if (initialChatTime) {
    initialChatTime.textContent = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`;
  }

  // 2. Flatpickr 달력 초기화
  const todayStr = now.toISOString().split("T")[0];
  datePickerInstance = flatpickr(dateInput, {
    mode: "range",
    locale: "ko",
    dateFormat: "Y-m-d",
    defaultDate: [todayStr, todayStr],
    maxDate: todayStr,
    showMonths: 1,
  });

  // 3. 앱 초기화 (DB 통계 및 대화 히스토리 로드)
  setTimeout(async () => {
    if (window.pywebview && window.pywebview.api) {
      await refreshDbStats();
      await loadChatHistory();
    }
  }, 300);

  async function refreshDbStats() {
    try {
      if (window.pywebview && window.pywebview.api) {
        const stats = await window.pywebview.api.get_db_stats();
        if (stats && dbStatBadge) {
          dbStatBadge.textContent = `DB 누적: ${stats.total_articles || 0}건`;
        }
      }
    } catch (e) {
      console.warn("DB 통계 조회 실패:", e);
    }
  }

  async function loadChatHistory() {
    try {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.get_chat_history();
        if (res && res.history && res.history.length > 0) {
          chatMessages.innerHTML = "";
          res.history.forEach(msg => {
            appendChatMessage(msg.role, msg.content);
          });
        }

        // 대기 중인 활성 지시사항 조회
        const activeRes = await window.pywebview.api.get_active_instruction();
        if (activeRes && activeRes.active_instruction && activeInstructionBar && instructionChipText) {
          instructionChipText.textContent = activeRes.active_instruction;
          activeInstructionBar.style.display = "flex";
        }
      }
    } catch (e) {
      console.warn("챗 히스토리 로드 실패:", e);
    }
  }

  // 4. [수집 & AI 보고서 생성] 원클릭 실행
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
    const endDateStr = selectedDates.length > 1 ? formatDate(selectedDates[1]) : startDateStr;
    const maxItems = parseInt(maxItemsSelect.value, 10) || 20;

    setUiRunningState(true);

    try {
      if (window.pywebview && window.pywebview.api) {
        const startRes = await window.pywebview.api.start_pipeline(startDateStr, endDateStr, "", maxItems);
        if (!startRes.success) {
          alert("실행 실패: " + startRes.error);
          setUiRunningState(false);
          return;
        }
        startStatusPolling();
      } else {
        alert("데스크톱 앱 환경에서 실행해 주세요.");
        setUiRunningState(false);
      }
    } catch (e) {
      alert("오류 발생: " + e.message);
      setUiRunningState(false);
    }
  });

  // 5. 상태 폴링
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
          appStatusBadge.textContent = "기사 수집 및 DB 적재 중";
          appStatusBadge.className = "badge primary";
        } else if (status.step === "reporting") {
          appStatusBadge.textContent = "AI 보고서 작성 중";
          appStatusBadge.className = "badge secondary";
        }

        if (!status.is_running) {
          clearInterval(pollInterval);
          pollInterval = null;

          if (status.step === "done") {
            appStatusBadge.textContent = "작업 완료";
            appStatusBadge.className = "badge secondary";
            await loadAndRenderResults();
            await refreshDbStats();
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

  // 6. 결과 렌더링
  async function loadAndRenderResults() {
    try {
      const data = await window.pywebview.api.get_results();
      currentReportData = data;

      const articles = data.articles || [];
      const report = data.report || {};
      const csvPath = data.csv_path || "";
      const period = data.period || "-";

      articleCountBadge.textContent = `${articles.length}건`;
      statPeriod.textContent = period;
      statCsv.textContent = csvPath ? csvPath.split("\\").pop() : "-";
      statCsv.title = csvPath;

      // 테이블 렌더링
      if (articles.length === 0) {
        newsTbody.innerHTML = `<tr><td colspan="4" class="empty-cell">지정된 기간 내 수집된 IT/과학 기사가 없습니다.</td></tr>`;
      } else {
        let rowsHtml = "";
        articles.forEach((art, idx) => {
          const title = art.title || "제목 없음";
          const press = art.press || "-";
          const link = art.link || art.originallink || "#";

          rowsHtml += `
            <tr>
              <td>${idx + 1}</td>
              <td title="${title}"><strong>${title}</strong></td>
              <td>${press}</td>
              <td>
                <a href="${link}" target="_blank" class="table-link-btn" title="원문 보기">보기</a>
              </td>
            </tr>
          `;
        });
        newsTbody.innerHTML = rowsHtml;
      }

      // 보고서 렌더링
      if (report && report.report_md) {
        reportEmpty.style.display = "none";
        reportContent.style.display = "block";
        reportContent.innerHTML = marked.parse(report.report_md);

        // 듀얼 모드 태그 표시
        if (reportModeTag) {
          if (report.report_mode === "custom") {
            reportModeTag.textContent = "맞춤 테마 브리핑";
            reportModeTag.className = "mode-tag custom";
          } else {
            reportModeTag.textContent = "기본 3대 브리핑";
            reportModeTag.className = "mode-tag standard";
          }
        }

        // 보고서 생성 완료 시 활성 지시 바 숨김 (소모됨)
        if (activeInstructionBar) {
          activeInstructionBar.style.display = "none";
        }
      } else {
        reportEmpty.style.display = "flex";
        reportContent.style.display = "none";
      }
    } catch (e) {
      console.error("결과 로드 실패:", e);
    }
  }

  // 7. 챗봇 대화 인터랙션
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = "";
    appendChatMessage("user", text);

    // 활성 지시 바 표시
    if (activeInstructionBar && instructionChipText) {
      instructionChipText.textContent = text;
      activeInstructionBar.style.display = "flex";
    }

    // AI 응답 요청
    try {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.send_chat(text);
        if (res && res.success) {
          appendChatMessage("assistant", res.reply);
          if (res.active_instruction && instructionChipText) {
            instructionChipText.textContent = res.active_instruction;
            activeInstructionBar.style.display = "flex";
          }
        } else {
          appendChatMessage("assistant", "응답 오류: " + (res.error || "알 수 없는 오류"));
        }
      }
    } catch (err) {
      appendChatMessage("assistant", "전송 실패: " + err.message);
    }
  });

  // 활성 지시사항 해제 버튼 (X 클릭)
  if (instructionChipRemove) {
    instructionChipRemove.addEventListener("click", async () => {
      try {
        if (window.pywebview && window.pywebview.api) {
          await window.pywebview.api.clear_active_instruction();
        }
        if (activeInstructionBar) activeInstructionBar.style.display = "none";
        if (instructionChipText) instructionChipText.textContent = "-";
      } catch (e) {
        console.warn("지시사항 해제 실패:", e);
      }
    });
  }

  function appendChatMessage(role, content) {
    const isUser = role === "user";
    const msgDiv = document.createElement("div");
    msgDiv.className = `msg ${isUser ? "outgoing" : "incoming"}`;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.innerHTML = `
      <div class="msg-bubble">${escapeHtml(content)}</div>
      <span class="msg-time">${timeStr}</span>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
  }

  clearChatBtn.addEventListener("click", async () => {
    if (confirm("AI 비서와의 대화 내역을 초기화하시겠습니까?")) {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.clear_chat_history();
        if (activeInstructionBar) activeInstructionBar.style.display = "none";
        chatMessages.innerHTML = `
          <div class="msg incoming">
            <div class="msg-bubble">대화 내역이 초기화되었습니다. 새로운 분석 지시사항을 말씀해 주세요!</div>
          </div>
        `;
      }
    }
  });

  // UI 상태 토글
  function setUiRunningState(isRunning) {
    runBtn.disabled = isRunning;
    progressWrap.style.display = isRunning ? "flex" : "none";
    if (isRunning) {
      runBtn.querySelector(".btn-text").textContent = "수집 & 분석 중...";
      runBtn.querySelector(".btn-icon").textContent = "⏳";
    } else {
      runBtn.querySelector(".btn-text").textContent = "수집 & AI 보고서 생성";
      runBtn.querySelector(".btn-icon").textContent = "🚀";
    }
  }

  // 유틸리티 버튼
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

  copyReportBtn.addEventListener("click", async () => {
    if (currentReportData && currentReportData.report && currentReportData.report.report_md) {
      try {
        await navigator.clipboard.writeText(currentReportData.report.report_md);
        alert("📋 마크다운 보고서가 클립보드에 복사되었습니다!");
      } catch (e) {
        alert("복사 실패: " + e.message);
      }
    } else {
      alert("복사할 보고서 내용이 없습니다.");
    }
  });
});
