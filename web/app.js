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
  const collectBtn = document.getElementById("collect-btn");
  const reportBtn = document.getElementById("report-btn");
  const appStatusBadge = document.getElementById("app-status-badge");
  const dbStatBadge = document.getElementById("db-stat-badge");

  const progressWrap = document.getElementById("progress-wrap");
  const progressMsg = document.getElementById("progress-msg");
  const progressPct = document.getElementById("progress-pct");
  const progressBarFill = document.getElementById("progress-bar-fill");

  const articleCountBadge = document.getElementById("article-count-badge");
  const statPeriod = document.getElementById("stat-period");
  const statDbStatus = document.getElementById("stat-db-status");
  const newsTbody = document.getElementById("news-tbody");

  const reportContainer = document.getElementById("report-container");
  const reportEmpty = document.getElementById("report-empty");
  const reportContent = document.getElementById("report-content");
  const reportModeTag = document.getElementById("report-mode-tag");
  const fontDecreaseBtn = document.getElementById("font-decrease-btn");
  const fontIncreaseBtn = document.getElementById("font-increase-btn");
  const fontZoomLevel = document.getElementById("font-zoom-level");

  const reportFileTree = document.getElementById("report-file-tree");
  const reportFileList = document.getElementById("report-file-list");
  const reportTreeCount = document.getElementById("report-tree-count");
  const treeToggleBtn = document.getElementById("tree-toggle-btn");

  const exportCsvBtn = document.getElementById("export-csv-btn");
  const openReportsBtn = document.getElementById("open-reports-btn");
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

  // 3. 앱 초기화 (DB 통계, 대화 히스토리, 이전 보고서 목록 및 최신 보고서 로드)
  setTimeout(async () => {
    if (window.pywebview && window.pywebview.api) {
      await refreshDbStats();
      await loadChatHistory();
      await loadReportsHistoryList();
      await loadLatestReportOnStartup();
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

  // 2-1. 폰트 줌(글자 크기) 스케일 제어
  const FONT_SCALES = [
    { label: "80%", scale: 0.85 },
    { label: "90%", scale: 0.92 },
    { label: "100%", scale: 1.0 },
    { label: "115%", scale: 1.15 },
    { label: "130%", scale: 1.3 },
    { label: "150%", scale: 1.5 },
  ];
  let currentFontIdx = 2; // 기본 100%

  function applyFontZoom(idx) {
    currentFontIdx = Math.max(0, Math.min(FONT_SCALES.length - 1, idx));
    const current = FONT_SCALES[currentFontIdx];
    document.documentElement.style.setProperty("--report-font-scale", current.scale);
    if (fontZoomLevel) {
      fontZoomLevel.textContent = current.label;
    }
    localStorage.setItem("news_report_font_idx", currentFontIdx);
  }

  // 저장된 폰트 크기 복원
  const savedFontIdx = localStorage.getItem("news_report_font_idx");
  if (savedFontIdx !== null) {
    applyFontZoom(parseInt(savedFontIdx, 10));
  } else {
    applyFontZoom(2);
  }

  if (fontDecreaseBtn) {
    fontDecreaseBtn.addEventListener("click", () => {
      applyFontZoom(currentFontIdx - 1);
    });
  }
  if (fontIncreaseBtn) {
    fontIncreaseBtn.addEventListener("click", () => {
      applyFontZoom(currentFontIdx + 1);
    });
  }

  // 2-2. 파일 보관함 서브 사이드바 접기/펼치기 토글
  if (treeToggleBtn && reportFileTree) {
    treeToggleBtn.addEventListener("click", () => {
      const isCollapsed = reportFileTree.classList.toggle("collapsed");
      treeToggleBtn.textContent = isCollapsed ? "▶" : "◀";
      treeToggleBtn.title = isCollapsed ? "보관함 펼치기" : "보관함 접기";
    });
  }

  let currentSelectedReportKey = "";

  // 이전 보고서 파일 시스템 탐색기 목록 로드 (서브 사이드바)
  async function loadReportsHistoryList() {
    try {
      if (window.pywebview && window.pywebview.api && reportFileList) {
        const res = await window.pywebview.api.get_reports_list();
        if (res && res.success && res.reports) {
          if (reportTreeCount) {
            reportTreeCount.textContent = res.reports.length;
          }
          reportFileList.innerHTML = "";
          if (res.reports.length === 0) {
            reportFileList.innerHTML = `<div class="empty-cell" style="padding: 15px 5px; font-size: 11px;">보관된 보고서가 없습니다.</div>`;
            return;
          }

          res.reports.forEach((rep) => {
            const key = rep.id > 0 ? `id:${rep.id}` : `file:${rep.file_path}`;
            const isCustom = (rep.report_mode === "custom") ||
                             (rep.user_instructions && rep.user_instructions !== "기본 표준 분석 (추가 지시 없음)" && !rep.user_instructions.includes("표준"));

            const card = document.createElement("div");
            card.className = "report-file-card" + (key === currentSelectedReportKey ? " active" : "");
            card.dataset.key = key;

            const title = rep.title || "브리핑 보고서";
            const date = rep.created_at || rep.period || "-";
            const tagText = isCustom ? "맞춤" : "기본";
            const tagClass = isCustom ? "custom" : "standard";
            const count = rep.article_count ? `${rep.article_count}건` : "";

            card.innerHTML = `
              <div class="file-card-top">
                <span class="file-card-title" title="${title}">${title}</span>
                <span class="file-card-tag ${tagClass}">${tagText}</span>
              </div>
              <div class="file-card-meta">
                <span>${date}</span>
                <span>${count}</span>
              </div>
            `;

            card.addEventListener("click", async () => {
              document.querySelectorAll(".report-file-card").forEach(c => c.classList.remove("active"));
              card.classList.add("active");
              currentSelectedReportKey = key;

              try {
                let loadRes = null;
                if (rep.id > 0) {
                  loadRes = await window.pywebview.api.load_report(rep.id, "");
                } else if (rep.file_path) {
                  loadRes = await window.pywebview.api.load_report(0, rep.file_path);
                }

                if (loadRes && loadRes.success && loadRes.report) {
                  currentReportData = loadRes;
                  renderReport(loadRes.report);
                  if (loadRes.articles && loadRes.articles.length > 0) {
                    renderArticles(loadRes.articles, loadRes.report.period || "-");
                  }
                } else {
                  alert("보고서 불러오기 실패: " + (loadRes?.error || "오류"));
                }
              } catch (err) {
                alert("보고서 로드 오류: " + err.message);
              }
            });

            reportFileList.appendChild(card);
          });
        }
      }
    } catch (e) {
      console.warn("보고서 목록 로드 실패:", e);
    }
  }

  // 앱 시작 시 가장 최근 생성된 보고서 자동 렌더링
  async function loadLatestReportOnStartup() {
    try {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.get_latest_report();
        if (res && res.success && res.report) {
          currentReportData = res;
          const key = res.report.id > 0 ? `id:${res.report.id}` : `file:${res.report.file_path}`;
          currentSelectedReportKey = key;
          renderReport(res.report);
          if (res.articles && res.articles.length > 0) {
            renderArticles(res.articles, res.report.period || "-");
          }
          // 파일 탐색기 카드 active 동기화
          document.querySelectorAll(".report-file-card").forEach(c => {
            c.classList.toggle("active", c.dataset.key === key);
          });
        }
      }
    } catch (e) {
      console.warn("최신 보고서 자동 로드 실패:", e);
    }
  }

  // Helper: 날짜 선택 값 파싱
  function getSelectedDateRange() {
    const selectedDates = datePickerInstance.selectedDates;
    if (!selectedDates || selectedDates.length === 0) {
      alert("날짜를 달력에서 선택해 주세요.");
      return null;
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

    return { startDateStr, endDateStr, maxItems };
  }

  // 4-1. [기사 수집 (DB 저장)] 버튼 이벤트
  collectBtn.addEventListener("click", async () => {
    const range = getSelectedDateRange();
    if (!range) return;

    setUiRunningState(true, "collect");

    try {
      if (window.pywebview && window.pywebview.api) {
        const startRes = await window.pywebview.api.start_collect(range.startDateStr, range.endDateStr, range.maxItems);
        if (!startRes.success) {
          alert("수집 실패: " + startRes.error);
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

  // 4-2. [AI 보고서 생성] 버튼 이벤트 (DB 우선 캐시 / 미존재 시 자동 수집 후 생성)
  reportBtn.addEventListener("click", async () => {
    const range = getSelectedDateRange();
    if (!range) return;

    setUiRunningState(true, "report");

    try {
      if (window.pywebview && window.pywebview.api) {
        const startRes = await window.pywebview.api.start_report(range.startDateStr, range.endDateStr, range.maxItems);
        if (!startRes.success) {
          alert("보고서 생성 실패: " + startRes.error);
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

      // 테이블 렌더링
      renderArticles(articles, period, csvPath);

      // 보고서 렌더링
      if (report && report.report_md) {
        renderReport(report);
        if (activeInstructionBar) {
          activeInstructionBar.style.display = "none";
        }
      }

      // 이전 보고서 파일 보관함 목록 갱신 및 활성 카드 선택
      await loadReportsHistoryList();
      if (report && (report.id || report.file_path)) {
        const key = report.id > 0 ? `id:${report.id}` : `file:${report.file_path}`;
        currentSelectedReportKey = key;
        document.querySelectorAll(".report-file-card").forEach(c => {
          c.classList.toggle("active", c.dataset.key === key);
        });
      }
    } catch (e) {
      console.error("결과 로드 실패:", e);
    }
  }

  function renderReport(report) {
    if (report && report.report_md) {
      reportEmpty.style.display = "none";
      reportContent.style.display = "block";
      reportContent.innerHTML = marked.parse(report.report_md);

      if (reportModeTag) {
        const isCustom = (report.report_mode === "custom") || 
                         (report.user_instructions && report.user_instructions !== "기본 표준 분석 (추가 지시 없음)" && !report.user_instructions.includes("표준"));
        if (isCustom) {
          reportModeTag.textContent = "맞춤 테마 브리핑";
          reportModeTag.className = "mode-tag custom";
        } else {
          reportModeTag.textContent = "기본 3대 브리핑";
          reportModeTag.className = "mode-tag standard";
        }
      }
    } else {
      reportEmpty.style.display = "flex";
      reportContent.style.display = "none";
    }
  }

  function renderArticles(articles = [], period = "-") {
    articleCountBadge.textContent = `${articles.length}건`;
    if (period && period !== "-") statPeriod.textContent = period;
    if (statDbStatus) {
      statDbStatus.textContent = articles.length > 0 ? `DB ${articles.length}건 보관` : "-";
    }

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
  function setUiRunningState(isRunning, operationType = "") {
    if (collectBtn) collectBtn.disabled = isRunning;
    if (reportBtn) reportBtn.disabled = isRunning;
    progressWrap.style.display = isRunning ? "flex" : "none";

    if (isRunning) {
      if (operationType === "collect" && collectBtn) {
        collectBtn.querySelector(".btn-text").textContent = "수집 진행 중...";
        collectBtn.querySelector(".btn-icon").textContent = "⏳";
      } else if (operationType === "report" && reportBtn) {
        reportBtn.querySelector(".btn-text").textContent = "보고서 작성 중...";
        reportBtn.querySelector(".btn-icon").textContent = "⏳";
      }
    } else {
      if (collectBtn) {
        collectBtn.querySelector(".btn-text").textContent = "기사 수집 (DB 저장)";
        collectBtn.querySelector(".btn-icon").textContent = "📥";
      }
      if (reportBtn) {
        reportBtn.querySelector(".btn-text").textContent = "AI 보고서 생성";
        reportBtn.querySelector(".btn-icon").textContent = "📑";
      }
    }
  }

  // 유틸리티 버튼
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener("click", async () => {
      try {
        if (window.pywebview && window.pywebview.api) {
          const res = await window.pywebview.api.export_articles_csv();
          if (res && res.success) {
            alert(`✅ ${res.message}\n(저장 폴더: reports/)`);
          } else {
            alert("CSV 내보내기 실패: " + (res?.error || "오류"));
          }
        } else {
          alert("데스크톱 앱 환경에서 실행해 주세요.");
        }
      } catch (e) {
        alert("CSV 내보내기 오류: " + e.message);
      }
    });
  }

  openReportsBtn.addEventListener("click", async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.open_folder("reports");
    }
  });

  openFileBtn.addEventListener("click", async () => {
    try {
      const filePath = (currentReportData && currentReportData.report && currentReportData.report.file_path) || "";
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.open_report_file(filePath);
        if (res && !res.success) {
          alert("보고서 파일 열기 실패: " + res.error);
        }
      } else {
        alert("데스크톱 앱 환경에서 실행해 주세요.");
      }
    } catch (e) {
      alert("파일 열기 오류: " + e.message);
    }
  });
});
