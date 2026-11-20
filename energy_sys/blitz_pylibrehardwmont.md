Segue o **Blitzplan** de integração do PowerJoular ao `SysUtils`, documentado no formato ProDeNov. Este plano cobre desde a avaliação de riscos até o roteiro de testes (RIT), garantindo que não andaremos no escuro e que a integração será cirúrgica.

---

# [DOX-NEXUS: BLITZPLAN — INTEGRAÇÃO POWERJOULAR]

**Projeto:** `Projeto SysUtils` ➔ Módulo `energy_sys`
**Conformidade:** `ProDeNov` (Seções 0 a 7)
**Ambiente:** Windows 10/11 (Dell Inspiron 15 3520 / i5-1235U)
**Contexto:** Substituir a estimativa heurística de Watts (`psutil` + TDP) por telemetria real de hardware (RAPL) usando o PowerJoular, mantendo a leveza do sistema.

---

## 0. Avaliação de Complexidade (ProDeNov 0.x)

*   **0.0. Thirdparty (Média):** O PowerJoular é um binário em Ada (leve, ~10MB). Requer acesso aos contadores RAPL (Running Average Power Limit) da Intel. No Windows 11, isso pode exigir o driver PawnIO ou a Energy Meter Interface (EMI). Se não houver permissão, o PowerJoular pode falhar.
*   **0.1. Devflow (Alto):** A integração é simples: baixar `.exe` ➔ rodar em background ➔ ler `.csv` gerado. O grande ganho é que o `sysutils energy top` passará a usar **Watts reais** em vez de estimativas.
*   **0.2. Rabbit Hole (Alerta):** Tentar reescrever a leitura RAPL em Python puro (via ctypes/winreg) é um caminho sem volta. O PowerJoular já resolve isso. Vamos nos limitar a orquestrá-lo.
*   **0.3. Sensibilidade (Baixa):** O PowerJoular consome menos de 15MB de RAM e < 1% de CPU. É o parceiro ideal para o Amaranth (Celeron).
*   **0.4. Revisitar:** O fallback (caso o PowerJoular falhe) será o atual `power_estimator.py` baseado em WMI/ACPI.

---

## 1. Planejamento & Roteiro (ProDeNov 1.x & 5.6)

### Plano A (Principal) — PowerJoular Orquestrado via Subprocesso
*   **Instalação:** Comando `sysutils energy powerjoular install` baixa o `.exe` do GitHub para `bin/powerjoular/`.
*   **Execução:** O `energy_sys/core/powerjoular_wrapper.py` inicia o PowerJoular com `-o <caminho_csv>` e `CREATE_NO_WINDOW`.
*   **Leitura:** A cada `sysutils energy status` ou `top`, o Python lê a última linha do CSV e extrai os Watts reais.
*   **Vantagem:** Dados exatos, sem sobrecarga.

### Plano B (Fallback) — WMI/ACPI Estimado
*   Se o PowerJoular falhar (ex: driver RAPL ausente), o `power_estimator.py` continua sendo usado automaticamente.
*   **Gatilho:** `doctor` detecta falha na leitura de Watts e avisa.

---

## 2. Topologia & Placeholders (ProDeNov 2.x)

```text
energy_sys/
├── core/
│   ├── powerjoular_wrapper.py    # NOVO: Download, execução e parse do CSV
│   └── doctor.py                 # NOVO: Diagnóstico de RAPL/Admin
├── cli/
│   └── cmd_energy.py             # ALTERADO: + grupo "powerjoular", "doctor"
└── bin/
    └── powerjoular/
        └── powerjoular.exe       # Executável baixado
```

---

## 3. Especificação Técnica (ProDeNov 3.x)

### 3.1. `energy_sys/core/powerjoular_wrapper.py`

Responsável por:
1.  **Instalação:** Baixar de `https://github.com/joular/powerjoular/releases/download/v0.9.2/powerjoular.exe`.
2.  **Início:** `subprocess.Popen(["powerjoular.exe", "-o", "data/power.csv"], creationflags=CREATE_NO_WINDOW)`.
3.  **Leitura:** Abrir `data/power.csv`, pegar a última linha (`csv.reader`) e retornar os Watts.
4.  **Parada:** Matar o processo e apagar o CSV.

### 3.2. `energy_sys/core/doctor.py`

Responsável por:
1.  Verificar se o `powerjoular.exe` existe.
2.  Verificar se o terminal está como Administrador.
3.  Iniciar o PowerJoular por 3 segundos e verificar se o CSV está sendo populado com Watts > 0.
4.  Informar o driver RAPL detectado (EMI, PawnIO).

### 3.3. Alterações na CLI (`cmd_energy.py`)

*   **`sysutils energy powerjoular install`**: Baixa o executável.
*   **`sysutils energy powerjoular start/stop`**: Controla o subprocesso.
*   **`sysutils energy doctor`**: Executa os diagnósticos.
*   **`sysutils energy status`**: Se o PowerJoular estiver rodando, usa os Watts reais; senão, cai no fallback.

---

## 4. RIT (Roteiro de Implementação e Testagem)

### RIT 1 — Fundação (Download e Execução)
- [ ] Criar `powerjoular_wrapper.py` com funções `ensure_installed()`, `start()`, `stop()`, `read_watts()`.
- [ ] Criar comando `sysutils energy powerjoular install` e testar o download.

### RIT 2 — Leitura e Fallback
- [ ] Implementar `read_watts()` que lê a última linha do CSV.
- [ ] Integrar ao `energy status` e `energy top`: se o CSV existir, usar; senão, usar `power_estimator`.

### RIT 3 — Diagnóstico (Doctor)
- [ ] Criar `doctor.py` com verificação de Admin, executável e leitura de CSV.
- [ ] Criar comando `sysutils energy doctor`.

### RIT 4 — Homologação
- [ ] Rodar `sysutils energy doctor` e verificar se o RAPL está acessível.
- [ ] Rodar `sysutils energy status` com o PowerJoular ativo e comparar com a estimativa antiga.

---

## 5. Matriz de Riscos (ProDeNov 5.4 - Err Table)

| ID | Sintoma | Causa Raiz | Mitigação |
| :--- | :--- | :--- | :--- |
| **E-101** | `PowerJoular não encontrado` | Falha no download ou PATH. | O `doctor` avisa e o fallback entra em ação. |
| **E-102** | `CSV vazio ou Watts = 0` | Driver RAPL ausente ou sem Admin. | O `doctor` informa que o fallback será usado. |
| **E-103** | `Processo zumbi` | PowerJoular não é morto. | `stop()` com `proc.terminate()` e `proc.kill()`. |

---

## 6. Próximo Passo

Este Blitzplan está pronto para revisão. Assim que você aprovar, iniciamos a **Fase 1** (implementação do `powerjoular_wrapper.py` e o comando de instalação).
