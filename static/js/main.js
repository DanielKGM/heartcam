document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  const socketStatusBadge = document.getElementById("socket-status");
  const hudSocketStatus = document.getElementById("hud-socket-status"); // NOVO

  // Atualiza status em ambos os lugares (Normal e HUD)
  const updateStatus = (isConnected) => {
    const text = isConnected ? "Conectado" : "Desconectado";
    const cls = isConnected ? "badge bg-success" : "badge bg-danger";

    socketStatusBadge.className = cls;
    socketStatusBadge.innerText = text;

    // HUD Status (com classes extras de posicionamento se necessário)
    hudSocketStatus.className = cls + " mb-1 d-block";
    hudSocketStatus.innerText = text;
  };

  socket.on("connect", () => updateStatus(true));
  socket.on("disconnect", () => updateStatus(false));

  // --- Elementos DOM ---
  const videoElement = document.getElementById("user-video");
  const canvasElement = document.getElementById("frame-canvas");
  const overlayCanvas = document.getElementById("overlay-canvas");
  const overlayCtx = overlayCanvas.getContext("2d");
  const context = canvasElement.getContext("2d");

  const bpmEl = document.getElementById("bpm-value");
  const hudBpmEl = document.getElementById("hud-bpm-value"); // NOVO

  const statusText = document.getElementById("status-msg");
  const hudStatusText = document.getElementById("hud-camera-status");

  const roiPreview = document.getElementById("roi-preview");

  // Elementos de Fullscreen
  const btnExpand = document.getElementById("btn-expand-camera");
  const btnExit = document.getElementById("btn-exit-fullscreen");
  const videoWrapper = document.getElementById("main-video-wrapper");
  const cameraHud = document.getElementById("camera-hud");
  const body = document.body;

  // --- Lógica de Fullscreen ---
  let isFullscreen = false;

  const toggleFullscreen = (active) => {
    isFullscreen = active;

    if (isFullscreen) {
      body.classList.add("fullscreen-active");
      videoWrapper.classList.add("fullscreen");
      cameraHud.classList.remove("d-none");
      btnExpand.innerHTML = '<i class="bi bi-arrows-collapse"></i>';

      // Força resize dos gráficos mini
      miniChartFFT.resize();
      miniChartRaw.resize();
      miniChartFiltered.resize();
    } else {
      body.classList.remove("fullscreen-active");
      videoWrapper.classList.remove("fullscreen");
      cameraHud.classList.add("d-none");
      btnExpand.innerHTML = '<i class="bi bi-fullscreen"></i>';
    }
  };

  btnExpand.addEventListener("click", () => {
    toggleFullscreen(!isFullscreen);
  });

  btnExit.addEventListener("click", () => {
    toggleFullscreen(false);
  });

  // Esc para sair do fullscreen
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isFullscreen) {
      btnExpand.click();
    }
  });

  // --- Toggles Lógica (Mantém igual) ---
  const setupToggle = (id, targetId) => {
    const el = document.getElementById(targetId);
    if (el) {
      document.getElementById(id).addEventListener("change", (e) => {
        if (e.target.checked) el.classList.remove("d-none");
        else el.classList.add("d-none");
      });
    }
  };
  setupToggle("toggle-fft", "card-fft");
  setupToggle("toggle-raw", "card-raw");
  setupToggle("toggle-filtered", "card-filtered");

  document.getElementById("toggle-roi").addEventListener("change", (e) => {
    roiPreview.style.display = e.target.checked ? "block" : "none";
  });

  // --- CHART.JS CONFIGURATIONS ---

  // Helper para gráficos normais
  const createLineChart = (ctx, label, color, isTimeBased = false) => {
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: label,
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
          x: { display: !isTimeBased, grid: { color: "#333" } },
          y: { display: false, grid: { color: "#333" } },
        },
        plugins: { legend: { display: false } },
      },
    });
  };

  // Helper para MINI GRÁFICOS (HUD) - Minimalistas (sem eixos, sem grid)
  const createMiniChart = (ctx, color) => {
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
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
        scales: { x: { display: false }, y: { display: false } }, // Sem eixos
        plugins: { legend: { display: false }, tooltip: { enabled: false } }, // Sem tooltip
        layout: { padding: 0 },
      },
    });
  };

  // Gráficos Principais
  const chartFFT = createLineChart(
    document.getElementById("chartFFT"),
    "Magnitude",
    "#00ff00",
  );
  const chartRaw = createLineChart(
    document.getElementById("chartRaw"),
    "Intensidade",
    "#ffc107",
    true,
  );
  const chartFiltered = createLineChart(
    document.getElementById("chartFiltered"),
    "Pulso",
    "#0dcaf0",
    true,
  );

  // Gráficos Mini (HUD)
  const miniChartFFT = createMiniChart(
    document.getElementById("miniChartFFT"),
    "#00ff00",
  );
  const miniChartRaw = createMiniChart(
    document.getElementById("miniChartRaw"),
    "#ffc107",
  );
  const miniChartFiltered = createMiniChart(
    document.getElementById("miniChartFiltered"),
    "#0dcaf0",
  );

  const MAX_DATA_POINTS = 100;
  const MINI_MAX_POINTS = 50; // Menos pontos para os minis para não poluir

  // Função para atualizar gráficos de tempo (Raw e Filtered)
  function updateRealTimeChart(chart, value, maxPoints) {
    chart.data.labels.push("");
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > maxPoints) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
    chart.update("none");
  }

  // --- Camera e Loop de Envio ---
  navigator.mediaDevices
    .getUserMedia({ video: { width: 320, height: 240 } })
    .then((stream) => {
      videoElement.srcObject = stream;

      const msg = "Câmera ativa. Processando...";
      statusText.innerText = msg;
      statusText.className = "badge bg-primary";

      hudStatusText.innerText = msg;
      hudStatusText.className = "badge bg-primary d-block"; // HUD

      startSendingFrames();
    })
    .catch((err) => {
      console.error(err);
      const msg = "Erro: Câmera não permitida";
      statusText.innerText = msg;
      statusText.className = "badge bg-danger";

      hudStatusText.innerText = msg;
      hudStatusText.className = "badge bg-danger d-block"; // HUD
    });

  function startSendingFrames() {
    setInterval(() => {
      context.drawImage(videoElement, 0, 0, 320, 240);
      canvasElement.toBlob(
        (blob) => {
          if (blob) socket.emit("process_frame", { image: blob });
        },
        "image/jpeg",
        0.5,
      );
    }, 100);
  }

  // --- Recebimento de Dados ---
  socket.on("data_update", (msg) => {
    // Limpa overlay (lembre-se de ajustar para resolução de tela cheia se necessário, mas o canvas estica via CSS)
    overlayCtx.clearRect(0, 0, 320, 240);

    if (msg.face_detected) {
      // Atualiza BPM Principal e HUD
      bpmEl.innerText = msg.bpm;
      hudBpmEl.innerText = msg.bpm;

      // Atualiza Texto Status
      const stTxt = "Monitorando...";
      const stCls = "badge bg-success";
      statusText.innerText = stTxt;
      statusText.className = stCls;

      hudStatusText.innerText = stTxt;
      hudStatusText.className = stCls + " d-block";

      if (msg.roi_rect) {
        const [x, y, w, h] = msg.roi_rect;
        overlayCtx.beginPath();
        overlayCtx.lineWidth = 3;
        overlayCtx.strokeStyle = "#00ff00";
        overlayCtx.rect(x, y, w, h);
        overlayCtx.stroke();
      }

      if (msg.roi_image) {
        roiPreview.src = "data:image/jpeg;base64," + msg.roi_image;
      }
    } else {
      const stTxt = "Procurando rosto...";
      const stCls = "badge bg-warning text-dark";
      statusText.innerText = stTxt;
      statusText.className = stCls;

      hudStatusText.innerText = stTxt;
      hudStatusText.className = stCls + " d-block";
    }

    // --- ATUALIZAÇÃO DOS GRÁFICOS ---

    // 1. FFT (Vetor Completo)
    if (msg.chart_data && msg.chart_data.x.length > 0) {
      const labels = msg.chart_data.x.map((v) => Math.round(v));

      // Gráfico Principal
      chartFFT.data.labels = labels;
      chartFFT.data.datasets[0].data = msg.chart_data.y;
      chartFFT.update("none");

      // Mini Gráfico (Só atualiza se fullscreen estiver ativo para economizar recursos)
      if (isFullscreen) {
        miniChartFFT.data.labels = labels;
        miniChartFFT.data.datasets[0].data = msg.chart_data.y;
        miniChartFFT.update("none");
      }
    }

    // 2. Tempo Real (Raw e Filtered)
    if (msg.face_detected) {
      // Principal
      if (!document.getElementById("card-raw").classList.contains("d-none")) {
        updateRealTimeChart(chartRaw, msg.raw_val, MAX_DATA_POINTS);
      }
      if (
        !document.getElementById("card-filtered").classList.contains("d-none")
      ) {
        updateRealTimeChart(chartFiltered, msg.filtered_val, MAX_DATA_POINTS);
      }

      // Mini Gráficos (HUD)
      if (isFullscreen) {
        updateRealTimeChart(miniChartRaw, msg.raw_val, MINI_MAX_POINTS);
        updateRealTimeChart(
          miniChartFiltered,
          msg.filtered_val,
          MINI_MAX_POINTS,
        );
      }
    }
  });
});
