document.addEventListener("DOMContentLoaded", () => {
  // =================================================================
  // 1. GERENCIAMENTO DE UI E SELETORES
  // =================================================================

  const UI = {
    video: document.getElementById("user-video"),
    canvasFrame: document.getElementById("frame-canvas"),
    canvasOverlay: document.getElementById("overlay-canvas"),
    ctxOverlay: document.getElementById("overlay-canvas").getContext("2d"),
    ctxFrame: document.getElementById("frame-canvas").getContext("2d"),

    // Elementos duplicados (Dashboard e HUD)
    bpm: [
      document.getElementById("bpm-value"),
      document.getElementById("hud-bpm-value"),
    ],
    socketStatus: [
      document.getElementById("socket-status"),
      document.getElementById("hud-socket-status"),
    ],
    cameraStatus: [
      document.getElementById("status-msg"),
      document.getElementById("hud-camera-status"),
    ],
    roiPreview: [
      document.getElementById("roi-preview"),
      document.getElementById("hud-roi-preview"),
    ],

    // --- NOVO: Botões de Travar/Destravar ---
    locks: [
      document.getElementById("btn-lock-camera"),
      document.getElementById("btn-lock-hud"),
    ],

    // Fullscreen Controls
    fullscreen: {
      btnExpand: document.getElementById("btn-expand-camera"),
      btnExit: document.getElementById("btn-exit-fullscreen"),
      wrapper: document.getElementById("main-video-wrapper"),
      hud: document.getElementById("camera-hud"),
      toggleRoi: document.getElementById("toggle-roi"),
    },

    // Cards (para toggles)
    cards: {
      fft: document.getElementById("card-fft"),
      raw: document.getElementById("card-raw"),
      filtered: document.getElementById("card-filtered"),
    },

    // HUD Boxes (para toggles)
    hudBoxes: {
      fft: document.getElementById("hud-box-fft"),
      raw: document.getElementById("hud-box-raw"),
      filtered: document.getElementById("hud-box-filtered"),
    },
  };

  // Estado Global
  const STATE = {
    isFullscreen: false,
    showRoi: true,
    isLocked: false, // <--- NOVO: Controla se está calculando ou procurando
    maxPoints: 100,
    miniMaxPoints: 50,
  };

  // =================================================================
  // 2. FUNÇÕES AUXILIARES DE UI (HELPERS)
  // =================================================================

  const updateBadges = (elements, text, cssClass) => {
    elements.forEach((el) => {
      if (el) {
        el.innerText = text;
        // Remove classes antigas de cor (bg-...) e mantém layout
        const layoutClasses = Array.from(el.classList).filter(
          (c) =>
            !c.startsWith("bg-") &&
            c !== "badge" &&
            c !== "text-dark" &&
            c !== "text-white",
        );
        el.className = `badge ${cssClass} ${layoutClasses.join(" ")}`;
      }
    });
  };

  const updateText = (elements, text) => {
    elements.forEach((el) => {
      if (el) el.innerText = text;
    });
  };

  const updateImages = (elements, base64) => {
    const src = "data:image/jpeg;base64," + base64;
    elements.forEach((el) => {
      if (el) el.src = src;
    });
  };

  const syncVisibility = (toggleId, ...targetElements) => {
    const toggle = document.getElementById(toggleId);
    if (!toggle) return;

    const apply = () => {
      targetElements.forEach((el) => {
        if (el)
          toggle.checked
            ? el.classList.remove("d-none")
            : el.classList.add("d-none");
      });
    };

    toggle.addEventListener("change", apply);
    apply();
  };

  // =================================================================
  // 3. CONFIGURAÇÃO DE SOCKET E STATUS
  // =================================================================
  const socket = io();

  socket.on("connect", () =>
    updateBadges(UI.socketStatus, "Conectado", "bg-success"),
  );
  socket.on("disconnect", () =>
    updateBadges(UI.socketStatus, "Desconectado", "bg-danger"),
  );

  // =================================================================
  // 4. CONFIGURAÇÃO DOS GRÁFICOS (CHART.JS)
  // =================================================================

  const createChart = (ctxId, color, isMini = false, isTimeBased = false) => {
    const ctx = document.getElementById(ctxId);
    if (!ctx) return null;

    return new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: isMini ? "" : "Dados",
            data: [],
            borderColor: color,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: { display: !isMini && !isTimeBased, grid: { color: "#333" } },
          y: { display: false, grid: { color: "#333" } },
        },
        plugins: { legend: { display: false }, tooltip: { enabled: !isMini } },
        layout: { padding: 0 },
      },
    });
  };

  const charts = {
    main: {
      fft: createChart("chartFFT", "#00ff00"),
      raw: createChart("chartRaw", "#ffc107", false, true),
      filtered: createChart("chartFiltered", "#0dcaf0", false, true),
    },
    mini: {
      fft: createChart("miniChartFFT", "#00ff00", true),
      raw: createChart("miniChartRaw", "#ffc107", true, true),
      filtered: createChart("miniChartFiltered", "#0dcaf0", true, true),
    },
  };

  const clearAllCharts = () => {
    const allCharts = [
      charts.main.fft,
      charts.main.raw,
      charts.main.filtered,
      charts.mini.fft,
      charts.mini.raw,
      charts.mini.filtered,
    ];

    allCharts.forEach((chart) => {
      if (chart) {
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update(); // Força a atualização visual para vazio
      }
    });
  };

  const pushChartData = (chart, value, maxPoints) => {
    if (!chart) return;
    chart.data.labels.push("");
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > maxPoints) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
    chart.update("none");
  };

  // =================================================================
  // 5. LÓGICA DE FULLSCREEN, TOGGLES E LOCK
  // =================================================================

  const toggleFullscreen = (active) => {
    STATE.isFullscreen = active;
    const { body } = document;
    const { wrapper, hud, btnExpand } = UI.fullscreen;

    if (active) {
      body.classList.add("fullscreen-active");
      wrapper.classList.add("fullscreen");
      hud.classList.remove("d-none");
      btnExpand.innerHTML = '<i class="bi bi-arrows-collapse"></i>';
      Object.values(charts.mini).forEach((c) => c?.resize());
    } else {
      body.classList.remove("fullscreen-active");
      wrapper.classList.remove("fullscreen");
      hud.classList.add("d-none");
      btnExpand.innerHTML = '<i class="bi bi-arrows-fullscreen"></i>';
    }
  };

  UI.fullscreen.btnExpand.addEventListener("click", () =>
    toggleFullscreen(!STATE.isFullscreen),
  );
  UI.fullscreen.btnExit.addEventListener("click", () =>
    toggleFullscreen(false),
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && STATE.isFullscreen) toggleFullscreen(false);
  });

  // --- Lógica de Travar/Destravar ---
  const toggleLock = () => {
    STATE.isLocked = !STATE.isLocked;

    // 1. Atualiza Visual dos Botões
    UI.locks.forEach((btn) => {
      if (!btn) return;
      if (STATE.isLocked) {
        // TRAVADO (Verde)
        btn.innerHTML = '<i class="bi bi-lock-fill"></i>';
        btn.classList.replace("btn-outline-danger", "btn-success");
        btn.classList.replace("btn-danger", "btn-success");
      } else {
        // DESTRAVADO (Vermelho)
        btn.innerHTML = '<i class="bi bi-unlock-fill"></i>';
        btn.classList.replace("btn-success", "btn-outline-danger");
        btn.classList.replace("btn-success", "btn-danger");
      }
    });

    if (!STATE.isLocked) {
      clearAllCharts();
    }
  };

  // Adiciona evento de clique aos botões de lock
  UI.locks.forEach((btn) => {
    if (btn) btn.addEventListener("click", toggleLock);
  });

  // Configuração dos Toggles
  syncVisibility("toggle-fft", UI.cards.fft, UI.hudBoxes.fft);
  syncVisibility("toggle-raw", UI.cards.raw, UI.hudBoxes.raw);
  syncVisibility("toggle-filtered", UI.cards.filtered, UI.hudBoxes.filtered);

  // Toggle ROI específico
  if (UI.fullscreen.toggleRoi) {
    UI.fullscreen.toggleRoi.addEventListener("change", (e) => {
      STATE.showRoi = e.target.checked;
      UI.roiPreview.forEach((el) => {
        if (el) el.style.display = STATE.showRoi ? "block" : "none";
      });
    });
    UI.fullscreen.toggleRoi.dispatchEvent(new Event("change"));
  }

  // =================================================================
  // 6. CÂMERA E LOOP DE ENVIO
  // =================================================================

  navigator.mediaDevices
    .getUserMedia({ video: { width: 320, height: 240 } })
    .then((stream) => {
      UI.video.srcObject = stream;
      updateBadges(
        UI.cameraStatus,
        "Câmera ativa. Processando...",
        "bg-primary",
      );
      startSendingFrames();
    })
    .catch((err) => {
      console.error(err);
      updateBadges(UI.cameraStatus, "Erro: Câmera não permitida", "bg-danger");
    });

  function startSendingFrames() {
    setInterval(() => {
      UI.ctxFrame.drawImage(UI.video, 0, 0, 320, 240);
      UI.canvasFrame.toBlob(
        (blob) => {
          if (blob) {
            // --- NOVO: Envia também se está travado e se quer a imagem ROI ---
            socket.emit("process_frame", {
              image: blob,
              is_locked: STATE.isLocked,
              send_roi: STATE.showRoi,
            });
          }
        },
        "image/jpeg",
        0.5,
      );
    }, 100);
  }

  // =================================================================
  // 7. PROCESSAMENTO DE DADOS (SOCKET)
  // =================================================================

  socket.on("data_update", (msg) => {
    // 1. Limpa Overlay
    UI.ctxOverlay.clearRect(0, 0, 320, 240);

    // 2. Atualiza Imagem ROI
    if (msg.roi_image) {
      updateImages(UI.roiPreview, msg.roi_image);
    }

    // 3. Lógica de Detecção e Travamento
    if (msg.face_detected) {
      // Define a cor: Verde se travado, Vermelho se destravado
      const rectColor = msg.is_locked ? "#00ff00" : "#dc3545";

      if (msg.roi_rect) {
        const [x, y, w, h] = msg.roi_rect;
        UI.ctxOverlay.beginPath();
        UI.ctxOverlay.lineWidth = msg.is_locked ? 3 : 2; // Mais grosso se travado
        UI.ctxOverlay.strokeStyle = rectColor;
        UI.ctxOverlay.rect(x, y, w, h);
        UI.ctxOverlay.stroke();
      }

      // Se estiver TRAVADO, atualiza dados reais
      if (msg.is_locked) {
        updateText(UI.bpm, msg.bpm);
        updateBadges(UI.cameraStatus, "Calculando BPM...", "bg-success");

        // Atualiza Gráficos (Só se travado)
        // FFT
        if (msg.chart_data && msg.chart_data.x.length > 0) {
          const labels = msg.chart_data.x.map((v) => Math.round(v));
          charts.main.fft.data.labels = labels;
          charts.main.fft.data.datasets[0].data = msg.chart_data.y;
          charts.main.fft.update("none");

          if (STATE.isFullscreen) {
            charts.mini.fft.data.labels = labels;
            charts.mini.fft.data.datasets[0].data = msg.chart_data.y;
            charts.mini.fft.update("none");
          }
        }

        // Gráficos Tempo Real
        const isRawVisible = !UI.cards.raw.classList.contains("d-none");
        const isFilteredVisible =
          !UI.cards.filtered.classList.contains("d-none");

        if (isRawVisible)
          pushChartData(charts.main.raw, msg.raw_val, STATE.maxPoints);
        if (isFilteredVisible)
          pushChartData(
            charts.main.filtered,
            msg.filtered_val,
            STATE.maxPoints,
          );

        if (STATE.isFullscreen) {
          const isMiniRawVisible =
            !UI.hudBoxes.raw.classList.contains("d-none");
          const isMiniFilteredVisible =
            !UI.hudBoxes.filtered.classList.contains("d-none");

          if (isMiniRawVisible)
            pushChartData(charts.mini.raw, msg.raw_val, STATE.miniMaxPoints);
          if (isMiniFilteredVisible)
            pushChartData(
              charts.mini.filtered,
              msg.filtered_val,
              STATE.miniMaxPoints,
            );
        }
      } else {
        // Se estiver DESTRAVADO (Procurando rosto)
        updateText(UI.bpm, "--");
        updateBadges(
          UI.cameraStatus,
          "Rosto encontrado. Trave para medir.",
          "bg-warning text-dark",
        );
      }
    } else {
      // Nenhuma face detectada
      updateBadges(UI.cameraStatus, "Procurando rosto...", "bg-danger");
    }
  });
});
