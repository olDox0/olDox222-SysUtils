# docs/blitzplans/input_leap_integration.md

---

# PLANO 1 - concepção

---

### [DOX-NEXUS: PRODENOV ANALYSIS & BLUEPRINT]
**Projeto:** `Projeto SysUtils` (CLI: `sysutils`)  
**Contexto Técnico:** Windows 10/11, Python 3.10+, arquitetura híbrida (Click CLI + C / Win32 / Robocopy / PowerShell). Ambientes modestos com foco em baixa latência, baixo consumo de RAM e estabilidade de rede local/Tailscale.  
**Conformidade:** `ProDeNov` (Protocolo de Desenvolvimento Novíssimo — seções 0 a 5).

---

## 1. Avaliação de Complexidade (ProDeNov 0.x) & Escolha do Motor

Você sugeriu o **Input Leap** (fork ativo e mantido do Barrier/Synergy). Vamos analisar friamente antes de bater o martelo técnico:

### Análise de Candidatos:

1. **Input Leap (`input-leap/input-leap`):**
   * **Natureza:** C/C++ nativo. Binários de serviço de fundo: `input-leaps.exe` (servidor/host que tem o teclado/mouse físico) e `input-leapc.exe` (cliente que recebe as entradas).
   * **Vantagens:** Madura, suporte a criptografia TLS nativa, clipboard compartilhado (inclusive texto/arquivos pequenos), consumo mínimo de RAM (~10-25 MB), suporte a múltiplas telas/layouts e hotkeys.
   * **Desvantagens:** Binários pré-compilados precisam ser distribuídos ou baixados; a GUI oficial é pesada (Qt), mas **a CLI dos daemons (`input-leaps` e `input-leapc`) é totalmente desacoplada e aceita arquivo de configuração plano `.conf`**.

2. **Barrier (`debauchee/barrier`):**
   * Ancestral do Input Leap. O projeto está estagnado/abandonado em favor do Input Leap. Não recomendado para projetos novos.

3. **Soluções puras em Python (`pynput` + sockets UDP/TCP):**
   * **Risco (Rabbit Hole & Sensibilidade - ProDeNov 0.2/0.3):** Desenvolver um multiplexador de mouse em Python gera jitter no cursor, overhead alto de CPU no loop de polling do Windows Hook (`WH_MOUSE_LL`), e exige lidar manualmente com layout de teclado, UAC elevation e firewall.
   * **Veredito:** Viola o ProDeNov 3.1.1 (*"se existe uma lib/ferramenta consolidada que já cumpre a tarefa, use-a; delegue funções ao que já existe"*).

4. **Mouse Without Borders (PowerToys):**
   * Muito acoplado ao ecossistema .NET / Windows exclusivo, sem CLI programável limpa.

### Decisão Técnica:
Adotar a **estratégia do `syncdiag`** (que usamos com sucesso via wrapper inteligente de Robocopy/SMB):
O **`SysUtils` será o orquestrador (Zeus)** de um novo submódulo: **`leapdiag`** (ou `switchdiag` / `kvmdiag`), integrando os executáveis portáteis headless do **Input Leap** (`input-leaps.exe` e `input-leapc.exe`). O Python cuidará da geração de topologia de telas, arquivos de configuração, inicialização resiliente, gestão de firewall e telemetria.

---

## 2. Planejamento & Roteiro (ProDeNov 1.x & 5.6)

### Plano A vs. Plano B (ProDeNov 1.2.1)
* **Plano A (Recomendado):** Modo Orquestrado Input Leap Headless.
  * O SysUtils baixa/detecta os binários headless do Input Leap (`bin/input-leaps.exe` e `bin/input-leapc.exe`).
  * O Python gera o arquivo `input-leap.conf` declarando a posição relativa dos monitores (ex: `PC-Direita fica à direita do PC-Esquerda`).
  * Inicia como subprocesso monitorado ou serviço com reconexão automática.
* **Plano B (Fallback Emergencial Local):** Bridge Python/Win32 via Socket.
  * Se os binários do Input Leap não estiverem presentes e o download falhar, o SysUtils aciona um modo leve de transferência de clipboard e clique via `ctypes` (Win32 `SendInput`), servindo de contingência imediata.

---

## 3. Topologia & Placeholders do Submódulo `leapdiag` (ProDeNov 2.x)

Seguindo a estrutura modular do seu repositório (`diskdiag`, `ramdiag`, `syncdiag`):

```text
sysutils/
├── leapdiag/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py         # Zeus: CLI click (server, client, pair, status, stop)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config_gen.py       # Dionísio/Hera: Gera input-leap.conf a partir de topologia
│   │   ├── daemon.py           # Poseidon: Gerencia processos em background (leaps/leapc)
│   │   ├── discovery.py        # Anúbis: Detecta PCs e testa handshake na porta 24800
│   │   └── installer.py        # Hefesto: Verifica/obtém os binários portáteis headless
│   └── platform/
│       └── windows/
│           ├── __init__.py
│           └── firewall.py     # Regras de liberação de porta via netsh / PowerShell
```

---

## 4. Esboço Prático da Arquitetura & Implementação

### 4.1. Gerador do Contrato de Configuração (`leapdiag/core/config_gen.py`)
O Input Leap precisa de um arquivo de configuração simples no Host/Servidor. Exemplo:

```python
# leapdiag/core/config_gen.py
"""
Gerador de arquivo de configuração do Input Leap Server (.conf).
Define as telas físicas e a regra de transição de bordas.
"""
from pathlib import Path

def generate_server_config(
    server_name: str,
    client_name: str,
    client_position: str = "right"  # "left", "right", "above", "below"
) -> str:
    """
    Gera a sintaxe textual esperada pelo input-leaps.exe.
    """
    opposites = {
        "right": ("right", "left"),
        "left": ("left", "right"),
        "above": ("up", "down"),
        "below": ("down", "up")
    }
    dir_to, dir_from = opposites.get(client_position, ("right", "left"))

    conf = f"""section: screens
    {server_name}:
    {client_name}:
end

section: links
    {server_name}:
        {dir_to} = {client_name}
    {client_name}:
        {dir_from} = {server_name}
end

section: options
    relativeMouseMoves = false
    screenSaverSync = true
    win32KeepForeground = false
    clipboardSharing = true
end
"""
    return conf
```

### 4.2. Gestor de Daemons em Background (`leapdiag/core/daemon.py`)
Controla o ciclo de vida sem travamento de terminal, em conformidade com as regras de I/O assíncrono:

```python
# leapdiag/core/daemon.py
"""
Orquestrador de execução de serviços em segundo plano para Input Leap.
"""
import subprocess
import os
import psutil
from pathlib import Path

BIN_DIR = Path("bin") / "input-leap"

def get_binaries():
    return {
        "server": BIN_DIR / "input-leaps.exe",
        "client": BIN_DIR / "input-leapc.exe"
    }

def start_server(config_path: Path, port: int = 24800) -> subprocess.Popen:
    bins = get_binaries()
    if not bins["server"].exists():
        raise FileNotFoundError(f"Binário {bins['server']} ausente. Execute 'sysutils leap setup'.")

    cmd = [
        str(bins["server"]),
        "-f",  # Foreground (gerenciado pelo subprocess)
        "--address", f":{port}",
        "-c", str(config_path),
        "--name", os.environ.get("COMPUTERNAME", "SERVER_PC")
    ]
    # Executa sem travar o shell
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

def start_client(server_ip: str, port: int = 24800) -> subprocess.Popen:
    bins = get_binaries()
    if not bins["client"].exists():
        raise FileNotFoundError(f"Binário {bins['client']} ausente. Execute 'sysutils leap setup'.")

    cmd = [
        str(bins["client"]),
        "-f",
        "--name", os.environ.get("COMPUTERNAME", "CLIENT_PC"),
        f"{server_ip}:{port}"
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

def stop_all():
    """Mata processos zumbis do input-leap."""
    killed = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in ('input-leaps.exe', 'input-leapc.exe', 'barrier.exe'):
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed
```

### 4.3. Comandos CLI Click (`leapdiag/cli/commands.py`)
Registrado em `cli/main.py` sob o alias `leap` ou `mouse`:

```python
# leapdiag/cli/commands.py
import click
import socket
from pathlib import Path
from leapdiag.core import daemon, config_gen

@click.group()
def cli():
    """LeapDiag — Compartilhamento de Mouse & Teclado entre computadores."""
    pass

@cli.command("host")
@click.option("--client", prompt="Nome do computador cliente (recebedor)", help="Hostname do outro PC.")
@click.option("--pos", type=click.Choice(["left", "right", "above", "below"]), default="right", help="Onde o cliente está fisicamente.")
@click.option("--port", default=24800, help="Porta de escuta.")
def host(client, pos, port):
    """Configura e inicia este PC como SERVIDOR (onde mouse/teclado estão plugados)."""
    hostname = socket.gethostname()
    conf_dir = Path("data") / "leap"
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf_file = conf_dir / "server.conf"

    conf_content = config_gen.generate_server_config(hostname, client, pos)
    conf_file.write_text(conf_content, encoding="utf-8")

    click.secho(f"[*] Servidor configurado: {hostname} -> [{pos.upper()}] -> {client}", fg="cyan")
    daemon.stop_all()
    daemon.start_server(conf_file, port)
    click.secho(f"[OK] Servidor Input Leap rodando em background na porta {port}.", fg="green", bold=True)
    click.echo(f"No outro PC ({client}), rode: sysutils leap join <IP_DESTE_PC>")

@cli.command("join")
@click.argument("server_ip")
@click.option("--port", default=24800, help="Porta de conexão.")
def join(server_ip, port):
    """Conecta este PC como CLIENTE (vai receber os comandos de mouse/teclado)."""
    click.secho(f"[*] Conectando ao Host {server_ip}:{port}...", fg="cyan")
    daemon.stop_all()
    daemon.start_client(server_ip, port)
    click.secho("[OK] Cliente em execução e aguardando ponteiro.", fg="green", bold=True)

@cli.command("stop")
def stop():
    """Encerra instâncias ativas do Input Leap."""
    count = daemon.stop_all()
    click.secho(f"[OK] {count} processos de entrada encerrados.", fg="yellow")
```

---

# RIT 1 - fundação

---

### Observação Crítica de Topologia
Note que o `doxoade mk` criou a raiz dentro de:
`Projeto SysUtils\sysutils\leap_sys\` (ou seja, sob a pasta `sysutils/` interna do pacote). Para que o `cli/main.py` consiga importar de qualquer lugar, garantiremos caminhos absolutos e imports resolvidos a partir de `sysutils.leap_sys` ou `leap_sys` de forma transparente.

---

## PARTE 1: Registro do Comando Zeus & CLI (`cli/main.py` e `cmd_leap.py`)

### 1.1 Atualizar `cli/main.py`
No seu arquivo `cli/main.py`, dentro de `SysUtilsLazyGroup.__init__`, adicione o roteador `'leap'`:

```python
# No cli/main.py -> self._lazy_map:
self._lazy_map = {
    'disk':   'diskdiag.cli.commands:cli',
    'ram':    'ramdiag.cli.commands:cli',
    'backup': 'doxbackup.cli.commands:cli',
    'bloat':  'bloatbreaker.cli.commands:cli',
    'win':    'sysdiag.cli.commands:cli',
    'net':    'netdiag.cli.commands:cli',
    'verify': 'doxbackup.core.verify:cli',
    'sync':   'syncdiag.cli.commands:cli',
    'leap':   'sysutils.leap_sys.cli.cmd_leap:cli',  # <- NOVO ROTEADOR ZEUS
}
```

---

### 1.2 `sysutils/leap_sys/cli/cmd_leap.py`
*(Papel: Zeus - Orquestrador de Comandos e UX do Terminal)*

```python
# sysutils/leap_sys/cli/cmd_leap.py
"""
Interface de Linha de Comando (CLI) para LeapSys / Input Leap.
Comandos:
  - setup: Baixa/valida os binários portáteis headless (leaps/leapc).
  - host:  Inicia modo Servidor (computador onde o mouse/teclado físicos estão).
  - join:  Inicia modo Cliente (computador que recebe o cursor).
  - status: Verifica processos ativos e conectividade.
  - stop:  Encerra daemons do Input Leap.
"""
from __future__ import annotations
import click
import socket
from pathlib import Path
from sysutils.leap_sys.leap_engine import (
    leap_installer,
    leap_orchestration,
    leap_daemon,
    leap_discovery
)
from sysutils.leap_sys.leap_platform.leap_windows import leap_firewall, leap_elevation

@click.group(name="leap")
def cli():
    """LeapSys — Compartilhamento de Mouse & Teclado (Input Leap Engine)."""
    pass

@cli.command("setup")
@click.option("--force", is_flag=True, help="Força novo download mesmo se os binários existirem.")
def cmd_setup(force: bool):
    """Verifica e baixa os binários headless necessários."""
    click.secho("[*] Auditando binários do Input Leap...", fg="cyan")
    ok, msg = leap_installer.ensure_binaries(force=force)
    if ok:
        click.secho(f"[OK] {msg}", fg="green", bold=True)
    else:
        click.secho(f"[ERRO] {msg}", fg="red", bold=True)
        raise click.Abort()

@cli.command("host")
@click.option("--client", default=None, help="Hostname ou apelido do computador cliente (ex: bluebaby).")
@click.option("--pos", type=click.Choice(["right", "left", "above", "below"]), default="right", show_default=True,
              help="Posição física do cliente em relação a este servidor.")
@click.option("--port", default=24800, show_default=True, help="Porta de escuta TCP.")
@click.option("--no-firewall", is_flag=True, help="Pula verificação de regra no Windows Firewall.")
def cmd_host(client: str | None, pos: str, port: int, no_firewall: bool):
    """Inicia este PC como SERVIDOR (onde mouse e teclado estão conectados fisicamente)."""
    server_host = socket.gethostname()

    # Validação dos binários
    if not leap_installer.is_installed():
        click.secho("[!] Binários não encontrados. Executando auto-setup...", fg="yellow")
        ok, msg = leap_installer.ensure_binaries()
        if not ok:
            click.secho(f"[ERRO] {msg}", fg="red")
            raise click.Abort()

    # Assistente caso client não tenha sido fornecido
    if not client:
        click.echo(f"Computador Servidor atual: {click.style(server_host, bold=True, fg='cyan')}")
        client = click.prompt("Nome do computador cliente de destino (ex: bluebaby)")

    # Firewall
    if not no_firewall:
        if not leap_firewall.is_port_open(port):
            click.secho(f"[*] Porta {port} fechada no Firewall do Windows. Solicitando liberação...", fg="yellow")
            if leap_elevation.is_admin():
                leap_firewall.open_firewall_port(port, "InputLeap_Server")
                click.secho(f"[OK] Porta {port} liberada no Firewall.", fg="green")
            else:
                click.secho("[AVISO] Rode o terminal como Administrador ou use '--no-firewall' se a porta já estiver aberta.", fg="yellow")

    click.secho(f"[*] Montando topologia: [{server_host}] ===({pos.upper()})===> [{client}]", fg="cyan")
    success, log = leap_orchestration.start_host(server_name=server_host, client_name=client, position=pos, port=port)
    if success:
        click.secho(f"\n[OK] Servidor Input Leap ativo em segundo plano na porta {port}!", fg="green", bold=True)
        click.echo(f"👉 No outro computador ({client}), execute:")
        click.secho(f"   sysutils leap join <IP_DESTE_PC> --port {port}\n", fg="yellow", bold=True)
    else:
        click.secho(f"[FALHA] {log}", fg="red")

@cli.command("join")
@click.argument("server_target", required=False)
@click.option("--port", default=24800, show_default=True, help="Porta do servidor.")
def cmd_join(server_target: str | None, port: int):
    """Conecta este PC como CLIENTE (receberá os comandos de mouse/teclado)."""
    if not leap_installer.is_installed():
        click.secho("[!] Binários não encontrados. Executando auto-setup...", fg="yellow")
        ok, msg = leap_installer.ensure_binaries()
        if not ok:
            click.secho(f"[ERRO] {msg}", fg="red")
            raise click.Abort()

    client_host = socket.gethostname()

    if not server_target:
        click.secho("[*] Escaneando rede local em busca do Servidor Input Leap...", fg="cyan")
        detected = leap_discovery.discover_server(port=port)
        if detected:
            click.secho(f"[!] Servidor localizado em: {detected}", fg="green")
            if click.confirm(f"Deseja conectar a {detected}?", default=True):
                server_target = detected
        if not server_target:
            server_target = click.prompt("Digite o IP ou Hostname do Servidor (PC Amaranth)")

    click.secho(f"[*] Conectando [{client_host}] ao servidor {server_target}:{port}...", fg="cyan")
    success, log = leap_orchestration.start_client(server_ip=server_target, client_name=client_host, port=port)
    if success:
        click.secho("[OK] Cliente Input Leap iniciado em background!", fg="green", bold=True)
        click.echo("Aguardando o cursor atravessar a borda da tela.")
    else:
        click.secho(f"[FALHA] {log}", fg="red")

@cli.command("status")
def cmd_status():
    """Verifica se os daemons do Input Leap estão rodando."""
    status = leap_daemon.get_running_status()
    click.echo("\n--- STATUS DO LEAP SYS ---")
    if status["server_running"]:
        click.secho(f"  ● Servidor: ATIVO (PID: {status['server_pids']})", fg="green", bold=True)
    else:
        click.echo("  ○ Servidor: Inativo")

    if status["client_running"]:
        click.secho(f"  ● Cliente:  ATIVO (PID: {status['client_pids']})", fg="green", bold=True)
    else:
        click.echo("  ○ Cliente:  Inativo")
    click.echo("--------------------------\n")

@cli.command("stop")
def cmd_stop():
    """Encerra todos os processos do Input Leap (Server e Client)."""
    killed = leap_daemon.stop_all()
    if killed > 0:
        click.secho(f"[OK] {killed} processo(s) do Input Leap finalizado(s).", fg="green")
    else:
        click.echo("[INFO] Nenhum processo ativo encontrado.")
```

---

## PARTE 2: Core 1 (Instalação dos Binários & Geração do Contrato .conf)

### 2.1 `sysutils/leap_sys/leap_engine/leap_installer.py`
*(Papel: Hefesto - Obtenção e verificação de integridade dos binários)*

```python
# sysutils/leap_sys/leap_engine/leap_installer.py
"""
Hefesto: Gerenciador de Instalação dos Binários Portáteis do Input Leap.
Localiza os binários em 'bin/input-leap/' ou realiza download automático
do pacote oficial (Windows x64).
"""
from __future__ import annotations
import os
import sys
import shutil
import zipfile
import urllib.request
from pathlib import Path

# Raiz do projeto SysUtils (sobe 4 níveis a partir deste arquivo)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BIN_DIR = PROJECT_ROOT / "bin" / "input-leap"

INPUT_LEAP_RELEASE_URL = (
    "https://github.com/input-leap/input-leap/releases/download/v2.4.0/InputLeap_2.4.0_win64.zip"
)

def get_binary_paths() -> dict[str, Path]:
    return {
        "server": BIN_DIR / "input-leaps.exe",
        "client": BIN_DIR / "input-leapc.exe"
    }

def is_installed() -> bool:
    bins = get_binary_paths()
    return bins["server"].exists() and bins["client"].exists()

def ensure_binaries(force: bool = False) -> tuple[bool, str]:
    """
    Garante a presença de input-leaps.exe e input-leapc.exe.
    """
    bins = get_binary_paths()
    if not force and is_installed():
        return True, f"Binários íntegros em: {BIN_DIR}"

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    zip_dest = BIN_DIR / "input-leap-temp.zip"

    try:
        print(f"[*] Baixando pacote Input Leap x64 de:\n    {INPUT_LEAP_RELEASE_URL}")
        urllib.request.urlretrieve(INPUT_LEAP_RELEASE_URL, zip_dest)

        print("[*] Extraindo executáveis headless...")
        with zipfile.ZipFile(zip_dest, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if filename in ("input-leaps.exe", "input-leapc.exe", "barrier.exe", "barrierc.exe"):
                    source = zip_ref.open(member)
                    target = open(BIN_DIR / filename, "wb")
                    with source, target:
                        shutil.copyfileobj(source, target)

        if zip_dest.exists():
            zip_dest.unlink()

        if is_installed():
            return True, "Binários instalados com sucesso em bin/input-leap/"
        else:
            return False, "Download concluído, mas os binários input-leaps.exe / input-leapc.exe não foram encontrados no zip."

    except Exception as e:
        if zip_dest.exists():
            try: zip_dest.unlink()
            except Exception: pass
        return False, f"Falha no download/extração: {e}"
```

---

### 2.2 `sysutils/leap_sys/leap_engine/leap_config.py`
*(Papel: Dionísio/Hera - Modelagem e geração do contrato sintático do arquivo de configuração)*

```python
# sysutils/leap_sys/leap_engine/leap_config.py
"""
Hera: Gerador de configuração declarativa para o input-leaps.exe.
Suporta topologia de telas: right, left, above (up), below (down).
"""
from __future__ import annotations
from pathlib import Path

def generate_conf_content(
    server_name: str,
    client_name: str,
    position: str = "right"
) -> str:
    """
    Gera o texto de configuração com links bidirecionais entre Server e Client.
    """
    # Mapeamento bidirecional da transição de bordas
    dir_map = {
        "right": ("right", "left"),
        "left":  ("left", "right"),
        "above": ("up", "down"),
        "below": ("down", "up")
    }
    dir_server_to_client, dir_client_to_server = dir_map.get(position, ("right", "left"))

    conf = f"""# ==============================================================================
# LEAP SYS CONFIGURATION FILE (Gerado automaticamente pelo SysUtils)
# ==============================================================================

section: screens
\t{server_name}:
\t\thalfDuplexCapsLock = false
\t\thalfDuplexNumLock = false
\t\thalfDuplexScrollLock = false
\t\txtestIsXineramaUnaware = false
\t\tswitchCorners = none
\t\tswitchCornerSize = 0
\t{client_name}:
\t\thalfDuplexCapsLock = false
\t\thalfDuplexNumLock = false
\t\thalfDuplexScrollLock = false
\t\txtestIsXineramaUnaware = false
\t\tswitchCorners = none
\t\tswitchCornerSize = 0
end

section: links
\t{server_name}:
\t\t{dir_server_to_client} = {client_name}
\t{client_name}:
\t\t{dir_client_to_server} = {server_name}
end

section: options
\theartbeat = 5000
\trelativeMouseMoves = false
\tscreenSaverSync = true
\twin32KeepForeground = false
\tclipboardSharing = true
\tswitchDelay = 250
end
"""
    return conf

def write_runtime_config(
    conf_dir: Path,
    server_name: str,
    client_name: str,
    position: str = "right"
) -> Path:
    conf_dir.mkdir(parents=True, exist_ok=True)
    target_path = conf_dir / "leap_runtime.conf"
    content = generate_conf_content(server_name, client_name, position)
    target_path.write_text(content, encoding="utf-8")
    return target_path
```

---

## PARTE 3: Core 2 (Gestão de Processos, Descoberta de Rede & Orquestração)

### 3.1 `sysutils/leap_sys/leap_engine/leap_daemon.py`
*(Papel: Poseidon - Manipulação de I/O de processos e streams em background)*

```python
# sysutils/leap_sys/leap_engine/leap_daemon.py
"""
Poseidon: Gestor de Processos em Background para Daemons do Input Leap.
Usa subprocess desanexado para não travar o terminal CLI do usuário.
"""
from __future__ import annotations
import subprocess
import os
import psutil
from pathlib import Path
from sysutils.leap_sys.leap_engine.leap_installer import get_binary_paths

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def get_running_status() -> dict:
    """Verifica PIDs ativos de input-leaps e input-leapc."""
    server_pids = []
    client_pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = (proc.info['name'] or '').lower()
            if name == 'input-leaps.exe':
                server_pids.append(proc.info['pid'])
            elif name == 'input-leapc.exe':
                client_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "server_running": len(server_pids) > 0,
        "server_pids": server_pids,
        "client_running": len(client_pids) > 0,
        "client_pids": client_pids,
    }

def spawn_server(conf_path: Path, port: int, server_name: str, log_file: Path) -> subprocess.Popen:
    bins = get_binary_paths()
    cmd = [
        str(bins["server"]),
        "-f",                           # Foreground (gerenciado pelo subprocess)
        "--address", f":{port}",        # Escuta na porta informada
        "-c", str(conf_path),           # Arquivo de topologia
        "--name", server_name
    ]

    out_fh = open(log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=out_fh,
        stderr=out_fh,
        creationflags=CREATE_NO_WINDOW
    )
    return proc

def spawn_client(server_ip: str, port: int, client_name: str, log_file: Path) -> subprocess.Popen:
    bins = get_binary_paths()
    cmd = [
        str(bins["client"]),
        "-f",
        "--name", client_name,
        f"{server_ip}:{port}"
    ]

    out_fh = open(log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=out_fh,
        stderr=out_fh,
        creationflags=CREATE_NO_WINDOW
    )
    return proc

def stop_all() -> int:
    """Mata com segurança qualquer instância ativa."""
    killed = 0
    targets = ("input-leaps.exe", "input-leapc.exe", "barrier.exe", "barrierc.exe")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if (proc.info['name'] or '').lower() in targets:
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed
```

---

### 3.2 `sysutils/leap_sys/leap_engine/leap_discovery.py`
*(Papel: Anúbis - Validação de Handshake de Rede e detecção de Servidor)*

```python
# sysutils/leap_sys/leap_engine/leap_discovery.py
"""
Anúbis: Sondagem rápida de socket TCP na rede local para detectar
instâncias do Input Leap ativas na porta padrão.
"""
from __future__ import annotations
import socket
import subprocess
import re

def test_tcp_connection(host: str, port: int, timeout: float = 0.8) -> bool:
    """Retorna True se conseguir conectar via socket TCP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def discover_server(port: int = 24800) -> str | None:
    """
    Sonda computadores conhecidos no ARP/Net View para ver quem está com a porta 24800 aberta.
    """
    candidates = []
    try:
        # Pega a tabela ARP local
        out = subprocess.check_output("arp -a", text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                ip = m.group(1)
                if not ip.startswith("255.") and not ip.startswith("224.") and not ip.endswith(".255"):
                    candidates.append(ip)
    except Exception:
        pass

    for ip in set(candidates):
        if test_tcp_connection(ip, port, timeout=0.3):
            return ip
    return None
```

---

### 3.3 `sysutils/leap_sys/leap_engine/leap_orchestration.py`
*(Papel: Atena - Orquestradora central das operações)*

```python
# sysutils/leap_sys/leap_engine/leap_orchestration.py
"""
Atena: Orquestrador da ponte de execução, logs e lifecycle do Leap Sys.
"""
from __future__ import annotations
import time
from pathlib import Path
from sysutils.leap_sys.leap_engine import leap_daemon, leap_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "leap"
LOG_DIR = DATA_DIR / "logs"

def start_host(server_name: str, client_name: str, position: str, port: int) -> tuple[bool, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "server.log"

    leap_daemon.stop_all()
    conf_path = leap_config.write_runtime_config(DATA_DIR, server_name, client_name, position)

    proc = leap_daemon.spawn_server(conf_path, port, server_name, log_file)
    time.sleep(1.0)

    if proc.poll() is not None:
        err = log_file.read_text(encoding="utf-8", errors="replace")[-500:] if log_file.exists() else "Erro desconhecido"
        return False, f"Falha ao iniciar o servidor. Saída do log:\n{err}"

    return True, f"Servidor rodando (PID: {proc.pid})"

def start_client(server_ip: str, client_name: str, port: int) -> tuple[bool, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "client.log"

    leap_daemon.stop_all()

    proc = leap_daemon.spawn_client(server_ip, port, client_name, log_file)
    time.sleep(1.0)

    if proc.poll() is not None:
        err = log_file.read_text(encoding="utf-8", errors="replace")[-500:] if log_file.exists() else "Erro desconhecido"
        return False, f"Falha ao iniciar o cliente. Saída do log:\n{err}"

    return True, f"Cliente rodando (PID: {proc.pid})"
```

---

## PARTE 5: Plataforma Windows (Firewall & Elevação)

### 5.1 `sysutils/leap_sys/leap_platform/leap_windows/leap_elevation.py`

```python
# sysutils/leap_sys/leap_platform/leap_windows/leap_elevation.py
import ctypes
import os

def is_admin() -> bool:
    """Verifica se o processo possui privilégios de Administrador."""
    if os.name != 'nt':
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
```

### 5.2 `sysutils/leap_sys/leap_platform/leap_windows/leap_firewall.py`

```python
# sysutils/leap_sys/leap_platform/leap_windows/leap_firewall.py
"""
Regras do Firewall do Windows para o Input Leap via netsh.
"""
from __future__ import annotations
import subprocess

def is_port_open(port: int) -> bool:
    """Verifica se há regra de liberação de porta ativa."""
    try:
        cmd = f"netsh advfirewall firewall show rule name=all"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return str(port) in res.stdout
    except Exception:
        return False

def open_firewall_port(port: int, rule_name: str = "InputLeap_Port") -> bool:
    """Cria regra de entrada TCP no Windows Firewall."""
    try:
        cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port}'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False
```

---


