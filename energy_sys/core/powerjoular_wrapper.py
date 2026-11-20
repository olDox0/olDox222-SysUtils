Excelente escolha. O **PyLibreHardwareMonitor** é uma biblioteca Python que atua como uma ponte para a DLL do *LibreHardwareMonitor* (C#). Ela lê os mesmos sensores de potência (RAPL, Intel Power) que o PowerJoular usaria, mas de forma direta, sem subprocessos ou CSVs.

O pulo do gato aqui é que a inicialização da `Computer()` no PyLibreHardwareMonitor exige privilégios de Administrador e o runtime do .NET instalado (que já vem no Windows 11). O grande risco é inicializar a biblioteca toda vez que rodar um comando (o que causa lentidão) ou não conseguir acessar os sensores por falta de Admin.

Aqui está o **Blitzplan revisado** para a nova arquitetura.

---

# [DOX-NEXUS: BLITZPLAN v2 — TELEMETRIA DE HARDWARE DIRETA]

**Projeto:** `Projeto SysUtils` ➔ Módulo `energy_sys`
**Conformidade:** `ProDeNov` (Seções 0 a 7)
**Ambiente:** Windows 10/11 (Dell Inspiron 15 3520 / i5-1235U)
**Objetivo:** Substituir a estimativa heurística (TDP) por leitura real de Watts via RAPL, usando o `PyLibreHardwareMonitor` (Python + .NET).

---

## 0. Avaliação de Complexidade (ProDeNov 0.x)

*   **0.0. Thirdparty (Média):** Dependência do pacote `pythonnet` e do runtime .NET (já presente no Windows 11). A biblioteca instala a DLL `LibreHardwareMonitorLib.dll` internamente.
*   **0.1. Devflow (Alto):** O fluxo será: instalar via `pip` ➔ criar singleton de conexão ➔ ler sensores (CPU Package, GPU) ➔ injetar no `power_estimator`. Elimina a necessidade de processos em background.
*   **0.2. Rabbit Hole (Alerta Vermelho):** Tentar abrir e fechar a conexão `Computer()` a cada segundo no `top --monitor` vai causar *throttling* e lentidão no terminal. A solução será um **Singleton** ou um `ContextManager`.
*   **0.3. Sensibilidade (Média):** A biblioteca carrega o .NET CLR na memória (~30-50 MB) apenas quando chamada. Não afetará a performance do i5-1235U se usado com parcimônia.
*   **0.4. Revisitar:** O fallback continuará sendo o `power_estimator.estimate_instant_watts()` (WMI/ACPI) caso o `doctor` detecte que o Admin ou os sensores não estão disponíveis.

---

## 1. Planejamento & Roteiro (ProDeNov 1.x & 5.6)

### Plano A (Principal) — PyLibreHardwareMonitor Acoplado
*   **Instalação:** `sysutils energy hardware install` (executa `pip install PyLibreHardwareMonitor`).
*   **Execução:** Um novo módulo `energy_sys/core/hardware_monitor.py` gerencia o singleton da classe `Computer()`.
*   **Leitura:** Lê o sensor de potência `CPU Package` (Intel RAPL).
*   **Vantagem:** Dados de hardware reais, sem CSV, sem subprocessos fantasmas.

### Plano B (Fallback) — WMI/ACPI Estimado
*   Se a leitura falhar (ex: terminal sem Admin ou sensor não encontrado), o `power_estimator.py` assume e o `sysutils energy status` avisa no rodapé: `[Fallback: Estimativa Heurística]`.

---

## 2. Topologia & Placeholders (ProDeNov 2.x)

```text
energy_sys/
├── core/
│   ├── hardware_monitor.py       # NOVO: Integração com PyLibreHardwareMonitor
│   ├── doctor.py                 # NOVO: Diagnóstico de Admin, .NET e Sensores
│   ├── power_estimator.py        # ALTERADO: Consome o hardware_monitor com fallback
│   └── powerjoular_wrapper.py    # DELETADO (abandonado)
├── cli/
│   └── cmd_energy.py             # ALTERADO: + "hardware" e "doctor"
```

---

## 3. Especificação Técnica (ProDeNov 3.x)

### 3.1. `energy_sys/core/hardware_monitor.py`
Responsável por:
1.  **Singleton:** Manter a instância do `Computer()` aberta em cache para não reabrir a DLL a cada leitura.
2.  **Leitura:** Iterar sobre `computer.hardware` e `computer.sensors`, buscando `SensorType.Power` no hardware `Cpu` e no sensor `"CPU Package"`.
3.  **Shutdown:** Método para fechar o `Computer()` no final da execução (para não deixar handles abertos).

### 3.2. `energy_sys/core/doctor.py`
Responsável por:
1.  Verificar se a biblioteca `PyLibreHardwareMonitor` está instalada (`importlib.util.find_spec`).
2.  Verificar se o terminal está elevado (Admin) usando `ctypes.windll.shell32.IsUserAnAdmin()`.
3.  Tentar ler o sensor de potência. Se retornar `None`, avisar que o hardware não expõe o RAPL ou precisa de Admin.

### 3.3. Alterações na CLI (`cmd_energy.py`)
*   **`sysutils energy hardware install`**: Instala a lib via `subprocess.run([sys.executable, "-m", "pip", "install", "PyLibreHardwareMonitor"])`.
*   **`sysutils energy hardware test`**: Roda o módulo e imprime os Watts atuais.
*   **`sysutils energy status`**: Tenta `hardware_monitor.read_power()`. Se falhar, usa `power_estimator`.
*   **`sysutils energy doctor`**: Roda os checks de Admin/Instalação.

---

## 4. RIT (Roteiro de Implementação e Testagem)

### RIT 1 — Fundação (Instalação e Singleton)
- [ ] Criar comando `sysutils energy hardware install` que dispara o `pip install`.
- [ ] Criar `hardware_monitor.py` com a estrutura de Singleton e a função `read_power()`.
- [ ] Testar a leitura básica com `sysutils energy hardware test`.

### RIT 2 — Integração e Fallback
- [ ] Modificar `power_estimator.py` para tentar o `hardware_monitor` primeiro.
- [ ] Se falhar (retornar `None`), usar a estimativa antiga.
- [ ] Atualizar o `cmd_status` para exibir a origem ("Real (RAPL)" ou "Estimado (WMI)").

### RIT 3 — Diagnóstico e UX
- [ ] Criar `doctor.py` com checagem de Admin e dependências.
- [ ] Criar comando `sysutils energy doctor`.

### RIT 4 — Homologação de Stress
- [ ] Rodar `sysutils energy top --monitor`. O singleton deve manter o uso de CPU baixo.
- [ ] Encerrar o comando e verificar se o handle .NET foi liberado corretamente.

---

## 5. Matriz de Riscos (ProDeNov 5.4 - Err Table)

| ID | Sintoma | Causa Raiz | Mitigação |
| :--- | :--- | :--- | :--- |
| **E-201** | `ModuleNotFoundError: PyLibreHardwareMonitor` | Lib não instalada. | O `doctor` avisa e o fallback WMI assume. |
| **E-202** | `Watts = None` ou `PermissionError` | Terminal não está como Administrador. | O `doctor` exibe instrução para abrir CMD como Admin. |
| **E-203** | `Terminal travado` no `--monitor` | O Singleton não está sendo reutilizado. | Implementar padrão de classe estática com `__new__`. |
| **E-204** | `System.AccessViolationException` | DLL do .NET conflitou com outro processo. | Adicionar `try/except` robusto no `read_power()` e chamar `close()` |

---

## 6. Próximo Passo

Com o Blitzplan aprovado, a **Fase 1** consistirá em:
1. Criar o módulo `hardware_monitor.py` com o Singleton da DLL.
2. Criar o comando de instalação e teste (`sysutils energy hardware install`).

Podemos iniciar a codificação da Fase 1?
