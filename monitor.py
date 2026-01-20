import numpy as np
import cv2
import os
import base64
import time


class HeartRateMonitor:
    def __init__(self):
        self._init_face_cascade()

        self.face_rect = [0, 0, 0, 0]
        self.face_detected = False
        self.frame_counter = 0
        self.detection_frequency = 5

        self.levels = 3
        self.alpha = 170
        self.min_frequency = 0.66
        self.max_frequency = 3.0

        # Separação dos buffers
        self.signal_buffer_size = 128  # Buffer longo
        self.video_buffer_size = 16  # buffer curto (previsualização)

        self.signal_index = 0
        self.video_index = 0

        self.proc_width = 160
        self.proc_height = 120
        self.video_channels = 3

        self.fps = 15
        self.timestamps = [0] * self.signal_buffer_size
        self.bpm_calculation_frequency = 1
        self.current_bpm = 0
        self.smoothed_bpm = 0

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
        h = self.proc_height // (2**self.levels)
        w = self.proc_width // (2**self.levels)

        self.video_gauss = np.zeros((self.video_buffer_size, h, w, self.video_channels))
        self.raw_signal = np.zeros(self.signal_buffer_size)

        self.frequencies = (
            (1.0 * self.fps)
            * np.arange(self.signal_buffer_size)
            / (1.0 * self.signal_buffer_size)
        )
        self.mask = (self.frequencies >= self.min_frequency) & (
            self.frequencies <= self.max_frequency
        )

    def _build_gauss(self, frame, levels):
        pyramid = [frame]
        for _ in range(levels):
            frame = cv2.pyrDown(frame)
            pyramid.append(frame)
        return pyramid

    def _reconstruct_frame(self, pyramid, index, levels):
        filtered_frame = pyramid[index]
        for _ in range(levels):
            filtered_frame = cv2.pyrUp(filtered_frame)
        filtered_frame = filtered_frame[: self.proc_height, : self.proc_width]
        return filtered_frame

    def _get_subface_coord(self, fh_x, fh_y, fh_w, fh_h):
        x, y, w, h = self.face_rect
        return [
            int(x + w * fh_x - (w * fh_w / 2.0)),
            int(y + h * fh_y - (h * fh_h / 2.0)),
            int(w * fh_w),
            int(h * fh_h),
        ]

    def _adaptive_smooth(self, current_val, new_val, fps):
        alpha = 0.05 * (30 / max(fps, 1))
        alpha = np.clip(alpha, 0.01, 0.5)

        if current_val == 0:
            return new_val
        return alpha * new_val + (1 - alpha) * current_val

    def _is_skin_pixel(self, roi):
        if roi is None or roi.size == 0:
            return False
        b = np.mean(roi[:, :, 0])
        g = np.mean(roi[:, :, 1])
        r = np.mean(roi[:, :, 2])
        return (r > g) and (r > b)

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
        self.video_index = 0
        self.current_bpm = 0
        self.smoothed_bpm = 0
        self.raw_signal.fill(0)
        self.video_gauss.fill(0)
        self.timestamps = [0] * self.signal_buffer_size
        self.psd_data = []
        self.freq_axis = []

    def _handle_unlocked_state(self, frame):
        self.reset()

        if self.frame_counter % self.detection_frequency == 0 or not self.face_detected:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = list(
                self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.3,
                    minNeighbors=4,
                    minSize=(40, 40),
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

    def _handle_locked_state(self, frame, send_roi):
        fx, fy, fw, fh = self._get_subface_coord(0.5, 0.18, 0.25, 0.15)
        real_height, real_width, _ = frame.shape

        if not (fy >= 0 and fy + fh < real_height and fx >= 0 and fx + fw < real_width):
            return {
                "bpm": "--",
                "face_detected": True,
                "roi_rect": None,
                "is_locked": True,
            }

        roi = frame[fy : fy + fh, fx : fx + fw]

        if not self._is_skin_pixel(roi):
            self.reset()
            return {
                "bpm": "--",
                "face_detected": False,
                "roi_rect": [fx, fy, fw, fh],
                "is_locked": True,
            }

        raw_val = np.mean(roi[:, :, 1])
        current_time = time.time()

        try:
            detection_frame = cv2.resize(roi, (self.proc_width, self.proc_height))

            self._update_buffers(detection_frame, raw_val, current_time)

            filtered_val = self._process_1d_signal(current_time)

            roi_output_b64 = None
            if send_roi:
                roi_output_b64 = self._generate_visual_feedback(detection_frame)

            return {
                "bpm": round(self.current_bpm, 1) if self.current_bpm > 40 else "--",
                "face_detected": True,
                "roi_rect": [int(fx), int(fy), int(fw), int(fh)],
                "roi_image": roi_output_b64,
                "raw_val": float(raw_val),
                "filtered_val": float(filtered_val),
                "is_locked": True,
                "chart_data": {"x": self.freq_axis, "y": self.psd_data},
            }
        except Exception:
            self.reset()
            return {"bpm": "--", "face_detected": True, "is_locked": True}

    def _update_buffers(self, detection_frame, raw_green_val, current_time):
        # Atualiza índices circulares
        self.signal_index = (self.signal_index + 1) % self.signal_buffer_size
        self.video_index = (self.video_index + 1) % self.video_buffer_size

        # Atualiza dados de sinal (Math)
        self.timestamps[self.signal_index] = current_time
        self.raw_signal[self.signal_index] = raw_green_val

        # Atualiza dados de vídeo (Visual)
        pyramid = self._build_gauss(detection_frame, self.levels + 1)
        current_level = pyramid[self.levels]
        self.video_gauss[self.video_index] = current_level

    def _process_1d_signal(self, current_time):
        # Usa buffer de sinal (tamanho 128)
        t_start = self.timestamps[(self.signal_index + 1) % self.signal_buffer_size]
        if t_start > 0 and current_time > t_start:
            self.fps = self.signal_buffer_size / (current_time - t_start)

        # Atualiza frequências para o buffer matemático
        self.frequencies = (
            (1.0 * self.fps)
            * np.arange(self.signal_buffer_size)
            / (1.0 * self.signal_buffer_size)
        )
        self.mask = (self.frequencies >= self.min_frequency) & (
            self.frequencies <= self.max_frequency
        )

        signal = np.concatenate(
            (
                self.raw_signal[self.signal_index + 1 :],
                self.raw_signal[: self.signal_index + 1],
            )
        )

        signal = signal - np.mean(signal)
        signal = signal / (np.std(signal) + 1e-6)

        fft_values = np.fft.fft(signal)

        magnitude = np.abs(fft_values)
        magnitude[self.mask == False] = 0

        valid_idx = np.nonzero(self.mask)
        self.psd_data = magnitude[valid_idx].tolist()
        self.freq_axis = (self.frequencies[valid_idx] * 60.0).tolist()

        fft_masked = fft_values.copy()
        fft_masked[self.mask == False] = 0
        filtered_signal = np.real(np.fft.ifft(fft_masked))

        current_filtered_val = filtered_signal[self.signal_buffer_size - 1] * self.alpha

        if self.signal_index % self.bpm_calculation_frequency == 0:
            idx = np.argmax(magnitude)
            peak_freq = self.frequencies[idx]

            if peak_freq * 60 > 100:
                half_idx = int(idx / 2)
                if magnitude[half_idx] > 0.6 * magnitude[idx]:
                    idx = half_idx
                    peak_freq = self.frequencies[idx]

            elif peak_freq * 60 < 50:
                min_human_idx = np.argmax(self.frequencies >= 1.0)
                max_human_idx = np.argmax(self.frequencies >= 1.7)

                human_range_mags = magnitude[min_human_idx:max_human_idx]

                if len(human_range_mags) > 0:
                    local_peak = np.argmax(human_range_mags)
                    possible_idx = min_human_idx + local_peak
                    if magnitude[possible_idx] > 0.5 * magnitude[idx]:
                        idx = possible_idx

            freqs = []
            mags = []

            for i in [idx - 1, idx, idx + 1]:
                if 0 <= i < len(self.frequencies):
                    freqs.append(self.frequencies[i])
                    mags.append(magnitude[i])

            mag_sum = sum(mags)
            if mag_sum > 0:
                instant_bpm = 60 * sum(f * (m / mag_sum) for f, m in zip(freqs, mags))
            else:
                instant_bpm = self.frequencies[idx] * 60

            if self.smoothed_bpm == 0:
                self.smoothed_bpm = instant_bpm
            else:
                self.smoothed_bpm = self._adaptive_smooth(
                    self.smoothed_bpm, instant_bpm, self.fps
                )
            self.current_bpm = self.smoothed_bpm

        return current_filtered_val

    def _generate_visual_feedback(self, detection_frame):
        vid_frequencies = (
            (1.0 * self.fps)
            * np.arange(self.video_buffer_size)
            / (1.0 * self.video_buffer_size)
        )
        vid_mask = (vid_frequencies >= self.min_frequency) & (
            vid_frequencies <= self.max_frequency
        )

        fourier_transform = np.fft.fft(self.video_gauss, axis=0)
        fourier_transform[vid_mask == False] = 0

        filtered = np.real(np.fft.ifft(fourier_transform, axis=0))

        filtered_frame = self._reconstruct_frame(
            filtered, self.video_index, self.levels
        )

        filtered_frame = filtered_frame * self.alpha

        b_channel, g_channel, r_channel = cv2.split(filtered_frame)

        empty_channel = np.zeros_like(g_channel)
        filtered_frame_visual = cv2.merge((empty_channel, g_channel, empty_channel))

        output_frame = detection_frame + filtered_frame_visual
        output_frame = cv2.convertScaleAbs(output_frame)

        _, buffer_img = cv2.imencode(".jpg", output_frame)
        return base64.b64encode(buffer_img).decode("utf-8")

    def process_frame(self, image_bytes, is_locked=False, send_roi=False):
        frame = self._decode_frame(image_bytes)
        if frame is None:
            return None

        if not is_locked:
            return self._handle_unlocked_state(frame)
        else:
            return self._handle_locked_state(frame, send_roi)
