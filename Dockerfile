# Usa imagem Python leve
FROM python:3.9-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala libs do sistema para OpenCV (necessário mesmo com headless as vezes)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Expõe a porta 8000 (Padrão sugerido para Gunicorn)
EXPOSE 8000

# --- COMANDO DE INICIALIZAÇÃO ATUALIZADO ---
# -k: Define o tipo de worker (Crucial para SocketIO funcionar)
# -w 1: Apenas 1 worker. (Explicação abaixo*)
# -b: Bind na porta 8000
# app:app : Arquivo app.py : Variável app
CMD ["gunicorn", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "-w", "1", "--bind", "0.0.0.0:8000", "app:app"]