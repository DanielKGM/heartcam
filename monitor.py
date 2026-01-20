import numpy as np
import cv2
import os
import time


class HeartRateMonitor:
    def __init__(self):
        self._init_face_cascade()

        self.face_rect = [0, 0, 0, 0]
        self.face_detected = False
        self.frame_counter = 0
        self.detection_frequency = 5

        # Configurações de Sinal
        self.min_frequency = 0.7  # ~42 BPM
        self.max_frequency = 3.0  # ~180 BPM

        # Buffer de sinal
        self.signal_buffer_size = 128  # ~8.5 seg a 15fps
        self.signal_index = 0

        # Dimensões de referência
        self.proc_width = 160
        self.proc_height = 120

        self.fps = 20  # Valor inicial (será ajustado dinamicamente)
        self.timestamps = []
        self.bpm_calculation_frequency = 2

        self.current_bpm = 0
        self.smoothed_bpm = 0
        self.alpha_smooth = 0.1  # Suavização visual

        self._init_buffers()

        self.psd_data = []
        self.freq_axis = []

    def _init_face_cascade(self):
        filename = "haarcascade_frontalface_alt.xml"
        local_path = os.path.join("models", filename)
        cascade_path = (
            local_path
            if os.path.exists(local_path)
            else os.path.join(cv2.data.haarcascades, filename)
        )
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def _init_buffers(self):
        self.raw_signal = np.zeros(self.signal_buffer_size)
        now = time.time()
        # Inicializa timestamps simulados para evitar FPS infinito no começo
        self.timestamps = [
            now - (i * (1 / self.fps)) for i in range(self.signal_buffer_size)
        ]
        self.timestamps.reverse()

        self.frequencies = np.zeros(self.signal_buffer_size)

    def _get_subface_coord(self, fh_x, fh_y, fh_w, fh_h):
        x, y, w, h = self.face_rect
        return [
            int(x + w * fh_x - (w * fh_w / 2.0)),
            int(y + h * fh_y - (h * fh_h / 2.0)),
            int(w * fh_w),
            int(h * fh_h),
        ]

    def _adaptive_smooth(self, current_val, new_val):
        if current_val == 0:
            return new_val
        return self.alpha_smooth * new_val + (1 - self.alpha_smooth) * current_val

    def _decode_frame(self, image_bytes):
        if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
            return None
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except:
            return None

    def reset(self):
        self.signal_index = 0
        self.current_bpm = 0
        self.smoothed_bpm = 0
        self.raw_signal.fill(0)
        self.face_detected = False
        self._init_buffers()
        self.psd_data = []
        self.freq_axis = []

    def _handle_unlocked_state(self, frame):
        if self.frame_counter % self.detection_frequency == 0 or not self.face_detected:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = list(
                self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.2,
                    minNeighbors=4,
                    minSize=(50, 50),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
            )

            if len(detected) > 0:
                detected.sort(key=lambda a: a[-1] * a[-2])
                self.face_rect = detected[-1]
                self.face_detected = True

        self.frame_counter = (self.frame_counter + 1) % 100

        roi_coords = None
        if self.face_detected:
            fx, fy, fw, fh = self._get_subface_coord(0.5, 0.18, 0.25, 0.15)
            roi_coords = [int(fx), int(fy), int(fw), int(fh)]

        return {
            "bpm": "--",
            "face_detected": self.face_detected,
            "roi_rect": roi_coords,
            "is_locked": False,
        }

    def _handle_locked_state(self, frame):
        fx, fy, fw, fh = self._get_subface_coord(0.5, 0.18, 0.25, 0.15)
        real_height, real_width, _ = frame.shape

        if not (fy >= 0 and fy + fh < real_height and fx >= 0 and fx + fw < real_width):
            self.reset()
            return {
                "bpm": "--",
                "face_detected": False,
                "roi_rect": None,
                "is_locked": False,
            }

        roi = frame[fy : fy + fh, fx : fx + fw]

        # Mantendo canal VERDE (melhor que a média RGB da inspiração)
        raw_val = np.mean(roi[:, :, 1])
        current_time = time.time()

        try:
            self._update_buffers(raw_val, current_time)
            filtered_val = self._process_1d_signal(current_time)

            # Normalização visual (0.0 a 1.0) para o quadrado piscante
            pulse_intensity = np.clip((filtered_val + 2) / 4, 0, 1)

            return {
                "bpm": round(self.current_bpm, 1) if self.current_bpm > 40 else "--",
                "face_detected": True,
                "roi_rect": [int(fx), int(fy), int(fw), int(fh)],
                "pulse_intensity": float(pulse_intensity),
                "raw_val": float(raw_val),
                "filtered_val": float(filtered_val),
                "is_locked": True,
                "chart_data": {"x": self.freq_axis, "y": self.psd_data},
            }
        except Exception as e:
            print(f"Error processing signal: {e}")
            self.reset()
            return {"bpm": "--", "face_detected": False, "is_locked": False}

    def _update_buffers(self, raw_val, current_time):
        self.signal_index = (self.signal_index + 1) % self.signal_buffer_size
        self.timestamps[self.signal_index] = current_time
        self.raw_signal[self.signal_index] = raw_val

    def _find_peaks_heuristic(self, freqs, mags):
        # Lógica portada do heartcam_forehead.py (função find_peaks e lógica adjacente)

        # 1. Encontra o pico máximo inicial na faixa válida completa
        if len(mags) == 0:
            return 0

        max_idx = np.argmax(mags)
        peak_freq = freqs[max_idx]
        final_idx = max_idx

        # 2. Correção de Harmônicos (Inspiration Logic)

        # Se detectou > 120 BPM (2 Hz), verifica se não é um harmônico do dobro
        # Ex: Detectou 140, mas na verdade é 70.
        if peak_freq > 2.0:
            half_freq = peak_freq / 2.0
            # Busca se existe um pico forte ao redor da metade da frequência
            search_mask = (freqs >= half_freq - 0.2) & (freqs <= half_freq + 0.2)
            if np.any(search_mask):
                # Pega os indices dessa sub-região
                sub_idxs = np.where(search_mask)[0]
                # Se o maior pico nessa região for significativo (> 60% do pico maximo)
                sub_max_idx = sub_idxs[np.argmax(mags[sub_idxs])]
                if mags[sub_max_idx] > 0.6 * mags[max_idx]:
                    final_idx = sub_max_idx

        # Se detectou < 50 BPM (0.83 Hz), força busca na faixa humana comum (60-100 BPM)
        # Ex: Ruído de baixa frequencia mascarando o pulso real
        elif peak_freq < 0.83:
            search_mask = (freqs >= 1.0) & (freqs <= 1.66)  # 60 a 100 BPM
            if np.any(search_mask):
                sub_idxs = np.where(search_mask)[0]
                sub_max_idx = sub_idxs[np.argmax(mags[sub_idxs])]
                # Se houver algo relevante ali, assume que é o coração
                if mags[sub_max_idx] > 0.5 * mags[max_idx]:
                    final_idx = sub_max_idx

        return final_idx

    def _process_1d_signal(self, current_time):
        prev_time_idx = (self.signal_index + 1) % self.signal_buffer_size
        t_start = self.timestamps[prev_time_idx]

        time_diff = current_time - t_start
        if time_diff > 1.0:
            self.fps = self.signal_buffer_size / time_diff

        self.fps = np.clip(self.fps, 10, 60)

        # Eixo de frequências completo
        all_freqs = np.fft.fftfreq(self.signal_buffer_size, d=1.0 / self.fps)

        # Preparação do Sinal
        signal = np.array(self.raw_signal)
        signal = np.roll(signal, -self.signal_index - 1)
        signal = signal - np.mean(signal)
        std = np.std(signal)
        signal = signal / (std if std > 1e-6 else 1)

        # FFT
        fft_values = np.fft.fft(signal)
        magnitude = np.abs(fft_values)

        # Filtros para Visualização e Cálculo
        # Faixa Estrita para BPM (0.7 a 3.0 Hz / 42 a 180 BPM)
        bpm_mask_indices = (all_freqs >= self.min_frequency) & (
            all_freqs <= self.max_frequency
        )

        # Dados para o Gráfico (apenas frequencias positivas dentro da faixa)
        valid_idx = np.where(bpm_mask_indices)[0]
        if len(valid_idx) > 0:
            self.psd_data = magnitude[valid_idx].tolist()
            self.freq_axis = (all_freqs[valid_idx] * 60.0).tolist()

        # Filtragem Temporal (para o visual do pulso)
        fft_masked = fft_values.copy()
        fft_masked[~bpm_mask_indices] = 0
        filtered_signal = np.real(np.fft.ifft(fft_masked))
        current_filtered_val = filtered_signal[-1]

        # Cálculo de BPM (lógica da inspiração aplicada)
        if (
            self.signal_index % self.bpm_calculation_frequency == 0
            and len(valid_idx) > 0
        ):

            # Recorta arrays apenas para a região de interesse para busca de picos
            roi_freqs = all_freqs[valid_idx]
            roi_mags = magnitude[valid_idx]

            # 1. Encontra o índice do pico usando a heurística de harmônicos
            local_peak_idx = self._find_peaks_heuristic(roi_freqs, roi_mags)

            # 2. Média Ponderada (Weighted Average) para precisão decimal
            # Pega o vizinho da esquerda e direita no array RECORTADO
            peak_freq = roi_freqs[local_peak_idx]

            # Tenta pegar vizinhos para suavizar
            try:
                # Indices globais (no array valid_idx)
                idx_prev = max(0, local_peak_idx - 1)
                idx_next = min(len(roi_mags) - 1, local_peak_idx + 1)

                # Somas ponderadas
                # (freq * mag) / sum(mag)
                weighted_freq_sum = 0
                mag_sum = 0

                for i in range(idx_prev, idx_next + 1):
                    weighted_freq_sum += roi_freqs[i] * roi_mags[i]
                    mag_sum += roi_mags[i]

                if mag_sum > 0:
                    refined_freq = weighted_freq_sum / mag_sum
                    instant_bpm = refined_freq * 60.0
                else:
                    instant_bpm = peak_freq * 60.0
            except:
                instant_bpm = peak_freq * 60.0

            # Suavização final
            if 40 <= instant_bpm <= 200:
                if self.smoothed_bpm == 0:
                    self.smoothed_bpm = instant_bpm
                else:
                    self.smoothed_bpm = self._adaptive_smooth(
                        self.smoothed_bpm, instant_bpm
                    )
                self.current_bpm = self.smoothed_bpm

        return current_filtered_val

    def process_frame(self, image_bytes, is_locked=False):
        frame = self._decode_frame(image_bytes)
        if frame is None:
            return None

        if not is_locked:
            return self._handle_unlocked_state(frame)
        else:
            return self._handle_locked_state(frame)
