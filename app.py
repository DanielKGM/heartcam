from gevent import monkey

monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from monitor import HeartRateMonitor
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)

socketio = SocketIO(
    app,
    async_mode="gevent",
    cors_allowed_origins="*",
    max_http_buffer_size=1e8,
    ping_timeout=60,
    ping_interval=25,
)

client_monitors = {}


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect(auth=None):
    sid = request.sid
    client_monitors[sid] = HeartRateMonitor()


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in client_monitors:
        del client_monitors[sid]


@socketio.on("process_frame")
def handle_process_frame(data):
    sid = request.sid
    image_data = data.get("image")

    # NOVOS PARÂMETROS
    is_locked = data.get("is_locked", False)
    # send_roi foi removido pois não usamos mais

    if sid in client_monitors and image_data:
        monitor = client_monitors[sid]

        # Passa as flags para o monitor
        result = monitor.process_frame(image_data, is_locked)

        if result:
            emit("data_update", result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor iniciado na porta {port}")
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
    )
