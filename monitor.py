import numpy as np
import cv2
import os
import base64
import time

class HeartRateMonitor:
    def __init__(self):
        # --- Configurações Iniciais ---
        cascade_filename = "haarcascade_frontalface_alt.xml"
        cascade_path = cascade_filename if os.path.exists(cascade_filename) else \
                       os.path.join(cv2.data.haarcascades, cascade_filename)
            
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.face_rect = [0, 0, 0, 0]
        self.face_detected = False

        self.frame_counter = 0
        self.detection_frequency = 5 

        # --- Parâmetros de Processamento ---
        self.levels = 3
        self.alpha = 170
        self.minFrequency = 1.0  # 60 BPM
        self.maxFrequency = 2.0  # 120 BPM
        self.bufferSize = 150
        self.bufferIndex = 0
        
        self.procWidth = 160
        self.procHeight = 120
        self.videoChannels = 3
        
        # --- MELHORIA 3: Controle de Tempo Real ---
        # Não confiamos apenas no FPS fixo, medimos o tempo real
        self.fps = 15 
        self.timestamps = [0] * self.bufferSize 

        # Buffers EVM
        self.videoGauss = np.zeros((self.bufferSize, self.procHeight//(2**self.levels), self.procWidth//(2**self.levels), self.videoChannels))
        self.fourierTransformAvg = np.zeros((self.bufferSize))
        
        # Buffer de Frequências (será recalculado dinamicamente)
        self.frequencies = np.zeros((self.bufferSize))
        self.mask = np.zeros((self.bufferSize), dtype=bool)

        self.bpmCalculationFrequency = 10
        self.current_bpm = 0
        self.smoothed_bpm = 0 # Variável para guardar o valor estável

        self.psd_data = [] 
        self.freq_axis = []

    def buildGauss(self, frame, levels):
        pyramid = [frame]
        for level in range(levels):
            frame = cv2.pyrDown(frame)
            pyramid.append(frame)
        return pyramid

    def reconstructFrame(self, pyramid, index, levels):
        filteredFrame = pyramid[index]
        for level in range(levels):
            filteredFrame = cv2.pyrUp(filteredFrame)
        filteredFrame = filteredFrame[:self.procHeight, :self.procWidth]
        return filteredFrame

    def get_subface_coord(self, fh_x, fh_y, fh_w, fh_h):
        x, y, w, h = self.face_rect
        return [int(x + w * fh_x - (w * fh_w / 2.0)),
                int(y + h * fh_y - (h * fh_h / 2.0)),
                int(w * fh_w),
                int(h * fh_h)]
    
    # --- MELHORIA 2: Função de Suavização (Do heartcam.py) ---
    def smooth_value(self, current_val, new_val, alpha=0.15):
        """
        Alpha pequeno (0.1) = Muito estável, demora a mudar.
        Alpha grande (0.9) = Muito reativo, instável.
        0.15 é um bom equilíbrio.
        """
        if current_val == 0: return new_val
        return alpha * new_val + (1 - alpha) * current_val

    def process_frame(self, image_bytes, is_locked=False, send_roi=False):
        if not image_bytes: return None

        # Validação de Segurança
        if not isinstance(image_bytes, (bytes, bytearray)):
            return None

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None: return None
        except:
            return None

        realHeight, realWidth, _ = frame.shape
        
        # --- Lógica de Tempo (Para FPS Real) ---
        current_time = time.time()
        
        # === ESTADO 1: DESTRAVADO ===
        if not is_locked:
            self.bufferIndex = 0
            self.current_bpm = 0
            self.smoothed_bpm = 0 # Reseta suavização
            
            if self.frame_counter % self.detection_frequency == 0 or not self.face_detected:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detected = list(self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.3, minNeighbors=4, minSize=(40, 40), flags=cv2.CASCADE_SCALE_IMAGE
                ))
                
                if len(detected) > 0:
                    detected.sort(key=lambda a: a[-1] * a[-2])
                    self.face_rect = detected[-1]
                    self.face_detected = True
            
            self.frame_counter = (self.frame_counter + 1) % 100
            
            roi_coords = None
            if self.face_detected:
                fx, fy, fw, fh = self.get_subface_coord(0.5, 0.18, 0.25, 0.15)
                roi_coords = [int(fx), int(fy), int(fw), int(fh)]

            return {
                'bpm': "--",
                'face_detected': self.face_detected,
                'roi_rect': roi_coords,
                'roi_image': None,
                'raw_val': 0,
                'filtered_val': 0,
                'is_locked': False
            }

        # === ESTADO 2: TRAVADO ===
        
        roi_coords = None
        roi_output_b64 = None
        raw_val = 0
        filtered_val = 0

        fx, fy, fw, fh = self.get_subface_coord(0.5, 0.18, 0.25, 0.15)
        
        if fy >= 0 and fy+fh < realHeight and fx >= 0 and fx+fw < realWidth:
            roi_coords = [int(fx), int(fy), int(fw), int(fh)]
            roi = frame[fy:fy+fh, fx:fx+fw]
            raw_val = np.mean(roi[:, :, 1]) # Canal Verde

            try:
                detectionFrame = cv2.resize(roi, (self.procWidth, self.procHeight))
                
                # Armazena timestamp atual para cálculo de FPS real
                self.timestamps[self.bufferIndex] = current_time

                # EVM: Pirâmide Gaussiana
                pyramid = self.buildGauss(detectionFrame, self.levels + 1)
                currentLevel = pyramid[self.levels]
                self.videoGauss[self.bufferIndex] = currentLevel
                
                # FFT
                fourierTransform = np.fft.fft(self.videoGauss, axis=0)

                # --- CÁLCULO DE BPM MELHORADO ---
                if self.bufferIndex % self.bpmCalculationFrequency == 0:
                    
                    # 1. Calcula FPS real baseado no tempo que levou para encher o buffer
                    # (Pega o tempo do último frame - tempo do primeiro frame do buffer)
                    # Se o buffer ainda não deu a volta, usamos fps padrão
                    t_start = self.timestamps[(self.bufferIndex + 1) % self.bufferSize]
                    t_end = current_time
                    if t_end > t_start:
                        self.fps = self.bufferSize / (t_end - t_start)
                    
                    # Atualiza eixo de frequências com FPS real
                    self.frequencies = (1.0 * self.fps) * np.arange(self.bufferSize) / (1.0 * self.bufferSize)
                    self.mask = (self.frequencies >= self.minFrequency) & (self.frequencies <= self.maxFrequency)
                    
                    # Aplica máscara na FFT
                    fourierTransform[self.mask == False] = 0

                    # Média espacial da FFT (transforma 3D em 1D)
                    for buf in range(self.bufferSize):
                        self.fourierTransformAvg[buf] = np.real(fourierTransform[buf]).mean()
                    
                    # --- MELHORIA 1: Weighted Average (Média Ponderada) ---
                    # Em vez de pegar só o pico, pegamos os vizinhos
                    idx = np.argmax(self.fourierTransformAvg)
                    
                    # Só calcula se o índice for válido e tiver vizinhos
                    if idx > 0 and idx < self.bufferSize - 1:
                        mag_prev = self.fourierTransformAvg[idx-1]
                        mag_curr = self.fourierTransformAvg[idx]
                        mag_next = self.fourierTransformAvg[idx+1]
                        
                        # Fórmula da Média Ponderada
                        # (freq_prev * mag_prev + freq_curr * mag_curr + ...) / soma_mags
                        weighted_freq = (self.frequencies[idx-1] * mag_prev + 
                                         self.frequencies[idx] * mag_curr + 
                                         self.frequencies[idx+1] * mag_next) / (mag_prev + mag_curr + mag_next)
                        
                        instant_bpm = 60.0 * weighted_freq
                    else:
                        # Fallback se estiver na borda
                        instant_bpm = 60.0 * self.frequencies[idx]

                    # Aplica a Suavização (Smooth)
                    if self.smoothed_bpm == 0:
                        self.smoothed_bpm = instant_bpm
                    else:
                        self.smoothed_bpm = self.smooth_value(self.smoothed_bpm, instant_bpm)
                    
                    self.current_bpm = self.smoothed_bpm
                    
                    # Dados para o gráfico
                    valid_idx = np.where(self.mask)
                    self.psd_data = self.fourierTransformAvg[valid_idx].tolist()
                    self.freq_axis = (self.frequencies[valid_idx] * 60.0).tolist()

                # Reconstrução da Imagem (Magnificação)
                filtered = np.real(np.fft.ifft(fourierTransform, axis=0))
                filtered = filtered * self.alpha
                filteredFrame = self.reconstructFrame(filtered, self.bufferIndex, self.levels)
                filtered_val = np.mean(filteredFrame)

                if send_roi:
                    outputFrame = detectionFrame + filteredFrame
                    outputFrame = cv2.convertScaleAbs(outputFrame)
                    _, buffer_img = cv2.imencode('.jpg', outputFrame)
                    roi_output_b64 = base64.b64encode(buffer_img).decode('utf-8')

                self.bufferIndex = (self.bufferIndex + 1) % self.bufferSize
                
            except Exception:
                pass

        return {
            'bpm': round(self.current_bpm, 1) if self.current_bpm > 0 else "--", # Filtro visual simples
            'face_detected': True,
            'roi_rect': roi_coords,
            'roi_image': roi_output_b64,
            'raw_val': float(raw_val),
            'filtered_val': float(filtered_val),
            'is_locked': True,
            'chart_data': {'x': self.freq_axis, 'y': self.psd_data}
        }