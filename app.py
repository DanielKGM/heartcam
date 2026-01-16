from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request # <--- ADICIONADO 'request'
from flask_socketio import SocketIO, emit, disconnect
from monitor import HeartRateMonitor
import sys
import os

# Garante que o print saia corretamente no terminal do Windows
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
# cors_allowed_origins="*" é vital para produção e evita erros de conexão cruzada
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")

# Dicionário para armazenar o monitor de cada cliente
client_monitors = {}

@app.route('/')
def index():
    return render_template('index.html')

# --- CORREÇÃO AQUI: auth=None aceita o argumento extra que o SocketIO envia ---
@socketio.on('connect')
def handle_connect(auth=None):
    # O request.sid existe dentro do contexto do socket
    sid = request.sid
    print(f"Cliente conectado: {sid}")
    
    # Cria uma nova instância isolada para este usuário
    client_monitors[sid] = HeartRateMonitor()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f"Cliente desconectado: {sid}")
    
    # Limpa a memória removendo o monitor do usuário
    if sid in client_monitors:
        del client_monitors[sid]

@socketio.on('process_frame')
def handle_process_frame(data):
    """
    Recebe o frame binário do frontend, processa e devolve o BPM.
    """
    sid = request.sid
    image_data = data.get('image') 
    
    # Verifica se o usuário tem um monitor ativo
    if sid in client_monitors and image_data:
        monitor = client_monitors[sid]
        
        # O monitor processa e retorna o dict com BPM e Gráfico
        result = monitor.process_frame(image_data)
        
        if result:
            # Devolve os dados apenas para este cliente
            emit('data_update', result)

if __name__ == '__main__':
    # Pega a porta do ambiente (Koyeb) ou usa 5000 se for local
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor iniciado na porta {port}. Aguardando conexões...")
    socketio.run(app, host='0.0.0.0', port=port)