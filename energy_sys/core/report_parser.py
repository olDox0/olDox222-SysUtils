# energy_sys/core/report_parser.py
from __future__ import annotations
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

KNOWN_CULPRITS = {
    "CopilotRuntimeBroker.exe": "Assistente Copilot (IA)",
    "ai_runtime.exe": "Runtime de IA do Windows",
    "esif_uf.exe": "Intel Innovation Platform Framework (IPF)",
    "WavesSysSvc": "Waves Audio Services",
    "nvlddmkm.sys": "Driver de vídeo NVIDIA",
    "igfxEM.exe": "Intel Graphics Command Center",
    "SearchIndexer.exe": "Windows Search Indexer",
    "OneDrive.exe": "Microsoft OneDrive",
    "Teams.exe": "Microsoft Teams",
    "msedge.exe": "Microsoft Edge (background)",
    "MsMpEng.exe": "Microsoft Defender Antivirus",
    "backgroundTaskHost.exe": "Background Task Host",
    "RuntimeBroker.exe": "Runtime Broker",
    "dwm.exe": "Desktop Window Manager",
}

def _find_json_arrays(raw: str) -> List[Any]:
    """
    Encontra listas JSON balanceadas no texto bruto.
    Procura por '[' ou '{' e faz balanceamento de brackets, tentando json.loads.
    """
    results = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch in ("[", "{"):
            # Tenta um balanceamento rápido
            open_ch = ch
            close_ch = "]" if ch == "[" else "}"
            depth = 0
            in_string = False
            escape = False
            end = None
            j = i
            # Limite de segurança: 10MB
            limit = min(n, i + 10_000_000)
            while j < limit:
                c = raw[j]
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_string = not in_string
                elif not in_string:
                    if c == open_ch:
                        depth += 1
                    elif c == close_ch:
                        depth -= 1
                        if depth == 0:
                            end = j + 1
                            break
                j += 1
            if end is not None:
                candidate = raw[i:end]
                # Só tenta parsear se for razoavelmente grande
                if len(candidate) > 100:
                    try:
                        parsed = json.loads(candidate)
                        results.append(parsed)
                        # Pula para depois do JSON
                        i = end
                        continue
                    except (json.JSONDecodeError, ValueError):
                        pass
        i += 1
    return results

def _walk_for_offenders(obj: Any, path: str = "") -> List[Dict]:
    """
    Navega recursivamente em JSON procurando listas de objetos com chaves
    típicas de 'top offenders' (Name + ActiveTimePercent ou DrainRate).
    """
    results = []
    if isinstance(obj, list):
        # Verifica se esta lista é uma lista de offenders
        if obj and isinstance(obj[0], dict):
            sample = obj[0]
            # Chaves típicas do sleepstudy
            has_name = any(k in sample for k in ("Name", "FriendlyName", "ProcessName"))
            has_percent = any(k in sample for k in ("ActiveTimePercent", "Percent", "DrainPercent", "Sw", "Hw"))
            if has_name and has_percent and len(obj) >= 1:
                for item in obj:
                    name = item.get("Name") or item.get("FriendlyName") or item.get("ProcessName") or "Unknown"
                    # Tenta pegar a porcentagem mais relevante
                    percent = None
                    percent_label = ""
                    for key in ("ActiveTimePercent", "DrainPercent", "Percent", "ActiveTime"):
                        if key in item and isinstance(item[key], (int, float)):
                            percent = float(item[key])
                            percent_label = key
                            break
                    # Sw / Hw são proporções (0-1), multiplica por 100
                    if percent is None:
                        if "Sw" in item and isinstance(item["Sw"], (int, float)):
                            percent = float(item["Sw"]) * 100
                            percent_label = "Sw (Software)"
                        elif "Hw" in item and isinstance(item["Hw"], (int, float)):
                            percent = float(item["Hw"]) * 100
                            percent_label = "Hw (Hardware)"
                    
                    if percent is not None and percent > 0:
                        type_name = item.get("Type") or item.get("Component") or "Component"
                        results.append({
                            "name": str(name),
                            "type": str(type_name),
                            "percent": round(percent, 2),
                            "percent_str": f"{percent:.2f}%",
                            "label": percent_label,
                            "is_known_culprit": any(c.lower() in str(name).lower() for c in KNOWN_CULPRITS),
                        })
        # Recursão nos itens da lista
        for item in obj:
            results.extend(_walk_for_offenders(item, path))
    elif isinstance(obj, dict):
        # Recursão nos valores
        for k, v in obj.items():
            results.extend(_walk_for_offenders(v, f"{path}.{k}"))
    return results

def parse_powercfg_report(html_path: Path) -> List[Dict]:
    """
    Lê o relatório HTML do powercfg (sleepstudy) extraindo o JSON embutido.
    """
    if not html_path.exists():
        return []

    raw_html = html_path.read_text(encoding="utf-8", errors="ignore")
    
    # 1. Extrai todos os JSON arrays/objects do HTML
    json_blobs = _find_json_arrays(raw_html)
    
    # 2. Navega em cada blob procurando listas de offenders
    all_results = []
    for blob in json_blobs:
        all_results.extend(_walk_for_offenders(blob))
    
    # 3. Se não achou nos JSONs, tenta os <script> tags específicos
    if not all_results:
        # Tenta extrair var/let/const NAME = <json>;
        for match in re.finditer(r'(?:var|let|const)\s+\w+\s*=\s*(\[[\s\S]*?\]);', raw_html):
            try:
                parsed = json.loads(match.group(1))
                all_results.extend(_walk_for_offenders(parsed))
            except json.JSONDecodeError:
                continue
    
    # 4. Ordena e deduplica por nome, mantendo o maior percent
    by_name: Dict[str, Dict] = {}
    for r in all_results:
        # Limpa códigos ANSI que possam ter vazado do HTML
        name_clean = re.sub(r'\x1b\[[0-9;]*m', '', r["name"]).strip()
        
        # Mapeia o enum de Type do Windows (1=Hardware, 2=App, 7=Driver)
        t_raw = str(r.get("type", ""))
        if t_raw == "1":
            t_clean = "Hardware"
        elif t_raw == "2":
            t_clean = "App"
        elif t_raw == "7":
            t_clean = "Driver/Sys"
        else:
            t_clean = t_raw

        if name_clean not in by_name or r["percent"] > by_name[name_clean]["percent"]:
            r["name"] = name_clean
            r["type"] = t_clean
            by_name[name_clean] = r
    
    sorted_results = sorted(by_name.values(), key=lambda x: x["percent"], reverse=True)
    return sorted_results[:25]

def find_sleep_blockers() -> List[str]:
    """Executa powercfg /requests e extrai o que está impedindo o sono."""
    try:
        res = subprocess.run(["powercfg", "/requests"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
        blockers = []
        current_section = ""
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.endswith(":"):
                current_section = line
            elif "[" in line and "]" in line:
                blockers.append(f"{current_section} -> {line}")
        return blockers
    except Exception:
        return []
