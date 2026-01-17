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
        const layoutClasses = Array.from(el.classList).filter(
          (c) => !c.startsWith("bg-") && c !== "badge",
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
  // 5. LÓGICA DE FULLSCREEN E TOGGLES
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

  // Configuração dos Toggles
  syncVisibility("toggle-fft", UI.cards.fft, UI.hudBoxes.fft);
  syncVisibility("toggle-raw", UI.cards.raw, UI.hudBoxes.raw);
  syncVisibility("toggle-filtered", UI.cards.filtered, UI.hudBoxes.filtered);

  // Toggle ROI específico (Controla apenas a visibilidade da IMAGEM)
  if (UI.fullscreen.toggleRoi) {
    UI.fullscreen.toggleRoi.addEventListener("change", (e) => {
      STATE.showRoi = e.target.checked;
      UI.roiPreview.forEach((el) => {
        // Esconde ou mostra a tag <img>
        if (el) el.style.display = STATE.showRoi ? "block" : "none";
      });
    });
    // Trigger inicial
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
          if (blob) socket.emit("process_frame", { image: blob });
        },
        "image/jpeg",
        0.5,
      );
    }, 100);
  }

  // =================================================================
  // 7. PROCESSAMENTO DE DADOS (SOCKET) - LÓGICA CENTRAL
  // =================================================================

  socket.on("data_update", (msg) => {
    // 1. Limpa Overlay
    UI.ctxOverlay.clearRect(0, 0, 320, 240);

    // 2. Atualiza Imagem ROI (Independente de detecção facial, visibilidade controlada pelo CSS/Toggle)
    if (msg.roi_image) {
      updateImages(UI.roiPreview, msg.roi_image);
    }

    // 3. Lógica de Detecção
    if (msg.face_detected) {
      // Atualiza textos
      updateText(UI.bpm, msg.bpm);
      updateBadges(UI.cameraStatus, "Monitorando...", "bg-success");

      // --- CORREÇÃO AQUI ---
      // Desenha Retângulo Verde SEMPRE que houver coordenadas
      // Removemos a verificação "&& STATE.showRoi"
      if (msg.roi_rect) {
        const [x, y, w, h] = msg.roi_rect;
        UI.ctxOverlay.beginPath();
        UI.ctxOverlay.lineWidth = 2;
        UI.ctxOverlay.strokeStyle = "#00ff00";
        UI.ctxOverlay.rect(x, y, w, h);
        UI.ctxOverlay.stroke();
      }
    } else {
      updateBadges(
        UI.cameraStatus,
        "Procurando rosto...",
        "bg-warning text-dark",
      );
    }

    // 4. Atualização dos Gráficos

    // 4.1 FFT
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

    // 4.2 Tempo Real
    if (msg.face_detected) {
      const isRawVisible = !UI.cards.raw.classList.contains("d-none");
      const isFilteredVisible = !UI.cards.filtered.classList.contains("d-none");

      if (isRawVisible)
        pushChartData(charts.main.raw, msg.raw_val, STATE.maxPoints);
      if (isFilteredVisible)
        pushChartData(charts.main.filtered, msg.filtered_val, STATE.maxPoints);

      if (STATE.isFullscreen) {
        const isMiniRawVisible = !UI.hudBoxes.raw.classList.contains("d-none");
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
    }
  });
});
