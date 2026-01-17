document.addEventListener("DOMContentLoaded", () => {
  // --- Configuração SocketIO ---
  const socket = io();
  const socketStatusBadge = document.getElementById("socket-status");

  socket.on("connect", () => {
    socketStatusBadge.className = "badge bg-success";
    socketStatusBadge.innerText = "Conectado";
  });
  socket.on("disconnect", () => {
    socketStatusBadge.className = "badge bg-danger";
    socketStatusBadge.innerText = "Desconectado";
  });

  // --- Elementos DOM ---
  const videoElement = document.getElementById("user-video");
  const canvasElement = document.getElementById("frame-canvas");
  const overlayCanvas = document.getElementById("overlay-canvas");
  const overlayCtx = overlayCanvas.getContext("2d");
  const context = canvasElement.getContext("2d");
  const bpmEl = document.getElementById("bpm-value");
  const statusText = document.getElementById("status-msg");
  const roiPreview = document.getElementById("roi-preview");

  // --- Toggles Lógica ---
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

  // --- Configuração de Gráficos (Chart.js) ---
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

  const MAX_DATA_POINTS = 100;

  function updateRealTimeChart(chart, value) {
    chart.data.labels.push("");
    chart.data.datasets[0].data.push(value);

    if (chart.data.labels.length > MAX_DATA_POINTS) {
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
      statusText.innerText = "Câmera ativa. Processando...";
      // CORREÇÃO: Removido mt-3 para manter alinhamento
      statusText.className = "badge bg-primary";
      startSendingFrames();
    })
    .catch((err) => {
      console.error(err);
      statusText.innerText = "Erro: Câmera não permitida";
      // CORREÇÃO: Removido mt-3
      statusText.className = "badge bg-danger";
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
    overlayCtx.clearRect(0, 0, 320, 240);

    if (msg.face_detected) {
      bpmEl.innerText = msg.bpm;
      statusText.innerText = "Monitorando...";
      // CORREÇÃO: Removido mt-3
      statusText.className = "badge bg-success";

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
      statusText.innerText = "Procurando rosto...";
      // CORREÇÃO: Removido mt-3
      statusText.className = "badge bg-warning text-dark";
    }

    if (msg.chart_data && msg.chart_data.x.length > 0) {
      chartFFT.data.labels = msg.chart_data.x.map((v) => Math.round(v));
      chartFFT.data.datasets[0].data = msg.chart_data.y;
      chartFFT.update("none");
    }

    if (msg.face_detected) {
      if (!document.getElementById("card-raw").classList.contains("d-none")) {
        updateRealTimeChart(chartRaw, msg.raw_val);
      }
      if (
        !document.getElementById("card-filtered").classList.contains("d-none")
      ) {
        updateRealTimeChart(chartFiltered, msg.filtered_val);
      }
    }
  });
});
