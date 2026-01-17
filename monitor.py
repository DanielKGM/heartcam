import numpy as np
import cv2
import os
import sys
import base64

class HeartRateMonitor:
    def __init__(self):
        # --- Configurações de Detecção Facial ---
        cascade_filename = "haarcascade_frontalface_alt.xml"
        cascade_path = cascade_filename if os.path.exists(cascade_filename) else \
                       os.path.join(cv2.data.haarcascades, cascade_filename)
            
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        self.face_rect = [0, 0, 0, 0]
        self.last_center = np.array([0, 0])
        self.face_detected = False

        self.frame_counter = 0
        self.detection_frequency = 10 # Roda detecção de rosto a cada 10 frames

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
        self.fps = 10 

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

    def shift(self, detected):
        x, y, w, h = detected
        center = np.array([x + 0.5 * w, y + 0.5 * h])
        shift = np.linalg.norm(center - self.last_center)
        self.last_center = center
        return shift

    def get_subface_coord(self, fh_x, fh_y, fh_w, fh_h):
        x, y, w, h = self.face_rect
        return [int(x + w * fh_x - (w * fh_w / 2.0)),
                int(y + h * fh_y - (h * fh_h / 2.0)),
                int(w * fh_w),
                int(h * fh_h)]

    def process_frame(self, image_bytes):
            if not image_bytes: return None

            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None: return None

            realHeight, realWidth, _ = frame.shape
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detecção Facial
            detected = list(self.face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=4, minSize=(40, 40), flags=cv2.CASCADE_SCALE_IMAGE))

            if len(detected) > 0:
                detected.sort(key=lambda a: a[-1] * a[-2])
                current_face = detected[-1]
                if self.shift(current_face) > 10 or not self.face_detected:
                    self.face_rect = current_face
                self.face_detected = True
            else:
                pass 

            roi_coords = None
            roi_output_b64 = None # Mudamos o nome para refletir que é a imagem processada
            raw_val = 0
            filtered_val = 0

            if self.face_detected:
                fx, fy, fw, fh = self.get_subface_coord(0.5, 0.18, 0.25, 0.15)
                
                if fy >= 0 and fy+fh < realHeight and fx >= 0 and fx+fw < realWidth:
                    roi_coords = [int(fx), int(fy), int(fw), int(fh)]
                    roi = frame[fy:fy+fh, fx:fx+fw]
                    
                    # 1. Raw Signal
                    raw_val = np.mean(roi[:, :, 1]) 

                    try:
                        detectionFrame = cv2.resize(roi, (self.procWidth, self.procHeight))
                        
                        # Processamento FFT (Construção da Pirâmide)
                        pyramid = self.buildGauss(detectionFrame, self.levels + 1)
                        currentLevel = pyramid[self.levels]
                        
                        self.videoGauss[self.bufferIndex] = currentLevel
                        fourierTransform = np.fft.fft(self.videoGauss, axis=0)
                        fourierTransform[self.mask == False] = 0

                        # Cálculo BPM
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

                        # 2. Magnificação (O "Psicodélico")
                        filtered = np.real(np.fft.ifft(fourierTransform, axis=0))
                        filtered = filtered * self.alpha
                        
                        # Frame reconstruído (apenas o sinal de pulso)
                        filteredFrame = self.reconstructFrame(filtered, self.bufferIndex, self.levels)
                        
                        # --- A MÁGICA ACONTECE AQUI ---
                        # Somamos o sinal amplificado ao frame original da ROI para visualizar o pulso
                        outputFrame = detectionFrame + filteredFrame
                        
                        # Normaliza para garantir que está entre 0-255 (Visualização correta)
                        outputFrame = cv2.convertScaleAbs(outputFrame)
                        
                        # Converte essa imagem "pulsante" para enviar ao front
                        _, buffer_img = cv2.imencode('.jpg', outputFrame)
                        roi_output_b64 = base64.b64encode(buffer_img).decode('utf-8')
                        # ------------------------------

                        filtered_val = np.mean(filteredFrame)

                        self.bufferIndex = (self.bufferIndex + 1) % self.bufferSize
                    except Exception as e:
                        # Se der erro no processamento (buffer vazio, etc), envia o ROI normal
                        print(f"Erro processamento: {e}")
                        _, buffer_backup = cv2.imencode('.jpg', roi)
                        roi_output_b64 = base64.b64encode(buffer_backup).decode('utf-8')
                        pass

            return {
                'bpm': round(self.current_bpm, 1),
                'face_detected': self.face_detected,
                'roi_rect': roi_coords,
                'roi_image': roi_output_b64, # Agora contém a imagem colorida e pulsante
                'raw_val': float(raw_val),
                'filtered_val': float(filtered_val), 
                'chart_data': {
                    'x': self.freq_axis,
                    'y': self.psd_data
                }
            }