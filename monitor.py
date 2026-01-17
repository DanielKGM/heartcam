import numpy as np
import cv2
import os
import base64
import time

class HeartRateMonitor:
    def __init__(self):
        # --- Configurações de Detecção ---
        self._init_face_cascade()
        
        # Estado
        self.face_rect = [0, 0, 0, 0]
        self.face_detected = False
        self.frame_counter = 0
        self.detection_frequency = 5 

        # --- Parâmetros de Processamento (EVM) ---
        self.levels = 3
        self.alpha = 170
        self.min_frequency = 1.0  # 60 BPM
        self.max_frequency = 2.0  # 120 BPM
        self.buffer_size = 150
        self.buffer_index = 0
        
        self.proc_width = 160
        self.proc_height = 120
        self.video_channels = 3
        
        # --- Controle de Tempo e BPM ---
        self.fps = 15 
        self.timestamps = [0] * self.buffer_size 
        self.bpm_calculation_frequency = 10
        self.current_bpm = 0
        self.smoothed_bpm = 0 

        # Buffers
        self._init_buffers()

        # Dados para Gráfico
        self.psd_data = [] 
        self.freq_axis = []

    def _init_face_cascade(self):
        cascade_filename = "haarcascade_frontalface_alt.xml"
        cascade_path = cascade_filename if os.path.exists(cascade_filename) else \
                       os.path.join(cv2.data.haarcascades, cascade_filename)
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def _init_buffers(self):
        # Buffer circular de vídeo (EVM)
        # Nota: proc_height e proc_width divididos por 2^levels devido à pirâmide
        h = self.proc_height // (2 ** self.levels)
        w = self.proc_width // (2 ** self.levels)
        
        self.video_gauss = np.zeros((self.buffer_size, h, w, self.video_channels))
        
        # Buffer para média da FFT
        self.fourier_transform_avg = np.zeros((self.buffer_size))
        
        # Eixo de Frequências (Dinâmico)
        self.frequencies = np.zeros((self.buffer_size))
        self.mask = np.zeros((self.buffer_size), dtype=bool)

    # CORE: Helpers de Imagem
    
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
        # Garante o tamanho exato cortando bordas extras geradas pelo pyrUp
        filtered_frame = filtered_frame[:self.proc_height, :self.proc_width]
        return filtered_frame

    def _get_subface_coord(self, fh_x, fh_y, fh_w, fh_h):
        x, y, w, h = self.face_rect
        return [int(x + w * fh_x - (w * fh_w / 2.0)),
                int(y + h * fh_y - (h * fh_h / 2.0)),
                int(w * fh_w),
                int(h * fh_h)]
    
    def _smooth_value(self, current_val, new_val, alpha=0.15):
        if current_val == 0: return new_val
        return alpha * new_val + (1 - alpha) * current_val

    # FASE 1: Decodificação e Entrada

    def _decode_frame(self, image_bytes):
        if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
            return None
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except:
            return None

    # FASE 2: Lógica de Estado (Destravado vs Travado)

    def _handle_unlocked_state(self, frame):
        """Procura o rosto e retorna apenas coordenadas para desenho."""
        self.buffer_index = 0
        self.current_bpm = 0
        self.smoothed_bpm = 0
        
        # Roda detecção se for a hora ou se não tiver rosto ainda
        if self.frame_counter % self.detection_frequency == 0 or not self.face_detected:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = list(self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.3, min_neighbors=4, minSize=(40, 40), flags=cv2.CASCADE_SCALE_IMAGE
            ))
            
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
            'bpm': "--",
            'face_detected': self.face_detected,
            'roi_rect': roi_coords,
            'is_locked': False
        }

    def _handle_locked_state(self, frame, send_roi):
        """Processamento principal: EVM + FFT + BPM."""
        fx, fy, fw, fh = self._get_subface_coord(0.5, 0.18, 0.25, 0.15)
        real_height, real_width, _ = frame.shape

        # Validação de limites
        if not (fy >= 0 and fy+fh < real_height and fx >= 0 and fx+fw < real_width):
             # Se perdeu o enquadramento, retorna erro suave
             return {'bpm': "--", 'face_detected': True, 'roi_rect': None, 'is_locked': True}

        roi = frame[fy:fy+fh, fx:fx+fw]
        raw_val = np.mean(roi[:, :, 1]) # Canal Verde
        current_time = time.time()

        try:
            # 1. Prepara e armazena no buffer (Resize & Pyramid)
            detection_frame = cv2.resize(roi, (self.proc_width, self.proc_height))
            fourier_transform = self._update_buffers(detection_frame, current_time)

            # 2. Calcula BPM (Matemática Pura)
            self._calculate_bpm(fourier_transform, current_time)

            # 3. Gera Feedback Visual (Se solicitado)
            filtered_val, roi_output_b64 = self._generate_visual_feedback(detection_frame, fourier_transform, send_roi)

            # Avança o buffer
            self.buffer_index = (self.buffer_index + 1) % self.buffer_size

            return {
                'bpm': round(self.current_bpm, 1) if self.current_bpm > 40 else "--",
                'face_detected': True,
                'roi_rect': [int(fx), int(fy), int(fw), int(fh)],
                'roi_image': roi_output_b64,
                'raw_val': float(raw_val),
                'filtered_val': float(filtered_val),
                'is_locked': True,
                'chart_data': {'x': self.freq_axis, 'y': self.psd_data}
            }
        except Exception:
            # Em caso de erro numérico, não quebra a aplicação
            return {'bpm': "--", 'face_detected': True, 'is_locked': True}

    # FASE 3: Processamento Matemático e Visual

    def _update_buffers(self, detection_frame, current_time):
        """Atualiza pirâmide gaussiana e timestamps."""
        self.timestamps[self.buffer_index] = current_time
        
        pyramid = self._build_gauss(detection_frame, self.levels + 1)
        current_level = pyramid[self.levels]
        self.video_gauss[self.buffer_index] = current_level
        
        return np.fft.fft(self.video_gauss, axis=0)

    def _calculate_bpm(self, fourier_transform, current_time):
        """FPS Dinâmico + Média Ponderada + Suavização."""
        if self.buffer_index % self.bpm_calculation_frequency != 0:
            return

        # 1. Calcula FPS real baseado no tempo que levou para encher o buffer
        t_start = self.timestamps[(self.buffer_index + 1) % self.buffer_size]
        if current_time > t_start:
            self.fps = self.buffer_size / (current_time - t_start)

        # 2. Atualiza Eixos e Máscara
        self.frequencies = (1.0 * self.fps) * np.arange(self.buffer_size) / (1.0 * self.buffer_size)
        self.mask = (self.frequencies >= self.min_frequency) & (self.frequencies <= self.max_frequency)

        # 3. Prepara FFT para análise (Zera frequências inúteis)
        # Nota: Usamos uma cópia para análise 1D, não alteramos o FT original usado para reconstrução de imagem
        ft_analysis = fourier_transform.copy()
        ft_analysis[self.mask == False] = 0

        # Média Espacial (Transforma 3D em 1D)
        for buf in range(self.buffer_size):
            self.fourier_transform_avg[buf] = np.real(ft_analysis[buf]).mean()

        # 4. Encontra Pico e Vizinhos (Weighted Average)
        idx = np.argmax(self.fourier_transform_avg)
        
        if idx > 0 and idx < self.buffer_size - 1:
            mag_prev, mag_curr, mag_next = self.fourier_transform_avg[idx-1:idx+2]
            
            # Fórmula da Média Ponderada
            numerator = (self.frequencies[idx-1]*mag_prev + 
                         self.frequencies[idx]*mag_curr + 
                         self.frequencies[idx+1]*mag_next)
            denominator = (mag_prev + mag_curr + mag_next)
            
            if denominator != 0:
                weighted_freq = numerator / denominator
                instant_bpm = 60.0 * weighted_freq
            else:
                instant_bpm = 60.0 * self.frequencies[idx]
        else:
            instant_bpm = 60.0 * self.frequencies[idx]

        # 5. Suavização (Smooth)
        if self.smoothed_bpm == 0:
            self.smoothed_bpm = instant_bpm
        else:
            self.smoothed_bpm = self._smooth_value(self.smoothed_bpm, instant_bpm)
        
        self.current_bpm = self.smoothed_bpm

        # 6. Dados para Exportação (Gráfico)
        valid_idx = np.nonzero(self.mask)
        self.psd_data = self.fourier_transform_avg[valid_idx].tolist()
        self.freq_axis = (self.frequencies[valid_idx] * 60.0).tolist()

    def _generate_visual_feedback(self, detection_frame, fourier_transform, send_roi):
        """Reconstroi a imagem com cores magnificadas (EVM)."""
        # Aplica máscara na FFT para reconstrução (apenas frequências cardíacas)
        fourier_transform[self.mask == False] = 0
        
        filtered = np.real(np.fft.ifft(fourier_transform, axis=0))
        filtered = filtered * self.alpha
        
        filtered_frame = self._reconstruct_frame(filtered, self.buffer_index, self.levels)
        filtered_val = np.mean(filtered_frame) # Valor para gráfico de pulso

        roi_output_b64 = None
        if send_roi:
            output_frame = detection_frame + filtered_frame
            output_frame = cv2.convertScaleAbs(output_frame)
            _, buffer_img = cv2.imencode('.jpg', output_frame)
            roi_output_b64 = base64.b64encode(buffer_img).decode('utf-8')
            
        return filtered_val, roi_output_b64

    # Começo

    def process_frame(self, image_bytes, is_locked=False, send_roi=False):
        """Método público chamado pelo app.py"""
        frame = self._decode_frame(image_bytes)
        if frame is None: return None

        if not is_locked:
            return self._handle_unlocked_state(frame)
        else:
            return self._handle_locked_state(frame, send_roi)