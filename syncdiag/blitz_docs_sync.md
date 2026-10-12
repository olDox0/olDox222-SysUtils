# Blitzplan & Blueprint: Conexão e Compartilhamento de Rede (Amaranth ↔ Bluebaby)
**Protocolo:** ProDeNov (Protocolo de Desenvolvimento Novíssimo)  
**Projeto:** `Sysutils_proj`  
**Alvos:** `PC-A (Amaranth)` e `PC-B (Bluebaby)` via Tailscale / SMB  

---

## 1. Requisição e Diagnóstico Estruturado (W5+2H / Os Porquês)

* **O quê (What):** Automação do handshake de rede, autorização e mapeamento de pastas compartilhadas (SMB/UNC ou Unidade `Z:`) entre as duas máquinas para acesso nativo e transparente via Windows Explorer (copiar e colar direto).
* **Onde (Where):** `syncdiag/core/network_connect.py` (novo módulo de persistência/conexão de rede) e expansão da CLI em `syncdiag/cli/commands.py`.
* **Quem (Who):** Usuário desenvolvedor operando entre `Amaranth` e `Bluebaby`.
* **Quando (When):** Acesso sob demanda ou montagem persistente na inicialização.
* **Quanto (How Much):** Mapeamento leve, sem overhead contínuo, testagem de socket TCP (< 1.5s de timeout) antes de qualquer travamento de I/O do Windows.
* **Por quê (Why):** Conexões manuais via SMB no Windows falham com frequência por 4 causas técnicas reais:
  1. **Falha de Resolução NetBIOS:** O comando `net view` atual em `syncdiag/core/discovery.py` depende de *Computer Browser/NetBIOS*, protocolos obsoletos que **não trafegam na malha virtual do Tailscale**.
  2. **Firewall no perfil Público do Tailscale:** O Windows frequentemente rotula o adaptador do Tailscale como rede "Pública", bloqueando a porta SMB (`TCP 445`) por padrão.
  3. **Autenticação e Restrição de Guest:** O Windows 11 bloqueia logins SMB anônimos/convidados por padrão (`RequireInsecureGuestLogon=0`), exigindo passagem explícita de usuário e senha ou cache no Windows Credential Manager.
  4. **Timeout do Windows Explorer:** Tentar acessar um UNC inexistente ou bloqueado congela a interface gráfica por 30 a 60 segundos.
* **Origem (Origin):** Falta de uma camada de autenticação rápida (`cmdkey` / `net use`) associada à ausência de resolução dos IPs CGNAT do Tailscale (`100.x.y.z`).
* **Consequências (Impact):** Frustração, perda de produtividade com cópias manuais e inviabilidade de automações robocopy sem montagem prévia.

---

## 2. Planos de Execução (ProDeNov 1.2.1)

* **Plano A (Principal - Mapeamento Direto com Verificação de Porta):**
  - Testa conectividade de socket na porta 445 (SMB) usando o IP Tailscale ou hostname MagicDNS com timeout estrito de 2 segundos.
  - Registra credenciais no gerenciador de credenciais do Windows via `cmdkey`.
  - Mapeia unidade de rede (ex.: `Z:`) ou link UNC persistente via `net use` com `/persistent:yes`.
  - Abre a pasta mapeada diretamente no Windows Explorer.

* **Plano B (Alternativo - Fallback Sem Letra de Unidade):**
  - Se todas as letras de drive estiverem ocupadas ou se o usuário não quiser criar uma unidade de disco virtual, cria um atalho persistente em `shell:links` / `Network Shortcuts` apontando diretamente para `\\<IP_TAILSCALE>\<SHARE_NAME>` e abre o Explorer com o caminho UNC já autenticado.

* **Plano C (Contingência / Diagnóstico Forense):**
  - Caso a porta 445 esteja inacessível:
    1. Verifica se o serviço do Tailscale está rodando localmente (`tailscale status`).
    2. Valida se o Firewall do Windows está bloqueando porta 445 na interface Tailscale e sugere a regra do PowerShell para liberação (`New-NetFirewallRule`).

---

## 3. Checklist de Implementação & Roteiro (RIT)

- [ ] **Passo 1:** Criar `syncdiag/core/network_connect.py` (Orquestrador de socket, credenciais e montagem SMB).
- [ ] **Passo 2:** Ajustar `syncdiag/core/discovery.py` para consultar IPs do Tailscale via CLI do próprio Tailscale em vez de depender exclusivamente do `net view`.
- [ ] **Passo 3:** Adicionar subcomandos `connect`, `disconnect` e `diag` no grupo `share` do `syncdiag/cli/commands.py`.
- [ ] **Passo 4:** Validação e salvaguarda com `--dry-run` para prever comandos de rede antes de executá-los.

---

## 5. Como Operar no Dia a Dia

1. **Ver as máquinas disponíveis via Tailscale:**
   ```bash
   sysutils share peers
   ```
2. **Conectar e mapear a pasta compartilhada de uma máquina na outra:**
   ```bash
   # Exemplo conectando na Bluebaby mapeando a pasta 'A20251122' para Z:
   sysutils share connect 100.x.y.z A20251122 --user NomeUsuario --password Senha
   ```
   *O Windows Explorer abrirá imediatamente a unidade `Z:` montada, permitindo arrastar, copiar e colar arquivos de forma nativa.*

3. **Desconectar quando terminar:**
   ```bash
   sysutils share disconnect Z:
   ```

## 6. Nota Técnica de Salvaguarda (Firewall do Windows)
Se o `probe_smb_port` acusar falha de conexão na porta 445 mesmo com o Tailscale ativo, execute este comando uma única vez no PowerShell (como Administrador) no PC que está hospedando a pasta:
```powershell
New-NetFirewallRule -DisplayName "SMB Tailscale Libera" -Direction Inbound -LocalPort 445 -Protocol TCP -Action Allow
```
