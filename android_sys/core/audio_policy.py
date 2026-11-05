# -*- coding: utf-8 -*-
# android_sys/core/audio_policy.py
"""
Hera / Hermes: Política de Foco de Áudio e Paralelismo de Reprodução.

Responsável por:
  1. Resolver o modo de áudio configurado (exclusive | duck | mix).
  2. Encapsular comandos 'appops set <pkg> TAKE_AUDIO_FOCUS ignore|allow'
     via ADB, para permitir múltiplas fontes de áudio simultâneas.
  3. Persistir o estado em data/android_config.json (chave "audio").

REGRA EMPÍRICA (testada no Galaxy A22 / One UI Core / Android 13):
  - Apps que TOLERAM TAKE_AUDIO_FOCUS=ignore (continuam a tocar):
      VLC (confirmado), Spotify/YouTube Music (prováveis).
  - Apps que NÃO toleram (param ao receber negação de foco):
      Vivaldi, Firefox, navegadores em geral.
  Ao aplicar 'ignore', o SysUtils avisa se o pacote não está na lista segura.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from android_sys.core import adb_manager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "data" / "android_config.json"

AUDIO_MODES = ("exclusive", "duck", "mix")
APPOP_KEY = "TAKE_AUDIO_FOCUS"

# Pacotes CONFIRMADOS como seguros para 'ignore' (continuam a tocar)
KNOWN_IGNORE_SAFE: Tuple[str, ...] = (
    "org.videolan.vlc",
)

# Pacotes PROVÁVEIS (relatos de projetos similares, mas não testados aqui)
KNOWN_IGNORE_SUSPECTED: Tuple[str, ...] = (
    "com.spotify.music",
    "com.google.android.apps.youtube.music",
)


# ─────────────────────────────────────────────────────────────────────
# Configuração (leitura/escrita em android_config.json)
# ─────────────────────────────────────────────────────────────────────

def load_audio_config() -> Dict:
    """Lê a secção 'audio' do android_config.json (ou devolve defaults)."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            audio = data.get("audio", {})
            if isinstance(audio, dict):
                return {
                    "mode": audio.get("mode", "mix"),
                    "packages": list(audio.get("packages", [])),
                }
        except Exception:
            pass
    return {"mode": "mix", "packages": []}


def save_audio_config(mode: str, packages: List[str]) -> Tuple[bool, str]:
    """Grava mode + lista de pacotes em data/android_config.json."""
    if mode not in AUDIO_MODES:
        return False, f"Modo inválido: {mode}. Use um de {AUDIO_MODES}."
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: Dict = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["audio"] = {"mode": mode, "packages": list(packages)}
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, f"Config de áudio salva (mode={mode}, {len(packages)} pacote(s))."
    except Exception as e:
        return False, f"Falha ao gravar config: {e}"


def resolve_audio_mode() -> str:
    """Retorna o modo efetivo (fallback 'mix')."""
    return load_audio_config().get("mode", "mix")


def is_ignore_safe(package: str) -> Optional[str]:
    """
    Classifica um pacote para 'ignore':
      'safe'      -> confirmado (VLC)
      'suspected' -> provável (Spotify, YT Music)
      None        -> não recomendado (browsers, etc.)
    """
    if package in KNOWN_IGNORE_SAFE:
        return "safe"
    if package in KNOWN_IGNORE_SUSPECTED:
        return "suspected"
    return None


# ─────────────────────────────────────────────────────────────────────
# Geração de comandos appops
# ─────────────────────────────────────────────────────────────────────

def build_appops_commands(
    packages: List[str],
    mode: str = "mix",
) -> List[List[str]]:
    """
    Gera a lista de argumentos ADB para aplicar o AppOp de foco.

    mode 'mix'  -> TAKE_AUDIO_FOCUS ignore  (libera paralelismo)
    mode 'duck' -> TAKE_AUDIO_FOCUS ignore  (idêntico no AppOp; duck é via AudioFocusRequest)
    mode 'exclusive' -> TAKE_AUDIO_FOCUS allow (restaura comportamento padrão)
    """
    target_value = "allow" if mode == "exclusive" else "ignore"
    return [
        ["shell", "appops", "set", pkg, APPOP_KEY, target_value]
        for pkg in packages
    ]


# ─────────────────────────────────────────────────────────────────────
# Aplicação e restauração
# ─────────────────────────────────────────────────────────────────────

def _get_target_device() -> Optional[str]:
    """Retorna o primeiro device conectado, ou None."""
    devs = adb_manager.get_connected_devices()
    return devs[0] if devs else None


def apply_audio_policy(
    packages: List[str],
    mode: str,
    dry_run: bool = True,
    safe_only: bool = False,
    restart: bool = False,
) -> Tuple[bool, str, List[str]]:
    """
    Executa (ou simula) a aplicação da política de áudio.

    safe_only=True: recusa pacotes fora de KNOWN_IGNORE_SAFE/SUSPECTED (só em 'mix'/'duck').
    restart=True:   faz 'am force-stop' nos pacotes após aplicar (só em '--apply').
    """
    logs: List[str] = []
    if mode not in AUDIO_MODES:
        return False, f"Modo inválido: {mode}.", logs
    if not packages:
        return False, "Nenhum pacote fornecido.", logs

    target_value = "allow" if mode == "exclusive" else "ignore"
    logs.append(f"Modo: {mode} -> TAKE_AUDIO_FOCUS={target_value}")
    logs.append(f"Pacotes: {', '.join(packages)}")

    # Filtro safe_only (só para ignore)
    if safe_only and target_value == "ignore":
        unsafe = [p for p in packages if is_ignore_safe(p) is None]
        if unsafe:
            return False, (
                f"Pacotes fora da lista segura (recusados por --safe-only): "
                f"{', '.join(unsafe)}. Use 'audio known' para ver a lista."
            ), logs
        for p in packages:
            kind = is_ignore_safe(p)
            if kind == "suspected":
                logs.append(f"  ⚠ {p}: provável (não confirmado)")

    if dry_run:
        for pkg in packages:
            logs.append(f"  [DRY] adb shell appops set {pkg} {APPOP_KEY} {target_value}")
        if restart:
            logs.append(f"  [DRY] adb shell am force-stop <pkg> (após apply)")
        return True, f"Simulação OK ({len(packages)} pacote(s)). Use --apply para efetivar.", logs

    device = _get_target_device()
    if not device:
        return False, "Nenhum dispositivo conectado. Use 'sysutils android connect'.", logs

    logs.append(f"Dispositivo: {device}")
    failed: List[str] = []
    for pkg in packages:
        ok, out = adb_manager.set_appop(device, pkg, APPOP_KEY, target_value)
        if ok:
            logs.append(f"  ✔ {pkg}: {target_value}")
        else:
            failed.append(pkg)
            logs.append(f"  ✘ {pkg}: {out or 'falha desconhecida'}")

    if failed:
        return False, f"{len(failed)}/{len(packages)} pacote(s) falharam: {', '.join(failed)}", logs

    ok_cfg, msg_cfg = save_audio_config(mode, packages)
    logs.append(f"  {msg_cfg}")

    # Restart (force-stop) para forçar releitura do appops
    if restart:
        logs.append("[*] Reiniciando apps (force-stop)...")
        for pkg in packages:
            res = adb_manager.run_adb(["-s", device, "shell", "am", "force-stop", pkg])
            if res.returncode == 0:
                logs.append(f"  ↻ {pkg}: parado (reabra para efeito)")
            else:
                logs.append(f"  ⚠ {pkg}: force-stop falhou")

    return True, f"Política aplicada em {len(packages)} pacote(s)." + (
        " Apps reiniciados." if restart else " Reinicie os apps para efeito."
    ), logs


def restore_audio_policy(
    packages: List[str],
) -> Tuple[bool, str, List[str]]:
    """Reverte todos os pacotes para TAKE_AUDIO_FOCUS allow."""
    logs: List[str] = []
    if not packages:
        return False, "Nenhum pacote fornecido.", logs

    device = _get_target_device()
    if not device:
        return False, "Nenhum dispositivo conectado.", logs

    logs.append(f"Dispositivo: {device}")
    failed: List[str] = []
    for pkg in packages:
        ok, out = adb_manager.set_appop(device, pkg, APPOP_KEY, "allow")
        if ok:
            logs.append(f"  ✔ {pkg}: allow")
        else:
            failed.append(pkg)
            logs.append(f"  ✘ {pkg}: {out or 'falha desconhecida'}")

    if failed:
        return False, f"{len(failed)}/{len(packages)} falharam: {', '.join(failed)}", logs
    return True, f"Foco restaurado em {len(packages)} pacote(s).", logs


# ─────────────────────────────────────────────────────────────────────
# AudioProbe (dumpsys audio parsing)
# ─────────────────────────────────────────────────────────────────────

def list_active_focus_holders() -> List[Dict]:
    """
    (AudioProbe) Parseia 'dumpsys audio' e devolve a pilha de foco atual.
    Estrutura: [{"package": str, "gain": str, "state": str}, ...]
    """
    device = _get_target_device()
    if not device:
        return []
    ok, raw = adb_manager.dumpsys_audio(device)
    if not ok:
        return []

    holders: List[Dict] = []
    in_focus_section = False
    current: Dict = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if "Audio Focus stack entries" in line or "Audio Focus Stack" in line:
            in_focus_section = True
            continue
        if in_focus_section and not stripped:
            if current:
                holders.append(current)
                current = {}
            continue
        if not in_focus_section:
            continue

        m_pkg = re.search(r"pack[:\s]+([a-zA-Z0-9_.]+)", line)
        m_gain = re.search(r"gain[:\s]+([A-Z_]+)", line)
        m_state = re.search(r"state[:\s]+([A-Z_]+)", line)
        if m_pkg:
            if current and current.get("package"):
                holders.append(current)
                current = {}
            current["package"] = m_pkg.group(1)
        if m_gain:
            current["gain"] = m_gain.group(1)
        if m_state:
            current["state"] = m_state.group(1)

    if current:
        holders.append(current)
    return holders


def format_probe_report(holders: List[Dict]) -> str:
    """Formata o resultado de list_active_focus_holders para o terminal."""
    if not holders:
        return "  (nenhum foco de áudio ativo, ou dispositivo não conectado)"
    lines = []
    for i, h in enumerate(holders, 1):
        pkg = h.get("package", "?")
        gain = h.get("gain", "?")
        state = h.get("state", "?")
        lines.append(f"  {i}. {pkg}")
        lines.append(f"       gain={gain}  state={state}")
    return "\n".join(lines)
