from __future__ import annotations
import psutil
from typing import List, Dict

# Lista de serviços conhecidos por consumir bateria e que podem ser desativados
# com segurança para a maioria dos usuários.
KNOWN_POWER_HOG_SERVICES = {
    "WSearch": "Windows Search Indexer",
    "BITS": "Background Intelligent Transfer Service",
    "DiagTrack": "Connected User Experiences and Telemetry",
    "PcaSvc": "Program Compatibility Assistant Service",
    "WerSvc": "Windows Error Reporting Service",
    "WpnService": "Windows Push Notifications System Service",
    "SysMain": "SysMain (Superfetch)",
    "MapsBroker": "Downloaded Maps Manager",
    "XblAuthManager": "Xbox Live Auth Manager",
    "XblGameSave": "Xbox Live Game Save",
    "XboxNetApiSvc": "Xbox Live Networking Service",
    "RetailDemo": "Retail Demo Service",
}

def get_running_services() -> List[Dict]:
    """
    Lista serviços do Windows em execução.
    Tolerante a serviços protegidos que causam FileNotFoundError no psutil.
    """
    services = []
    for service in psutil.win_service_iter():
        try:
            name = service.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
            continue

        try:
            status = service.status()
            if status != "running":
                continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
            continue

        try:
            display_name = service.display_name()
        except Exception:
            display_name = name

        try:
            start_type = service.start_type()
        except Exception:
            start_type = "unknown"

        services.append({
            "name": name,
            "display_name": display_name,
            "status": status,
            "start_type": start_type,
        })
    return services

def audit_service_impact() -> List[Dict]:
    """Audita serviços em execução e sinaliza os que são candidatos à desativação."""
    running = get_running_services()
    report = []
    for srv in running:
        srv_name = srv["name"]
        is_known_hog = srv_name in KNOWN_POWER_HOG_SERVICES
        report.append({
            **srv,
            "is_known_power_hog": is_known_hog,
            "recommendation": "Desativar (se não usar a funcionalidade)" if is_known_hog else "Manter",
        })
    # Ordena para colocar os "power hogs" no topo
    report.sort(key=lambda x: x["is_known_power_hog"], reverse=True)
    return report
