# [BLITZPLAN & BLUEPRINT: INFRAESTRUTURA ANDROID / BENZAITEN NEOGUI]
**Projeto:** `Projeto SysUtils` / `Doxoade Benzaiten`  
**Conformidade:** `ProDeNov` (Protocolo de Desenvolvimento Novíssimo — Seções 0 a 7)  
**Ambiente:** Windows 10/11 (Amaranth: Celeron N2808 2GB RAM; Bluebaby: i5-1235U 12 Threads) ➔ Android Target (Termux / Wireless ADB).

---

## 0. Avaliação de Complexidade (ProDeNov 0.x)

* **0.0. Thirdparty:** **Média-Alta.** Não usaremos o Android Studio nem o daemon do Gradle (que consomem 4GB a 8GB de RAM e quebrariam o Amaranth). Empregaremos ferramentas autônomas de linha de comando: `aapt2`, `d8`, `apksigner` (Android Build-Tools) e o compilador C nativo `clang` do Android NDK ou OpenJDK headless.
* **0.1. Devflow:** O fluxo precisa ser transparente: `Escrever código (C / HTML / JS) ➔ Compilar ➔ Assinar ➔ Envio Wireless ➔ Auto-Launch ➔ Scrcpy Mirror`.
* **0.2. Rabbit Hole:** **Risco Crítico.** Evitar cair na armadilha de tentar construir um ecossistema Gradle completo via CLI. O empacotamento deve ser cirúrgico: bytecode compilado para `.dex`, empacotado via `aapt2` direto no `.apk`.
* **0.3. Sensibilidade:** Alta no Amaranth (2 GB RAM). O compilador local não pode alocar heap pesada. A execução e renderização são transferidas 100% para o SoC do smartphone via Wi-Fi.
* **0.4. Revisitar:** Construir templates prontos de casca (*Shell APK*) reutilizáveis para que uma alteração em HTML/JS/C não exija reconfigurar manifestos ou chaves criptográficas.

---

## 1. Planejamento & Análise de Viabilidade (ProDeNov 1.x)

### 1.1. Contexto e Motivação Técnica
O objetivo não é apenas gerar APKs genéricos, mas viabilizar o **NeoGUI do Doxoade Benzaiten**:
* No Desktop, o Benzaiten usa `dxgui_win.c` (Webview2 / GDI / Software Render) conectado ao Python via `HermesRouter` (`__dx_send__` e `__dx_receive__`).
* No Android, o equivalente nativo perfeito é o componente **`android.webkit.WebView`** com **`addJavascriptInterface`**, permitindo rodar a mesmíssima interface HTML5/CSS3 (como o `thoth_gui.html`) trocando mensagens de mão dupla com o backend em C ou Kotlin sem reescrever a UI.

### 1.2. Planos de Contingência (ProDeNov 1.2.1)

* **Plano A (Recomendado — Benzaiten Web-Shell Cirúrgico / Headless SDK):**
  * Uma casca APK ultraleve (~800 KB) com suporte a WebView em tela cheia e offline.
  * O `SysUtils` baixa apenas as ferramentas puras de linha de comando (`aapt2`, `d8`, `android.jar`, `zipalign`, `apksigner`) totalizando menos de 100 MB.
  * Ao rodar `sysutils android build`, o sistema injeta os assets (HTML/CSS/JS do Benzaiten) e compila o APK em 3 segundos.
* **Plano B (PWA Nativo / TWA Standalone via Bubblewrap):**
  * Utilizar o motor oficial da Google (Trusted Web Activity) que encapsula a aplicação web com ícone, tela cheia, permissões e isolamento completo sem precisar tocar em código Java/Kotlin.
* **Plano C (Termux On-Device Bridge / Fallback Local):**
  * Utilizar o ambiente que você já tem no celular: compilar binários C e scripts dentro do próprio Termux usando o `clang` nativo do ARM64, controlando tudo remotamente via `sysutils android shell` ou espelhamento wireless.

---

## 2. Topologia & Placeholders do Módulo `android_sys` (ProDeNov 2.x)

```text
Projeto SysUtils/
├── bin/
│   └── android/
│       ├── adb.exe
│       ├── scrcpy.exe
│       └── build-tools/        # aapt2, d8, zipalign, apksigner, android.jar
└── android_sys/
    ├── __init__.py
    ├── cli/
    │   ├── __init__.py
    │   └── cmd_android.py      # Zeus: CLI click (build, deploy, run, bridge)
    ├── core/
    │   ├── __init__.py
    │   ├── adb_manager.py      # Conexão TCP/IP, envio wireless de APKs
    │   ├── sdk_installer.py    # Hefesto: Baixa apenas build-tools mínimos
    │   ├── apk_builder.py      # Hera/Hefesto: Pipeline aapt2 + d8 + apksigner
    │   └── hermes_android.py   # Hermes: Bridge de mensagens Python/C <-> JS Mobile
    └── templates/
        └── benzaiten_shell/    # Casca nativa minimalista do WebView
            ├── AndroidManifest.xml
            └── src/MainActivity.java
```

---

## 3. Especificação Técnica dos Componentes (ProDeNov 2.1 & 3.x)

### 3.1. O Pipeline Cirúrgico de Build (Sem Gradle / Sem Android Studio)
Em vez de baixar gigabytes de dependências, o `apk_builder.py` executa o pipeline direto:

```text
[Benzaiten HTML/CSS/JS] ──┐
[AndroidManifest.xml]   ──┼─► aapt2 compile/link ──► [resources.apk]
                          │                                │
[MainActivity.java]     ──┴─► javac ─► d8 (dex) ───────────┼─► zip / zipalign ─► apksigner ─► [app-release.apk]
```

### 3.2. Esboço dos Placeholders Principais

#### Placeholder 1: `android_sys/core/sdk_installer.py`
```python
# android_sys/core/sdk_installer.py
"""
Hefesto: Obtenção cirúrgica das ferramentas de linha de comando do Android.
Baixa apenas aapt2, d8, android.jar e apksigner (ignora Android Studio e Gradle).
"""
from __future__ import annotations
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDK_TOOLS_DIR = PROJECT_ROOT / "bin" / "android" / "build-tools"

# URL das Command-Line Tools oficiais headless da Google (~120 MB)
CMDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

def is_sdk_ready() -> bool:
    """Verifica se aapt2, d8 e android.jar estão presentes."""
    required = ["aapt2.exe", "d8.bat", "android.jar", "apksigner.jar"]
    return all((SDK_TOOLS_DIR / f).exists() for f in required)

def ensure_minimal_sdk() -> tuple[bool, str]:
    """Baixa e extrai apenas os binários vitais para compilação sem Gradle."""
    if is_sdk_ready():
        return True, f"SDK mínimo pronto em {SDK_TOOLS_DIR}"
    # Fluxo de download e extração cirúrgica...
    return True, "SDK configurado com sucesso."
```

#### Placeholder 2: `android_sys/core/apk_builder.py`
```python
# android_sys/core/apk_builder.py
"""
Hefesto: Compilador e empacotador de APKs sem Gradle.
Executa aapt2 link + javac + d8 + zipalign + apksigner.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

def compile_benzaiten_apk(
    app_name: str,
    web_assets_dir: Path,
    output_apk: Path
) -> tuple[bool, str]:
    """
    Empacota uma interface web do Benzaiten dentro da casca APK nativa.
    1. Injeta web_assets_dir na pasta assets/ da casca.
    2. Compila recursos via aapt2.
    3. Gera classes.dex via d8.
    4. Assina o APK com keystore de debug local.
    """
    # Execução controlada dos binários sem travar terminal...
    return True, f"APK gerado com sucesso: {output_apk}"
```

#### Placeholder 3: `android_sys/core/hermes_android.py`
```python
# android_sys/core/hermes_android.py
"""
Hermes: Bridge de comunicação entre a interface Webview e o backend.
Replica a assinatura do HermesRouter do Benzaiten Desktop no Android.
"""
from __future__ import annotations
import json

class HermesMobileBridge:
    """
    Permite que o frontend HTML/JS envie comandos como:
    window.__dx_send__('sensor', { read: 'accel' })
    e receba respostas estruturadas sem recarregar a tela.
    """
    pass
```

---

## 4. Diagnóstico Forense & Rastreabilidade (ProDeNov 3.1.4)

O sistema de diagnóstico do `android_sys build` deve responder estritamente:
* **O quê falhou?** (Sintaxe XML no Manifesto, erro de tipos no JS ou falha de compilação `.dex`).
* **Onde?** Arquivo exato e linha do asset (`thoth_gui.html`, `MainActivity.java` ou `assets/`).
* **Quando e Quanto?** Tempo de compilação, tamanho do APK resultante e consumo de banda Wi-Fi.
* **Reversibilidade:** Caso a compilação ou deploy falhe, o último APK funcional permanece intocado e o celular mantém a versão anterior.

---

## 5. Roteiro de Implementação & RIT (Ritual de Testes — ProDeNov 5.6)

1. **RIT 1 — Fundação Headless:**
   - Criar estrutura de diretórios e validar a presença das ferramentas em `bin/android/`.
   - Adicionar o comando `sysutils android sdk setup`.
2. **RIT 2 — Casca Minimalista Benzaiten:**
   - Montar o template `benzaiten_shell` (um `MainActivity` ultraleve com `WebView` configurado para tela cheia e hardware acceleration ativado).
3. **RIT 3 — Compilação e Deploy Sem Fio:**
   - Implementar `sysutils android build --source <pasta_html>`.
   - Conectar o pipeline ao `adb install -r` via Wi-Fi e auto-abrir no celular via `scrcpy`.
4. **RIT 4 — Homologação da Ponte Hermes:**
   - Testar um botão HTML na tela do celular disparando um comando no PC pelo espelhamento.

---

Se aprovar o planejamento, avançaremos para o **RIT 1** para validar a extração do SDK cirúrgico sem instalar nenhum software pesado no Windows.

# [DOX-NEXUS: ROTEIRO DE IMPLEMENTAÇÃO E TESTAGEM (RIT 1 & RIT 2)]
**Projeto:** `Projeto SysUtils` ➔ Módulo `android_sys`  
**Conformidade:** `ProDeNov.md` (Seções 0 a 7)  
**Ambiente:** Windows 10/11 (Amaranth: Celeron N2808 2GB / Bluebaby: i5-1235U) ➔ Android 11+ (Termux / Wireless ADB)  
**Contexto de Engenharia:** Construção de infraestrutura ultraleve de compilação, empacotamento e ponte de comunicação móvel para o **NeoGUI do Doxoade Benzaiten** sem dependência do Android Studio ou do daemon do Gradle.

---

## 0. Matriz de Complexidade Preliminar (ProDeNov 0.x)

* **0.0. Thirdparty (Média):** `aapt2`, `d8`, `zipalign`, `apksigner`, `android.jar` (API 33/34). Evitar dependência de JDK completa pesada (>300 MB); priorizar ferramentas isoladas ou compilação desacoplada.
* **0.1. Devflow (Otimizado):** O ciclo de desenvolvimento deve ser contínuo:
  $$\text{Editar HTML/JS/C} \xrightarrow{\text{1 comando CLI}} \text{Gerar APK} \xrightarrow{\text{Wi-Fi}} \text{Instalar} \xrightarrow{\text{Scrcpy Auto-Launch}}$$
* **0.2. Rabbit Hole (Alerta Vermelho):** Tentar montar um parser completo de Gradle na mão é um *rabbit hole* fatal. A compilação deve usar o pipeline atômico puro do Android SDK de linha de comando.
* **0.3. Sensibilidade:** O Amaranth tem apenas **2 GB de RAM**. O pipeline de build deve consumir menos de **150 MB de RAM** de pico durante o empacotamento.
* **0.4. Revisitar:** Arquitetura desacoplada em duas partes: a *Casca Nativa* (estável, raramente muda) e os *Assets Benzaiten* (voláteis, mudam a cada edição de tela).

---

# PARTE I: PLANEJAMENTO DO RIT 1 — FUNDAÇÃO HEADLESS (SDK CIRÚRGICO)

### 1.1. Objetivo do RIT 1
Estabelecer o ferramental mínimo de compilação em `bin/android/build-tools/`, provendo comandos de auditoria e download automatizado sem que o desenvolvedor precise instalar gigabytes no sistema operacional.

### 1.2. Plano A vs. Plano B (ProDeNov 1.2.1)
* **Plano A (Headless CLI Standalone Oficial):**
  * Baixa o pacote oficial das **Android Command-Line Tools** (~120 MB) e extrai estritamente: `aapt2.exe`, `d8.bat`, `zipalign.exe`, `apksigner.bat` e um único `android.jar` (API 33).
  * Peso total em disco: **~85 MB** (em vez dos 15 GB do Android Studio).
* **Plano B (Pre-baked Core Fallback / Casca Pré-Compilada):**
  * Se o computador estiver sem internet ou o download falhar, o `SysUtils` utiliza uma casca `classes.dex` universal já forjada embutida no repositório.
  * O empacotador precisa apenas do `aapt2` e de um zip-aligner para injetar os arquivos HTML/JS na pasta `assets/`, **dispensando qualquer compilador Java/Kotlin no PC**.

### 1.3. Tabela de Previsão de Falhas do RIT 1 (ProDeNov 5.4 - Err Table)

| ID | Sintoma | Causa Raiz | Ação Preventiva / Mitigação |
| :--- | :--- | :--- | :--- |
| **E-101** | `java.exe not found` ao rodar `d8` ou `apksigner` | PC não tem JRE no PATH | Usar fallback do Java do sistema ou compilar via *Plano B* (Dex Pré-assado). |
| **E-102** | Download corrompido ou abortado por Wi-Fi | Oscilação de rede durante fetch do zip | Download em buffer com validação de hash SHA-256 e retentativa atômica. |
| **E-103** | Caminho com espaços no Windows quebra `d8.bat` | `C:\Users\Victor Alexandre\...` | Execução com argumentos em lista (`shell=False`) e caminhos via `Path.resolve()`. |

### 1.4. Tasklist do RIT 1
- [ ] Criar módulo `android_sys/core/sdk_installer.py`.
- [ ] Implementar verificação de integridade dos 4 binários-chave (`aapt2`, `d8`, `zipalign`, `android.jar`).
- [ ] Implementar comando `sysutils android sdk status` com laudo visual no terminal.
- [ ] Implementar comando `sysutils android sdk setup --dry-run` e `--apply`.

---

# PARTE II: PLANEJAMENTO DO RIT 2 — CASCA MINIMALISTA BENZAITEN (`benzaiten_shell`)

### 2.1. Objetivo do RIT 2
Projetar o template da aplicação Android que servirá de hospedeiro para qualquer interface webview do Benzaiten (como o `thoth_gui.html` ou o futuro NeoGUI), espelhando a arquitetura desktop `dxgui_win.c`.

### 2.2. Arquitetura da Casca & Mapeamento de Paridade Desktop ➔ Mobile

| Recurso | Benzaiten Desktop (`dxgui_win.c`) | Benzaiten Mobile (`benzaiten_shell`) |
| :--- | :--- | :--- |
| **Janela / Render** | Win32 HWND + Webview2 Runtime | Android `Activity` + `android.webkit.WebView` |
| **Aceleração Gráfica** | DirectComposition / GDI | Hardware Acceleration (`android:hardwareAccelerated="true"`) |
| **Armazenamento Local** | SQLite local / Sistema de Arquivos | DOM Storage / IndexedDB habilitados |
| **Bridge JS ➔ Backend** | `window.__dx_send__(action, payload)` | `@JavascriptInterface public void __dx_send__(...)` |
| **Bridge Backend ➔ JS** | `dxgui_eval_js("window.__dx_receive__(...)")` | `webView.evaluateJavascript("window.__dx_receive__(...)", null)` |

### 2.3. Plano A vs. Plano B (ProDeNov 1.2.1)
* **Plano A (Compilação On-Demand via Java + D8):**
  * O código-fonte `MainActivity.java` fica aberto na pasta de templates.
  * O `apk_builder.py` compila o Java com `javac` contra o `android.jar` e gera o `classes.dex` via `d8`.
* **Plano B (Casca Universal Dex Imutável - Zero-Compile):**
  * O `MainActivity` é compilado uma única vez e gera um `classes.dex` genérico de 18 KB.
  * Todas as aplicações móveis do Benzaiten passam a ser puramente a substituição da pasta `assets/` (HTML/CSS/JS) e a reescrita do `AndroidManifest.xml` via `aapt2 link`.
  * **Vantagem:** O tempo de build cai para **menos de 1 segundo**, ideal para o processador Celeron do Amaranth.

### 2.4. Tasklist do RIT 2
- [ ] Criar estrutura do template `android_sys/templates/benzaiten_shell/`.
- [ ] Escrever `AndroidManifest.xml` estritamente delimitado (sem permissões abusivas, tela cheia, rotação adaptativa).
- [ ] Escrever `MainActivity.java` implementando o contrato `HermesMobileBridge` (`__dx_send__` e `__dx_receive__`).
- [ ] Criar o injetor de assets (`index.html`, estilos e scripts).
- [ ] Validar a paridade do bridge com o `HermesRouter.py` existente no desktop.

---

# PARTE III: ESBOÇO DOS PLACEHOLDERS (ProDeNov 2.x)

Os arquivos a seguir definem o contrato estrutural das duas fases, contendo cabeçalhos relativos, docstrings de responsabilidade e imports declarativos.

### Placeholder 1: `android_sys/core/sdk_installer.py`
```python
# -*- coding: utf-8 -*-
# android_sys/core/sdk_installer.py
"""
Hefesto: Gerenciador de Instalação e Auditoria do Android SDK Mínimo (Headless).
Responsável pela aquisição cirúrgica de aapt2, d8, zipalign e android.jar
sem necessidade de instalação do Android Studio ou do daemon do Gradle.
"""
from __future__ import annotations
import os
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Tuple

# Constantes de Topologia
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_ANDROID_DIR = PROJECT_ROOT / "bin" / "android"
BUILD_TOOLS_DIR = BIN_ANDROID_DIR / "build-tools"

# URLs oficiais e fixas dos binários headless
AAPT2_STANDALONE_URL = "https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/8.2.2-10154469/aapt2-8.2.2-10154469-windows.jar"
COMMANDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

def get_required_tools() -> Dict[str, Path]:
    """Retorna o dicionário de ferramentas essenciais para build sem Gradle."""
    return {
        "aapt2": BUILD_TOOLS_DIR / "aapt2.exe",
        "d8": BUILD_TOOLS_DIR / "d8.bat",
        "zipalign": BUILD_TOOLS_DIR / "zipalign.exe",
        "apksigner": BUILD_TOOLS_DIR / "apksigner.bat",
        "android_jar": BUILD_TOOLS_DIR / "android.jar",
    }

def audit_sdk_tools() -> Dict[str, bool]:
    """Inspeciona o disco e verifica quais ferramentas estão presentes e executáveis."""
    tools = get_required_tools()
    return {name: path.exists() and path.stat().st_size > 1024 for name, path in tools.items()}

def is_sdk_ready() -> bool:
    """Retorna True se todo o kit cirúrgico estiver pronto para compilação."""
    return all(audit_sdk_tools().values())

def install_minimal_sdk(dry_run: bool = True) -> Tuple[bool, str]:
    """
    Executa o download e instalação cirúrgica dos componentes necessários.
    Suporta salvaguarda dry-run obrigatória (ProDeNov 5.3).
    """
    # Fluxo a ser implementado no RIT 1
    raise NotImplementedError("Implementação controlada no RIT 1.")
```

### Placeholder 2: `android_sys/core/apk_builder.py`
```python
# -*- coding: utf-8 -*-
# android_sys/core/apk_builder.py
"""
Hefesto / Hera: Motor de Compilação e Empacotamento Autônomo de APKs Benzaiten.
Executa o pipeline atômico:
  1. aapt2 compile/link (Manifesto + Recursos)
  2. d8 (Conversão Java Bytecode ➔ classes.dex)
  3. Injeção de Assets HTML/JS/CSS do Benzaiten
  4. zipalign (Alinhamento de 4 bytes)
  5. apksigner (Assinatura com chave de debug criptográfica)
"""
from __future__ import annotations
import subprocess
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional
from android_sys.core import sdk_installer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "android_sys" / "templates" / "benzaiten_shell"
BUILD_CACHE_DIR = PROJECT_ROOT / "data" / "android_build"

def preflight_build_check(source_html_dir: Path) -> Tuple[bool, str]:
    """
    Valida a existência dos assets de frontend e integridade das ferramentas.
    Responde: O quê, Onde e Por quê antes de disparar o compilador.
    """
    if not sdk_installer.is_sdk_ready():
        return False, "Ferramentas do SDK incompletas. Execute 'sysutils android sdk setup'."
    if not source_html_dir.exists() or not (source_html_dir / "index.html").exists():
        return False, f"Diretório fonte '{source_html_dir}' não contém um 'index.html' válido."
    return True, "Preflight de build aprovado."

def build_benzaiten_apk(
    app_name: str,
    package_id: str,
    source_html_dir: Path,
    output_apk: Path,
    use_prebaked_dex: bool = True,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Executa o pipeline completo de compilação sem intervenção de IDE externa.
    """
    # Fluxo a ser implementado no RIT 2
    raise NotImplementedError("Implementação controlada no RIT 2.")
```

### Placeholder 3: `android_sys/templates/benzaiten_shell/AndroidManifest.xml`
```xml
<!-- android_sys/templates/benzaiten_shell/AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.doxoade.benzaiten"
    android:versionCode="1"
    android:versionName="1.0.0">

    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />

    <!-- Permissões mínimas para inter-operabilidade local / dev -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:label="Benzaiten NeoGUI"
        android:hardwareAccelerated="true"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.NoTitleBar.Fullscreen">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

### Placeholder 4: `android_sys/templates/benzaiten_shell/src/MainActivity.java`
```java
/* android_sys/templates/benzaiten_shell/src/MainActivity.java */
package com.doxoade.benzaiten;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.util.Log;

/**
 * Benzaiten Mobile Shell: Hospedeiro de UI ultraleve.
 * Espelha a funcionalidade do dxgui_win.c / HermesRouter no Android.
 */
public class MainActivity extends Activity {
    private WebView webView;
    private static final String TAG = "BenzaitenMobile";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        
        // Habilitações vitais para UI reativa sem lag
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);

        // Bridge Hermes Mobile: JS chama window.__dx_native__.send(...)
        webView.addJavascriptInterface(new HermesBridge(), "__dx_native__");

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        // Carrega o app empacotado nos assets locais
        webView.loadUrl("file:///android_asset/index.html");
        setContentView(webView);
    }

    public class HermesBridge {
        @JavascriptInterface
        public void send(String payload) {
            Log.d(TAG, "Hermes Message Received: " + payload);
            // Ponto de integração: redirecionamento para o sistema local ou ADB
        }
    }
}
```

---

# PARTE IV: RITUAL DE TESTES & HOMOLOGAÇÃO (RIT Loop — ProDeNov 5.6)

Seguindo o princípio de testagem calma e sem *development hell* (`Discussão ➔ Implementação ➔ Teste ➔ Validação`):

```text
[RIT 1: Ferramental]
   1. Executar: sysutils android sdk status
      - Confirmação visual do checklist das 5 ferramentas essenciais.
   2. Executar: sysutils android sdk setup
      - Baixa as ferramentas e confirma ausência de erros no PATH/diretórios.

[RIT 2: Casca e Compilação]
   3. Executar: sysutils android build --test-shell
      - Gera o primeiro APK teste (menos de 1 MB) na pasta data/android_build/.
   4. Executar: sysutils android deploy
      - Envia o APK pelo ar (Wi-Fi) para o celular 192.168.18.105 e abre a tela via Scrcpy.
```

Com esta base delimitada e validada segundo os cânones do `ProDeNov`, podemos avançar para a **codificação do RIT 1** com total segurança e clareza de escopo.
