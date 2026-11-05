# A2MS — Android Audio Management System

**Status:** Base Consolidada (RIT-A & RIT-B concluídos)
**Módulos:** `android_sys/core/audio_*`, `android_sys/templates/benzaiten_shell`

## 1. Arquitetura e Limitações (ProDeNov 0.x)

O ecossistema de áudio do Android é dividido em duas camadas de acesso:

### Tier 1 — Sandbox Nativo (100% Self-Contained)
*   **Como funciona:** Usa a API nativa `AudioManager` dentro do próprio app.
*   **O que vê:** `isMusicActive`, volumes de stream, modo de áudio, ringer mode.
*   **Limitação:** O Android proíbe que um app veja o foco de áudio de *outros* apps.
*   **Uso:** App Mobile (SysUtils Mobile) e lógica de sobrevivência.

### Tier 2 — Shizuku / ADB (Observabilidade Profunda)
*   **Como funciona:** Usa `appops` e `dumpsys audio` via shell (PC via ADB ou Mobile via Shizuku).
*   **O que vê:** Pilha de foco completa (quem está com `GAIN`, `LOSS`, `DUCK`).
*   **Limitação:** Requer app externo (Shizuku) ou PC conectado. Não é self-contained.
*   **Uso:** CLI (`sysutils android audio`).

## 2. CLI — Gerenciamento e Reversibilidade

O CLI permite manipular o `TAKE_AUDIO_FOCUS` via ADB. A regra empírica descoberta:
*   Apps como **VLC** toleram `ignore` (continuam tocando).
*   Apps como **Vivaldi / Firefox** quebram com `ignore` (param de tocar). Para eles, usar `allow`.

### Comandos Principais:
*   `sysutils android audio patch --apps <pkg> --mode mix --apply`
    *   Aplica `ignore` no pacote. Tira snapshot automático antes.
*   `sysutils android audio restore --apps <pkg>`
    *   Devolve para `allow` (comportamento padrão).
*   `sysutils android audio snapshot --apps <pkg>`
    *   Salva o estado atual em `data/audio_state/last_snapshot.json`.
*   `sysutils android audio verify`
    *   Compara o estado atual com o último snapshot.
*   `sysutils android audio rollback`
    *   Reverte todos os pacotes ao estado do snapshot.
*   `sysutils android audio history`
    *   Lê o log JSONL de operações (audit trail).
*   `sysutils android audio probe`
    *   Lê o `dumpsys audio` via ADB e mostra a pilha atual.

## 3. SysUtils Mobile (App Android)

O app é construído sem Gradle via `sysutils android build --apply`.

*   **MainActivity.java:** Contém a ponte `HermesBridge` e o monitor de áudio (Handler de 2s).
*   **Interface:** `assets/index.html` com design escuro e `dx_bridge.js`.
*   **Dependências:** JARs do Shizuku são baixados automaticamente pelo `sdk_installer.py` e injetados via classpath no `javac`.

### Diagnóstico Shizuku
Se o status estiver `NOT_RUNNING`, use o botão "🩺 Diagnóstico Shizuku" no app. Ele mostrará se o pacote Shizuku está instalado e se o Binder está ativo.

## 4. Próximos Passos (Fora do Escopo Atual)
1.  Instalar o app Shizuku no celular para ativar o Tier 2 no Mobile.
2.  Refinar o parser do `dumpsys audio` para o padrão da Samsung (One UI Core).
3.  Adicionar controle de volume (Tier 1) na UI do app.
