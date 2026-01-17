import numpy as np
import cv2
import os
import base64

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
        self.detection_frequency = 5 # Detecta a cada 5 frames (quando destravado)

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
        self.fps = 15 

        # Buffers
        self.videoGauss = np.zeros((self.bufferSize, self.procHeight//(2**self.levels), self.procWidth//(2**self.levels), self.videoChannels))
        self.fourierTransformAvg = np.zeros((self.bufferSize))
        
        self.frequencies = (1.0 * self.fps) * np.arange(self.bufferSize) / (1.0 * self.bufferSize)
        self.mask = (self.frequencies >= self.minFrequency) & (self.frequencies <= self.maxFrequency)

        self.bpmCalculationFrequency = 10
        self.bpmBufferIndex = 0
        self.bpmBufferSize = 10
        self.bpmBuffer = np.zeros((self.bpmBufferSize))
        self.current_bpm = 0

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

    def process_frame(self, image_bytes, is_locked=False, send_roi=False):
        if not image_bytes: return None

        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None: return None

        realHeight, realWidth, _ = frame.shape
        
        # ==========================================================
        # ESTADO 1: DESTRAVADO (BUSCA E RASTREIO)
        # ==========================================================
        if not is_locked:
            # Zera buffers para não misturar dados antigos
            self.bufferIndex = 0
            self.current_bpm = 0
            
            # Executa detecção periodicamente
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
            
            # Calcula apenas a coordenada visual da testa para desenhar o quadrado
            roi_coords = None
            if self.face_detected:
                fx, fy, fw, fh = self.get_subface_coord(0.5, 0.18, 0.25, 0.15)
                roi_coords = [int(fx), int(fy), int(fw), int(fh)]

            return {
                'bpm': "--",
                'face_detected': self.face_detected,
                'roi_rect': roi_coords,
                'roi_image': None, # Não envia imagem processada
                'raw_val': 0,
                'filtered_val': 0,
                'is_locked': False
            }

        # ==========================================================
        # ESTADO 2: TRAVADO (CÁLCULO PESADO)
        # ==========================================================
        # Aqui assumimos que self.face_rect já está posicionado e não mudamos ele
        
        roi_coords = None
        roi_output_b64 = None
        raw_val = 0
        filtered_val = 0

        fx, fy, fw, fh = self.get_subface_coord(0.5, 0.18, 0.25, 0.15)
        
        # Verifica se o quadrado ainda está dentro da tela
        if fy >= 0 and fy+fh < realHeight and fx >= 0 and fx+fw < realWidth:
            roi_coords = [int(fx), int(fy), int(fw), int(fh)]
            roi = frame[fy:fy+fh, fx:fx+fw]
            raw_val = np.mean(roi[:, :, 1])

            try:
                # Resize e Pirâmide
                detectionFrame = cv2.resize(roi, (self.procWidth, self.procHeight))
                pyramid = self.buildGauss(detectionFrame, self.levels + 1)
                currentLevel = pyramid[self.levels]
                
                self.videoGauss[self.bufferIndex] = currentLevel
                fourierTransform = np.fft.fft(self.videoGauss, axis=0)
                fourierTransform[self.mask == False] = 0

                # Cálculo do BPM
                if self.bufferIndex % self.bpmCalculationFrequency == 0:
                    for buf in range(self.bufferSize):
                        self.fourierTransformAvg[buf] = np.real(fourierTransform[buf]).mean()
                    hz = self.frequencies[np.argmax(self.fourierTransformAvg)]
                    bpm = 60.0 * hz
                    self.bpmBuffer[self.bpmBufferIndex] = bpm
                    self.bpmBufferIndex = (self.bpmBufferIndex + 1) % self.bpmBufferSize
                    self.current_bpm = self.bpmBuffer.mean()
                    
                    valid_idx = np.where((self.frequencies >= self.minFrequency) & (self.frequencies <= self.maxFrequency))
                    self.psd_data = self.fourierTransformAvg[valid_idx].tolist()
                    self.freq_axis = (self.frequencies[valid_idx] * 60.0).tolist()

                # Reconstrução (Pulse)
                filtered = np.real(np.fft.ifft(fourierTransform, axis=0))
                filtered = filtered * self.alpha
                filteredFrame = self.reconstructFrame(filtered, self.bufferIndex, self.levels)
                filtered_val = np.mean(filteredFrame)

                # Geração de Imagem (APENAS SE SOLICITADO)
                if send_roi:
                    outputFrame = detectionFrame + filteredFrame
                    outputFrame = cv2.convertScaleAbs(outputFrame)
                    _, buffer_img = cv2.imencode('.jpg', outputFrame)
                    roi_output_b64 = base64.b64encode(buffer_img).decode('utf-8')

                self.bufferIndex = (self.bufferIndex + 1) % self.bufferSize
                
            except Exception:
                pass

        return {
            'bpm': round(self.current_bpm, 1) if self.current_bpm > 0 else "--",
            'face_detected': True,
            'roi_rect': roi_coords,
            'roi_image': roi_output_b64,
            'raw_val': float(raw_val),
            'filtered_val': float(filtered_val),
            'is_locked': True,
            'chart_data': {'x': self.freq_axis, 'y': self.psd_data}
        }