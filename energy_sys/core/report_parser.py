# energy_sys/core/report_parser.py
from __future__ import annotations
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

from bs4 import BeautifulSoup

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
        if obj and isinstance(obj[0], dict):
            sample = obj[0]
            has_name = any(k in sample for k in ("Name", "FriendlyName", "ProcessName"))
            has_percent = any(k in sample for k in ("ActiveTimePercent", "Percent", "DrainPercent", "Sw", "Hw"))
            
            if has_name and has_percent and len(obj) >= 1:
                for item in obj:
                    name = item.get("Name") or item.get("FriendlyName") or item.get("ProcessName") or "Unknown"
                    
                    # 1. Porcentagem (ActiveTimePercent, Sw, Hw)
                    percent = None
                    for key in ("ActiveTimePercent", "DrainPercent", "Percent"):
                        if key in item and isinstance(item[key], (int, float)):
                            percent = float(item[key])
                            break
                    if percent is None:
                        if "Sw" in item and isinstance(item["Sw"], (int, float)):
                            percent = float(item["Sw"]) * 100
                        elif "Hw" in item and isinstance(item["Hw"], (int, float)):
                            percent = float(item["Hw"]) * 100

                    # 2. Drain Rate (mW)
                    drain_mw = None
                    for key in ("DrainRate", "Drain", "Rate"):
                        if key in item and isinstance(item[key], (int, float)):
                            drain_mw = float(item[key])
                            break
                    
                    # 3. Tempo Ativo (em ms, converte para segundos/minutos)
                    active_time = None
                    for key in ("ActiveTime", "ActiveTimeMs"):
                        if key in item and isinstance(item[key], (int, float)):
                            active_time = float(item[key])
                            break

                    # 4. Tipo (1=Hardware, 2=App, 7=Driver)
                    type_map = {1: "Hardware", 2: "App", 7: "Driver/Sys"}
                    raw_type = item.get("Type") or item.get("Component") or "Component"
                    type_name = type_map.get(raw_type, str(raw_type))

                    if percent is not None and percent > 0:
                        results.append({
                            "name": str(name),
                            "type": type_name,
                            "percent": round(percent, 2),
                            "percent_str": f"{percent:.2f}%",
                            "drain_mw": drain_mw,
                            "active_time_s": (active_time / 1000.0) if active_time else None,
                            "is_known_culprit": any(c.lower() in str(name).lower() for c in KNOWN_CULPRITS),
                        })
        for item in obj:
            results.extend(_walk_for_offenders(item, path))
    elif isinstance(obj, dict):
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
        name = r["name"]
        if name not in by_name or r["percent"] > by_name[name]["percent"]:
            by_name[name] = r
            
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

def parse_energy_report(html_path: Path) -> List[Dict]:
    """
    Lê o powercfg /energy e extrai erros/avisos de bloqueio e CPU.
    """
    if not html_path.exists():
        return []
        
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")
        
    results = []
    
    # Procura os blocos de erro e aviso
    for div_class in ["error-log-entry", "warning-log-entry"]:
        for entry in soup.find_all("div", class_=div_class):
            header = entry.find("div", class_="log-entry-header")
            content = entry.find("div", class_="log-entry-description")
            
            if not header or not content:
                continue
                
            title = header.get_text(strip=True)
            desc = content.get_text(strip=True)
            
            # Extrai o nome do processo se existir
            proc_name = "Desconhecido"
            details = entry.find_all("td", class_="detail-name")
            for td in details:
                if "Solicitando processo" in td.get_text():
                    next_td = td.find_next_sibling("td")
                    if next_td:
                        path = next_td.get_text(strip=True)
                        proc_name = path.split("\\")[-1]  # Pega só o .exe
                        break
                        
            severity = "CRITICAL" if div_class == "error-log-entry" else "WARNING"
            
            results.append({
                "severity": severity,
                "title": title,
                "description": desc,
                "process": proc_name
            })
            
    return results
