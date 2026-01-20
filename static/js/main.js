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
    statusBar: [document.getElementById("status-bar")],
    cameraStatus: [
      document.getElementById("status-msg"),
      document.getElementById("hud-camera-status"),
    ],

    // Botões de Travar/Destravar
    locks: [
      document.getElementById("btn-lock-camera"),
      document.getElementById("btn-lock-hud"),
    ],

    // Controles de Tela Cheia
    fullscreen: {
      btnExpand: document.getElementById("btn-expand-camera"),
      btnExit: document.getElementById("btn-exit-fullscreen"),
      wrapper: document.getElementById("main-video-wrapper"),
      hud: document.getElementById("camera-hud"),
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
    isLocked: false,
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
  // 3. CONFIGURAÇÃO DE SOCKET E GRÁFICOS
  // =================================================================
  const socket = io();

  socket.on("connect", () => {
    updateBadges(UI.socketStatus, "Conectado", "bg-success");
    if (UI.statusBar[0])
      UI.statusBar[0].className =
        "position-absolute top-0 start-0 w-100 bg-success";
  });
  socket.on("disconnect", () => {
    updateBadges(UI.socketStatus, "Desconectado", "bg-danger");
    if (UI.statusBar[0])
      UI.statusBar[0].className =
        "position-absolute top-0 start-0 w-100 bg-danger";
  });

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
  // 4. LÓGICA DE TRAVAMENTO E TELA CHEIA
  // =================================================================

  const toggleLock = (forceState = null) => {
    if (forceState !== null) {
      STATE.isLocked = forceState;
    } else {
      STATE.isLocked = !STATE.isLocked;
    }

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
  };

  UI.locks.forEach((btn) => {
    if (btn) btn.addEventListener("click", () => toggleLock());
  });

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

  // Toggles
  syncVisibility("toggle-fft", UI.cards.fft, UI.hudBoxes.fft);
  syncVisibility("toggle-raw", UI.cards.raw, UI.hudBoxes.raw);
  syncVisibility("toggle-filtered", UI.cards.filtered, UI.hudBoxes.filtered);

  // =================================================================
  // 5. CÂMERA E LOOP DE ENVIO
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
      UI.video.play();
      startSendingFrames();
    })
    .catch((err) => {
      console.error(err);
      updateBadges(UI.cameraStatus, "Erro: Câmera bloqueada", "bg-danger");
    });

  let isSending = false;

  function startSendingFrames() {
    setInterval(() => {
      if (!socket.connected || isSending) return;

      UI.ctxFrame.drawImage(UI.video, 0, 0, 320, 240);
      UI.canvasFrame.toBlob(
        (blob) => {
          if (blob) {
            isSending = true;

            socket.emit(
              "process_frame",
              {
                image: blob,
                is_locked: STATE.isLocked,
              },
              (response) => {
                isSending = false;
              },
            );

            setTimeout(() => {
              isSending = false;
            }, 200);
          }
        },
        "image/jpeg",
        0.8,
      );
    }, 100); // 10 FPS
  }

  // =================================================================
  // 6. PROCESSAMENTO DE DADOS (SOCKET)
  // =================================================================

  socket.on("data_update", (msg) => {
    // 1. Limpa Overlay
    UI.ctxOverlay.clearRect(0, 0, 320, 240);

    // 2. Desenha ROI (Retângulo ou Feedback Visual)
    if (msg.roi_rect) {
      const [x, y, w, h] = msg.roi_rect;

      if (
        msg.is_locked &&
        msg.face_detected &&
        msg.pulse_intensity !== undefined
      ) {
        // MODO TRAVADO: Desenha o quadrado PREENCHIDO com opacidade variável
        // A intensidade vem de 0 a 1. Usamos isso para controlar a opacidade (alpha).
        // Um multiplicador (ex: 0.6) evita que fique 100% opaco.
        const opacity = msg.pulse_intensity * 0.7;

        UI.ctxOverlay.fillStyle = `rgba(0, 255, 0, ${opacity})`;
        UI.ctxOverlay.fillRect(x, y, w, h);

        // Borda fina para delimitar
        UI.ctxOverlay.lineWidth = 1;
        UI.ctxOverlay.strokeStyle = "rgba(0, 255, 0, 0.5)";
        UI.ctxOverlay.strokeRect(x, y, w, h);
      } else {
        // MODO BUSCA: Apenas borda
        const rectColor = msg.face_detected ? "#00ff00" : "#dc3545";
        UI.ctxOverlay.beginPath();
        UI.ctxOverlay.lineWidth = 2;
        UI.ctxOverlay.strokeStyle = rectColor;
        UI.ctxOverlay.rect(x, y, w, h);
        UI.ctxOverlay.stroke();
      }
    }

    // 3. Lógica de UI (Badges e Gráficos)
    if (msg.face_detected) {
      if (msg.is_locked && STATE.isLocked) {
        updateText(UI.bpm, msg.bpm);
        updateBadges(UI.cameraStatus, "Calculando BPM...", "bg-success");

        // Atualiza Gráficos
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
        updateText(UI.bpm, "--");
        updateBadges(
          UI.cameraStatus,
          "Rosto encontrado. Trave para medir.",
          "bg-warning text-dark",
        );
      }
    } else {
      updateText(UI.bpm, "--");
      updateBadges(UI.cameraStatus, "Procurando rosto...", "bg-danger");
    }
  });

  // =================================================================
  // 7. AUTO-DESTRAVAMENTO NO SCROLL (Interruption Logic)
  // =================================================================

  const toastContainer = document.createElement("div");
  toastContainer.className =
    "toast-container position-fixed bottom-0 end-0 p-3";
  toastContainer.style.zIndex = "1100";

  toastContainer.innerHTML = `
    <div id="scrollToast" class="toast align-items-center text-bg-warning border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi bi-exclamation-circle-fill me-2"></i>
          Navegadores desativam o acesso à câmera quando a aba não está visível. Gráficos e BPM podem não ser atualizados.
        </div>
        <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close" style="filter: none;"></button>
      </div>
    </div>
  `;
  document.body.appendChild(toastContainer);

  const scrollToast = new bootstrap.Toast(
    document.getElementById("scrollToast"),
  );

  const observerOptions = {
    root: null,
    threshold: 0.1,
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting && STATE.isLocked) {
        toggleLock(false);
        scrollToast.show();
      }
    });
  }, observerOptions);

  const cameraCard = document.getElementById("camera-card");
  if (cameraCard) {
    observer.observe(cameraCard);
  }
});
