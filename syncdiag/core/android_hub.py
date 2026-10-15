# syncdiag/core/android_hub.py
"""
Núcleo de Intercâmbio de Dados Windows <-> Android via Flask & Tailscale.
Servidor WSGI com upload/download assíncrono, suporte a PWA (App Android) e sem engasgos.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# INJEÇÃO AUTOMÁTICA DE VENV (Garante Flask mesmo no Python Global)
# ═══════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENV_SITE_PACKAGES = PROJECT_ROOT / "venv" / "Lib" / "site-packages"

if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

# Agora os imports de terceiros funcionam 100%
import logging
import socket
import subprocess
from datetime import datetime
from typing import Optional

from flask import Flask, jsonify, redirect, render_template_string, request, send_from_directory
from werkzeug.utils import secure_filename

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANDROID_BASE_DIR = Path(r"C:\SysUtils_Shared\Android")
INBOX_DIR = ANDROID_BASE_DIR / "Inbox"
OUTBOX_DIR = ANDROID_BASE_DIR / "Outbox"

# Garante a existência das pastas físicas
INBOX_DIR.mkdir(parents=True, exist_ok=True)
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

# Inicializa aplicação Flask leve
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # Suporta arquivos de até 4 GB

# Silencia logs excessivos no terminal
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


def get_tailscale_ip() -> Optional[str]:
    """Descobre o IP Tailscale (100.x.y.z) local."""
    try:
        proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            ip = proc.stdout.strip().splitlines()[0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass

    return None


def format_file_size(bytes_size: int) -> str:
    """Converte bytes para formato legível."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


# ═══════════════════════════════════════════════════════════════
# TEMPLATE HTML COM SUPORTE A APP ANDROID (PWA FULLSCREEN)
# ═══════════════════════════════════════════════════════════════
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0f172a">
<link rel="manifest" href="/manifest.json">
<title>SysUtils Android</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; --green: #22c55e; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; }
  .container { max-width: 500px; margin: 0 auto; }
  .header { text-align: center; margin-bottom: 20px; }
  .header h1 { font-size: 1.4rem; margin: 0 0 4px 0; color: var(--accent); }
  .header p { font-size: 0.85rem; color: var(--muted); margin: 0; }
  .card { background: var(--card); border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
  .card h2 { font-size: 1.1rem; margin-top: 0; margin-bottom: 12px; border-bottom: 1px solid #334155; padding-bottom: 8px; }
  .upload-box { border: 2px dashed #475569; border-radius: 8px; padding: 20px; text-align: center; }
  .file-input { width: 100%; margin-bottom: 12px; font-size: 0.9rem; color: var(--muted); }
  .btn-upload { background: var(--accent); color: #000; font-weight: bold; border: none; border-radius: 8px; padding: 12px 20px; width: 100%; font-size: 1rem; cursor: pointer; }
  .file-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #334155; font-size: 0.9rem; }
  .file-item.received { color: var(--green); }
  .btn-dl { background: #334155; color: var(--accent); text-decoration: none; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; }
  .empty-msg { color: var(--muted); font-size: 0.85rem; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📱 SysUtils Android Hub</h1>
    <p>Conexão Direta via Tailscale</p>
  </div>
  
  <div class="card">
    <h2>📤 Enviar Arquivo para o PC</h2>
    <form class="upload-box" method="POST" enctype="multipart/form-data" action="/upload">
      <input class="file-input" type="file" name="files" multiple required>
      <button class="btn-upload" type="submit">Enviar para o Computador</button>
    </form>
  </div>

  <div class="card">
    <h2>📥 Baixar do PC (Outbox)</h2>
    {% if outbox_files %}
      {% for f in outbox_files %}
        <div class="file-item">
          <div><strong>{{ f.name }}</strong><br><small>{{ f.size }} • {{ f.time }}</small></div>
          <a class="btn-dl" href="/download/{{ f.name }}">Baixar</a>
        </div>
      {% endfor %}
    {% else %}
      <p class="empty-msg">Nenhum arquivo no Outbox do PC.</p>
    {% endif %}
  </div>

  <div class="card">
    <h2>✔ Recebidos Recentemente (Inbox)</h2>
    {% if inbox_files %}
      {% for f in inbox_files %}
        <div class="file-item received">
          <div>✔ {{ f.name }}</div>
          <small>{{ f.size }}</small>
        </div>
      {% endfor %}
    {% else %}
      <p class="empty-msg">Nenhum arquivo recebido ainda.</p>
    {% endif %}
  </div>
</div>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════
# ROTAS ESSENCIAIS FLASK
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    outbox_files = []
    if OUTBOX_DIR.exists():
        for f in sorted(OUTBOX_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                stat = f.stat()
                outbox_files.append({
                    "name": f.name,
                    "size": format_file_size(stat.st_size),
                    "time": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m %H:%M")
                })

    inbox_files = []
    if INBOX_DIR.exists():
        for f in sorted(INBOX_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            if f.is_file():
                inbox_files.append({
                    "name": f.name,
                    "size": format_file_size(f.stat().st_size)
                })

    return render_template_string(HTML_TEMPLATE, outbox_files=outbox_files, inbox_files=inbox_files)


@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_files = request.files.getlist("files")
    for file in uploaded_files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            if not filename:
                filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
            file.save(os.path.join(INBOX_DIR, filename))
            print(f"  ✔ [RECEBIDO DO CELULAR] {filename}")
    return redirect("/")


@app.route("/download/<path:filename>")
def download_file(filename):
    clean_name = os.path.basename(filename)
    return send_from_directory(OUTBOX_DIR, clean_name, as_attachment=True)


@app.route("/manifest.json")
def pwa_manifest():
    """Manifest PWA: Permite instalar o site como App nativo no celular."""
    return jsonify({
        "name": "SysUtils Hub",
        "short_name": "SysUtils",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📱</text></svg>",
                "sizes": "192x192",
                "type": "image/svg+xml"
            }
        ]
    })


def run_micro_hub(requested_port: int = 8080) -> None:
    """Executa o servidor WSGI com Flask escutando em todas as interfaces."""
    tailscale_ip = get_tailscale_ip() or "127.0.0.1"

    print(f"\n[*] Servidor Flask Android Hub ativo!")
    print(f"  • Via Tailscale : http://{tailscale_ip}:{requested_port}/")
    print(f"  • Via Wi-Fi     : http://192.168.18.52:{requested_port}/")
    print(f"  • Pasta Upload  : {INBOX_DIR}")
    print(f"  • Pasta Download: {OUTBOX_DIR}\n")
    print(f"👉 Abra no celular:\n\033[1;36mhttp://{tailscale_ip}:{requested_port}/\033[0m\n")

    app.run(host="0.0.0.0", port=requested_port, debug=False, threaded=True)
