
### 1. Diagnóstico do Contexto Android (W5+2H / ProDeNov 1)

* **O quê (What):** Acesso bidirecional a uma pasta comum entre Windows (`Amaranth`/`Bluebaby`) e smartphone Android.
* **Por quê (Why):** Conectar cabo USB toda hora ou enviar arquivos por mensageiros (WhatsApp/Telegram/Email) degrada a produtividade, comprime arquivos e quebra o fluxo de trabalho.
* **Onde (Where):** Rede Tailscale conectando Windows ↔ Android.

No Tailscale e no Android existem **três abordagens técnicas possíveis**. Analisamos cada uma para escolher o melhor plano:

| Método | Mecanismo | Prós | Contras |
| :--- | :--- | :--- | :--- |
| **Plano A: Taildrop (Nativo do Tailscale)** [1.1] | Envio ponto a ponto P2P via protocolo do Tailscale (`tailscale file cp`) [1.1] | **Sem configuração extra.** Funciona pelo menu nativo "Compartilhar" do Android e via CLI no Windows [1.1]. | É envio/recebimento de arquivos pontuais, não um sistema de arquivos montado contínuo [1.1]. |
| **Plano B: SMB Direto no Android** | Conectar o Android na pasta `\\100.x.y.z\Apricot` já criada | **Pasta montada de verdade.** O Android vê a pasta como se fosse um pendrive ou disco [1.2]. Pode editar, copiar e colar direto [1.2]. | Exige um gerenciador de arquivos no Android compatível com SMB (ex: Solid Explorer, Total Commander ou o próprio gerenciador nativo da Samsung/Xiaomi) [1.2]. |
| **Plano C: Tailscale Serve / WebDAV / HTTP Local** | Um servidor web/navegador leve exposto apenas na Tailnet via `sysutils` | Qualquer navegador no celular acessa `http://100.x.y.z:porta` para baixar e subir arquivos. | Interface web, um pouco menos integrada que uma pasta nativa. |

---

### 2. O Plano Recomendado (Combinação A + B)

Para ter o melhor dos dois mundos sem complexidade:

1. **Acesso como Disco (Plano B):**  
   Como você acabou de criar o compartilhamento `Apricot` (na Amaranth) e `Bluebaby_Share` (na Bluebaby), **o seu Android já tem acesso direto a essas pastas agora mesmo pela malha do Tailscale** [1.2].
2. **Envio Rápido Instantâneo (Plano A - Taildrop):**  
   Automatizar via CLI (`sysutils android drop` / `send`) o envio de arquivos do PC para o celular e vice-versa [1.1].

---

### 3. Como Acessar a Pasta do PC Direto no Android Agora (Plano B)

Você não precisa instalar servidores adicionais no PC; a pasta `C:\SysUtils_Shared` que você já compartilhou pode ser aberta no Android:

1. **No Android:** Certifique-se de que o **Tailscale** está conectado [1.2].
2. Abra o gerenciador de arquivos do seu celular:
   - **Samsung (Meus Arquivos):** Vá em *Armazenamento de Rede* ➔ *Adicionar Compartilhamento de Rede (SMB)*.
   - **Xiaomi / Motorola / Outros:** Baixe um gerenciador com suporte a SMB (recomendações leves e consagradas: **Solid Explorer**, **MiXplorer** ou **Total Commander com LAN Plugin**).
3. **Preencha os dados:**
   - **Endereço do Servidor:** `100.113.157.27` (Amaranth) ou `100.99.6.9` (Bluebaby)
   - **Caminho / Compartilhamento:** `Apricot`
   - **Usuário:** `olDox222`
   - **Senha:** `890890`
4. **Pronto!** A pasta `C:\SysUtils_Shared` do seu PC aparecerá como se fosse a memória interna do telefone [1.2]. Qualquer foto, APK, PDF ou código colado lá pelo PC aparece no celular no mesmo segundo [1.2].

---

### 4. Como Usar o Taildrop Nativo (Plano A)

O Tailscale possui o **Taildrop**, que transfere arquivos sem cabos entre qualquer máquina da rede [1.1]:

#### Do Android para o PC:
1. No Android, selecione qualquer foto ou arquivo e toque em **Compartilhar**.
2. Escolha **Tailscale** na lista [1.1].
3. Selecione `Amaranth` ou `Bluebaby` [1.1].
4. O arquivo cairá direto na pasta `Downloads` do Windows [1.1].

#### Do PC para o Android:
Podemos integrar o comando no `SysUtils`:
```bash
tailscale file cp "meu_arquivo.zip" android:
```
*(Onde `android` é o nome do seu celular cadastrado no Tailscale [1.1])*.

---

# BLITZPLAN: Subsistema de Compartilhamento e Sincronização Android (SyncDiag Android Hub)
**Documento:** `doxoade/docs/Protocols/Blitzplan_SyncDiag_Android.md`  
**Protocolo:** ProDeNov (Protocolo de Desenvolvimento Novíssimo — Diretrizes 0 a 6)  
**Projeto:** `Sysutils_proj`  
**Módulo Alvo:** `syncdiag` (com integração à malha Tailscale)  
**Estações:** `Amaranth` (PC-A), `Bluebaby` (PC-B) e dispositivos móveis `Android`  

---

## 1. Requisição e Análise Forense (W5+2H / ProDeNov 1 & 6.1)

* **O quê (What):** Criação do subsistema **SyncDiag Android Hub**, unificando acesso a arquivos, envio bidirecional e montagem de pastas compartilhadas entre PCs Windows e dispositivos Android através da malha virtual do Tailscale.
* **Onde (Where):**
  - Núcleo: `# syncdiag/core/android_hub.py` (Motor de transporte e ponte Android).
  - CLI: Expansão em `# syncdiag/cli/commands.py` sob o grupo `android` (acessível via `sysutils sync android` e `sysutils share android`).
  - Persistência: Diretório padrão `C:\SysUtils_Shared\Android\` (com pastas `Inbox` e `Outbox`).
* **Quem (Who):** Desenvolvedor transitando arquivos (código, APKs, mídias, logs, capturas de tela) entre computadores e smartphones.
* **Quando (When):** Sob demanda (envio rápido) ou persistente (estação de trabalho em produção).
* **Quanto (How Much):**
  - Zero dependências pesadas externas (usa Python stdlib: `http.server`, `urllib`, `socket` e o binário `tailscale.exe`).
  - Overhead de memória < 25 MB quando o servidor de staging web estiver ativo.
* **Por quê (Why):**
  - MTP via cabo USB no Windows trava com frequência, exige desbloquear a tela e quebra o fluxo de trabalho sem fio.
  - O envio de arquivos por WhatsApp/Telegram degrada a resolução de mídia, expõe dados a servidores de terceiros e limita tamanho.
  - Embora o Android esteja na malha Tailscale, o usuário não dispõe de um ponto centralizado e automatizado no terminal para despachar e puxar arquivos do telefone sem atrito.
* **Origem (Origin):** Necessidade de estender o sucesso do `sysutils share auto` (SMB) e `sysutils leap auto` (KVM) para a ponta móvel do ecossistema.
* **Consequências (Impact):** Eliminação de cabos e atrito cognitivo; tráfego 100% criptografado pelo túnel Tailscale; sincronia imediata entre telefone e computadores.

---

## 2. Análise de Complexidade e Riscos (ProDeNov 0.0 – 0.4)

| Fator ProDeNov | Grau | Mitigação Técnica |
| :--- | :---: | :--- |
| **0.0 Thirdparty** | Médio | Dependência da interface do Tailscale e de clientes Android. Mitigado usando padrões universais (HTTP, WebDAV e SMB). |
| **0.1 Devflow** | Baixo | Adição modular ao `syncdiag` sem alterar os motores existentes de Robocopy ou Barrier. |
| **0.2 Rabbit Hole** | Médio | Evitar desenvolver um aplicativo nativo Android do zero. Delegar a visualização a navegadores web e gerenciadores de arquivo padrão. |
| **0.3 Sensibilidade** | Baixo | I/O de rede contido na faixa CGNAT do Tailscale (`100.64.0.0/10`), inacessível pela internet pública. |
| **0.4 Revisitar** | Baixo | Arquitetura desacoplada via contratos de interface CLI simples. |

---

## 3. Arquitetura dos Planos de Ação (ProDeNov 1.2.1)

```text
                               ┌──────────────────────────────────────────────┐
                               │             TAILSCALE VIRTUAL MESH           │
                               │               (100.64.0.0/10)                │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       │                              │                              │
                       ▼                              ▼                              ▼
            ┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
            │   PLANO A (Padrão)   │      │   PLANO B (Bridge)   │      │   PLANO C (Físico)   │
            │  Micro Hub Web HTTP  │      │    Taildrop Worker   │      │      SMB Nativo      │
            │  (QR Code no Terminal│      │  (Fila P2P Tailscale)│      │  (Gerenciador Files) │
            │   Zero-App no Celular│      │  `tailscale file cp` │      │   Porta 445 Direta   │
            └──────────────────────┘      └──────────────────────┘      └──────────────────────┘
```

### 3.1. Plano A (Principal) — Micro Hub Web com QR Code no Terminal
* **Conceito:** O PC sobe um micro-servidor HTTP local leve (Python nativo), vinculado **exclusivamente ao IP Tailscale do PC** (`100.x.y.z:8080`), servindo a pasta `C:\SysUtils_Shared\Android`.
* **Fluxo UX:**
  1. No terminal do PC: `sysutils sync android web`.
  2. O terminal desenha um **QR Code em blocos ASCII/UTF-8**.
  3. Você aponta a câmera do Android para a tela do PC.
  4. O navegador do Android abre uma interface responsiva, com:
     - Botão *"Enviar Arquivo para o PC"* (com arrastar e soltar).
     - Lista de arquivos disponíveis no PC para download imediato no celular com 1 toque.
* **Segurança:** O servidor só escuta no adaptador do Tailscale. Dispositivos fora da sua conta Tailscale não conseguem nem ver a porta aberta.

### 3.2. Plano B (Alternativo) — Taildrop Auto-Bridge
* **Conceito:** Automação em torno da API do `tailscale file`.
* **Fluxo UX:**
  - **PC ➔ Android:** `sysutils sync android send <caminho_arquivo>`  
    Identifica o nome do celular no Tailscale e despacha o arquivo diretamente para a caixa de entrada do app Tailscale no Android via P2P.
  - **Android ➔ PC:** `sysutils sync android receive`  
    Worker que monitora e descarrega automaticamente os arquivos enviados via menu "Compartilhar com Tailscale" do Android para a pasta `C:\SysUtils_Shared\Android\Inbox`.

### 3.3. Plano C (Contingência) — Card de Montagem SMB para Android
* **Conceito:** Integração com os gerenciadores de arquivo padrão do Android (Samsung Meus Arquivos, Solid Explorer, MiXplorer).
* **Fluxo UX:** `sysutils sync android smb-card`  
  Exibe na tela do terminal um card visual com as credenciais já configuradas no `share auto` e instruções passo a passo para conectar o celular diretamente à pasta `Apricot` / `Bluebaby_Share`.

---

## 4. Placeholders & Estrutura de Código (ProDeNov 2)

### 4.1. Arquivo de Núcleo: `# syncdiag/core/android_hub.py`
* **Objetivo:** Orquestrar o servidor web leve, renderização de QR Code, automação de Taildrop e gestão das pastas de intercâmbio.

```python
# syncdiag/core/android_hub.py
"""
Núcleo de Intercâmbio de Dados Windows <-> Android via Tailscale.
Gerencia o Micro-Servidor Web com QR Code, automação Taildrop e pastas staging.
"""
from __future__ import annotations

import cgi
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANDROID_BASE_DIR = Path(r"C:\SysUtils_Shared\Android")
INBOX_DIR = ANDROID_BASE_DIR / "Inbox"
OUTBOX_DIR = ANDROID_BASE_DIR / "Outbox"


def ensure_android_dirs() -> Tuple[Path, Path]:
    """Garante a existência das pastas físicas de Inbox e Outbox com permissões NTFS."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    
    # Concede permissões totais para escrita
    for p in (INBOX_DIR, OUTBOX_DIR):
        subprocess.run(
            ["icacls", str(p), "/grant", "Todos:(OI)(CI)F", "/T", "/C", "/Q"],
            capture_output=True,
            text=True,
        )
    return INBOX_DIR, OUTBOX_DIR


def get_tailscale_ip() -> Optional[str]:
    """Recupera o IP Tailscale local (100.x.y.z) da máquina atual."""
    # 1. Tenta via tailscale status
    try:
        proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except Exception:
        pass

    # 2. Varre adaptadores locais de rede procurando faixa 100.x.y.z
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass

    return None


def generate_terminal_qr(data: str) -> None:
    """Renderiza um QR Code em blocos ASCII/UTF-8 diretamente no terminal."""
    try:
        import urllib.parse
        # Fallback leve: renderização de bloco caso qrencode/qrcode não esteja instalado
        print(f"\n[URL DE ACESSO MOBILE]: {data}\n")
    except Exception:
        print(f"\n[URL DE ACESSO MOBILE]: {data}\n")


class AndroidHubHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Handler HTTP customizado com interface responsiva mobile e suporte a upload."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ANDROID_BASE_DIR), **kwargs)

    def do_GET(self):
        # Renderiza dashboard mobile amigável
        return super().do_GET()

    def do_POST(self):
        # Processa upload multipart de arquivos enviados do smartphone
        pass


def run_micro_hub(port: int = 8080) -> None:
    """Inicia o servidor de staging HTTP no IP Tailscale."""
    ip = get_tailscale_ip()
    if not ip:
        raise RuntimeError("Adaptador Tailscale não encontrado ou desconectado.")

    ensure_android_dirs()
    server_address = (ip, port)
    
    with socketserver.TCPServer(server_address, AndroidHubHTTPHandler) as httpd:
        url = f"http://{ip}:{port}/"
        print(f"[*] Android Hub Web ativo em: {url}")
        generate_terminal_qr(url)
        httpd.serve_forever()
```

---

### 4.2. Extensão da CLI em `# syncdiag/cli/commands.py`

Adicionar o subgrupo `android` ao Click:

```python
# Em syncdiag/cli/commands.py:

@cli.group("android")
def android_group():
    """🤖 Subsistema de Conexão e Troca de Arquivos com Android (Tailscale)."""
    pass


@android_group.command("web")
@click.option("--port", "-p", default=8080, show_default=True, help="Porta HTTP do servidor móvel.")
def android_web(port):
    """Inicia o Micro Hub Web com QR Code para upload e download via celular."""
    from syncdiag.core import android_hub
    click.secho("\n=======================================================", fg="cyan")
    click.secho(" 📱 SYNCDIAG ANDROID WEB HUB (TAILSCALE STAGING)", fg="cyan", bold=True)
    click.secho("=======================================================\n", fg="cyan")
    try:
        android_hub.run_micro_hub(port=port)
    except KeyboardInterrupt:
        click.secho("\n[PARADO] Servidor Android Hub encerrado.", fg="yellow")


@android_group.command("send")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--target", default="android", help="Nome do dispositivo no Tailscale.")
def android_send(filepath, target):
    """Envia um arquivo para o Android via Taildrop P2P instantâneo."""
    click.echo(f"[*] Despachando '{filepath}' para o dispositivo '{target}' via Taildrop...")
    cmd = ["tailscale", "file", "cp", filepath, f"{target}:"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        click.secho(f"[OK] Arquivo enviado com sucesso para '{target}'!", fg="green", bold=True)
    else:
        click.secho(f"[ERRO] Falha no envio: {proc.stderr or proc.stdout}", fg="red")


@android_group.command("smb-card")
def android_smb_card():
    """Gera o cartão de conexão SMB para cadastrar no gerenciador do celular."""
    from syncdiag.core import network_connect
    station_key, profile = network_connect.identify_current_station()
    ip = network_connect.get_tailscale_ip()
    
    click.secho("\n--- DADOS DE CONEXÃO SMB PARA O CELULAR ---", fg="cyan", bold=True)
    click.echo(f"  • Servidor / Host : {click.style(ip, fg='green', bold=True)}")
    click.echo(f"  • Pasta / Share   : {click.style(profile['local_share_name'], fg='yellow', bold=True)}")
    click.echo(f"  • Usuário         : (seu usuário Windows local)")
    click.echo(f"  • Senha           : (sua senha cadastrada)")
    click.echo(f"  • Caminho Completo: smb://{ip}/{profile['local_share_name']}")
    click.secho("-------------------------------------------\n", fg="cyan")
```

---

## 5. Roteiro de Implementação e Testagem (RIT / Ritual)

- [ ] **Etapa 1:** Criar a pasta base física `C:\SysUtils_Shared\Android\` com permissões de gravação universal via `icacls`.
- [ ] **Etapa 2:** Implementar `syncdiag/core/android_hub.py` contendo:
  - Recuperação dinâmica de `tailscale ip -4`.
  - Servidor `SimpleHTTPRequestHandler` customizado com página HTML otimizada para telas móveis (touch-friendly).
  - Endpoint de upload multipart para receber arquivos direto do navegador do telefone.
- [ ] **Etapa 3:** Registrar o subgrupo `android` na CLI de `syncdiag/cli/commands.py`.
- [ ] **Etapa 4:** Teste de Fogo com o Celular:
  1. No PC: Rodar `sysutils sync android web`.
  2. No Celular: Acessar a URL com o Tailscale ativo no Android.
  3. Enviar uma foto do celular para o PC.
  4. Confirmar que a foto caiu em `C:\SysUtils_Shared\Android\`.
- [ ] **Etapa 5:** Validação de Regressão: Garantir que os comandos `share auto` e `leap auto` continuam funcionando sem interferência.

---

# RIT (Roteiro de Implementação e Testagem) — ETAPAS 3 e 4
**Protocolo:** ProDeNov (Diretrizes 1.2, 1.2.1, 3.1.4, 5.4 e 5.6)  
**Módulos Alvo:** `syncdiag/cli/commands.py` (Etapa 3) e `syncdiag/core/android_hub.py` (Etapa 4)  
**Objetivo:** Antecipar e blindar a orquestração CLI e o teste de fogo mobile com Planos A e B antes de escrever o núcleo.

---

## CAPÍTULO 1: RIT — ETAPA 3 (Registro da CLI, Namespace e Lazy-Loading)

### 1.1. Diagnóstico Preventivo de Riscos (Os Porquês)
* **O Risco de Colisão no `cli/main.py`:**  
  No `_lazy_map` do `main.py`, já existe o registro raiz:
  `'android': 'android_sys.cli.cmd_android:cli'`
  Se criássemos um comando raiz chamado `android`, haveria **conflito destrutivo de namespace**.
* **O Risco do Click Subgroup:**  
  Subcomandos aninhados precisam responder corretamente tanto em `sysutils sync android` quanto em `sysutils share android`, sem quebrar a introspecção do Click nem gerar exceções silenciosas de lazy import.

---

### 1.2. Planos de Execução da Etapa 3

#### 🟢 Plano A (Principal) — Duplo Registro Aninhado sem Conflito Raiz
* **Arquitetura:** O grupo `android` é criado dentro de `syncdiag/cli/commands.py` anexado ao `cli` raiz do `sync`. Em seguida, é vinculado como atalho também ao grupo `share`.
* **Comandos resultantes:**
  - `sysutils sync android web`
  - `sysutils sync android send`
  - `sysutils share android web` *(alias idêntico)*
* **Vantagem:** Não toca no comando raiz `sysutils android` (mantém o `android_sys` intacto, sem regressões).

#### 🟡 Plano B (Alternativo / Fallback) — Namespace Dedicado `mobile`
* **Gatilho de Acionamento:** Se durante a execução houver qualquer colisão de contexto ou introspecção do Click entre `android` do `syncdiag` e `android` do `android_sys`.
* **Arquitetura:** Renomeia o subgrupo dentro do `syncdiag` para `mobile` (`sysutils sync mobile web` / `sysutils share mobile web`).
* **Vantagem:** Isolamento léxico 100% garantido contra colisões.

---

### 1.3. Matriz de Falhas Previstas (Err Table — Etapa 3)

| ID | Sintoma | Causa Raiz Provável | Ação Preventiva / Solução |
| :---: | :--- | :--- | :--- |
| **E3.1** | `AttributeError: module has no attribute 'android_group'` | O `cli/main.py` tenta fazer split ou lazy-load de atributo não exportado. | Manter a invocação sempre aninhada dentro de `syncdiag.cli.commands:cli`. |
| **E3.2** | `ClickException: No such command 'android'` | Comando chamado via `sysutils share` sem o alias registrado. | Registrar explicitamente: `share_group.add_command(android_group, "android")`. |
| **E3.3** | `SyntaxError` / Import circular | `commands.py` importa `android_hub.py` no topo antes de resolver paths. | Import tardio (*lazy import*) de `android_hub` apenas dentro do corpo dos comandos. |

---

### 1.4. Checklist de Validação da Etapa 3
- [ ] Testar se `sysutils sync --help` exibe `android` na lista de comandos.
- [ ] Testar se `sysutils share --help` exibe `android` na lista de comandos.
- [ ] Testar se o comando raiz `sysutils android --help` original continua apontando para `android_sys` sem alterações.
- [ ] Validar sintaxe sem erros: `python -m py_compile syncdiag/cli/commands.py`.

---

## CAPÍTULO 2: RIT — ETAPA 4 (Teste de Fogo Mobile: Rede, Firewall e Upload)

### 2.1. Diagnóstico Preventivo de Riscos no Android
* **Risco 1 (Firewall do Windows na Porta 8080):** A porta 445 (SMB) já está aberta, mas a porta HTTP `8080` costuma vir bloqueada por padrão para adaptadores de rede.
* **Risco 2 (Obsolescência do módulo `cgi` no Python 3.12):**  
  O Python 3.12 descontinuou o módulo `cgi` (e removeu em 3.13). Tentar usar `cgi.FieldStorage` para upload multipart gera avisos graves e corrompe arquivos grandes no streaming do celular.
* **Risco 3 (Timeout e Sleep do Celular):**  
  O Android coloca navegadores em segundo plano para dormir após alguns segundos se a tela apagar ou a aba mudar.
* **Risco 4 (Conflito de Porta 8080):** A porta 8080 pode estar ocupada por outro processo na máquina.

---

### 2.2. Planos de Execução da Etapa 4

#### 🟢 Plano A (Principal) — Micro-Hub HTTP com Parser Streaming Nativo e Auto-Porta
* **Arquitetura:**
  1. **Auto-Hunting de Porta:** Se a porta `8080` estiver em uso, tenta automaticamente `8081`, `8082`, etc.
  2. **Liberação Automática de Firewall:** O comando adiciona regra temporária via `netsh` ou PowerShell para a porta escolhida na interface Tailscale.
  3. **Parser Streaming sem `cgi`:** O handler HTTP lê o `Content-Length` e consome os *chunks* do stream diretamente para um arquivo temporário no disco, extraindo o boundary do multipart sem estourar a RAM.
  4. **Interface Touch-Friendly:** HTML/CSS moderno, com botão grande de upload, barra de progresso e visualização imediata da lista de arquivos para download.

#### 🟡 Plano B (Alternativo) — Taildrop Nativo P2P (Zero Porta Aberta)
* **Gatilho de Acionamento:** Se a política de firewall do Windows impedir abertura da porta HTTP ou se o navegador do celular não conseguir carregar a página web por restrições de VPN móvel.
* **Arquitetura:**
  - O script desvia imediatamente para o motor **Taildrop**:
    - Dispara no PC: `tailscale file get --loop C:\SysUtils_Shared\Android\Inbox` em segundo plano.
    - Exibe no terminal a instrução para o usuário enviar o arquivo tocando no botão **Compartilhar ➔ Tailscale** do Android.
  - Vantagem: Dispensa abertura de portas HTTP e funciona 100% nativo pelo app do Tailscale.

#### 🔴 Plano C (Contingência) — Card SMB Visual com QR Code de Credenciais
* **Gatilho de Acionamento:** Falha de rede HTTP e Taildrop indisponível.
* **Arquitetura:** O terminal gera o card de conexão SMB com as credenciais já validadas no `share auto` (`Apricot` / `100.113.157.27`), permitindo que qualquer app gerenciador de arquivos do Android acesse a pasta como disco local.

---

### 2.3. Matriz de Falhas Previstas (Err Table — Etapa 4)

| ID | Sintoma | Causa Raiz | Ação Preventiva / Solução |
| :---: | :--- | :--- | :--- |
| **E4.1** | `OSError: [WinError 10048] Only one usage of each socket address` | Porta 8080 já está ocupada por outro software no Windows. | Função `find_free_port(start_port=8080)` que varre portas até achar uma livre. |
| **E4.2** | Celular carrega infinito / `ERR_CONNECTION_TIMED_OUT` | Windows Firewall bloqueando conexões de entrada na porta HTTP. | Injetar regra temporária no Firewall: `netsh advfirewall firewall add rule...`. |
| **E4.3** | Upload de arquivo grande trava ou corrompe | Uso do módulo depreciado `cgi.FieldStorage` acumulando dados na RAM. | Implementar buffer streaming em blocos de 64KB direto para o arquivo em disco. |
| **E4.4** | `ConnectionResetError` durante upload | Tela do celular apagou ou usuário trocou de aplicativo no Android. | Handler HTTP com bloco `try/except (ConnectionResetError, BrokenPipeError)` limpando arquivos temporários parciais. |

---

### 2.4. Checklist do Teste de Fogo (Etapa 4)

1. [ ] **Verificação de Escuta:** O servidor deve subir exclusivamente no IP `100.x.y.z` (Tailscale), **nunca** em `0.0.0.0` (proteção contra acesso externo não autorizado).
2. [ ] **Teste de Acesso Web:** Abrir o Chrome no Android com o Tailscale ligado e carregar `http://100.x.y.z:8080`.
3. [ ] **Teste de Upload (Celular ➔ PC):**
   - Selecionar uma foto/vídeo no celular.
   - Pressionar "Enviar".
   - Confirmar se o arquivo apareceu íntegro em `C:\SysUtils_Shared\Android\Inbox\`.
4. [ ] **Teste de Download (PC ➔ Celular):**
   - Colocar um arquivo de teste em `C:\SysUtils_Shared\Android\Outbox\`.
   - Clicar no link de download no navegador do celular e verificar se o arquivo baixou intacto.
5. [ ] **Encerramento Limpo:** Pressionar `Ctrl + C` no terminal do PC e verificar se a porta foi liberada imediatamente sem processos zumbis.

---

## 3. Decisão de Partida

Com os riscos mapeados, os planos B e C prontos e as matrizes de erro estruturadas, estamos seguros contra regressões. 

Podemos agora iniciar a **Etapa 1 (Estrutura física de pastas)** e a **Etapa 2 (Implementação do núcleo em `android_hub.py`)** seguindo exatamente os parâmetros aprovados neste RIT.
