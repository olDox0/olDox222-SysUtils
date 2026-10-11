# energy_sys/core/process_impact.py
from __future__ import annotations
import time
import psutil
from collections import defaultdict
from typing import List, Dict

# Processos que representam tempo ocioso ou infraestrutura interna do kernel
IGNORED_SYSTEM_PROCS = {
    "system idle process", "idle", "system", "registry"
}

def get_top_energy_consumers(limit: int = 8, instant_watts: float = 10.0, aggregate: bool = True) -> List[Dict]:
    """Ranqueia processos com filtro de ociosidade e normalização multi-core."""
    cpu_cores = psutil.cpu_count(logical=True) or 1
    tracked_procs = {}

    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            name_low = (p.info['name'] or '').lower()
            if name_low in IGNORED_SYSTEM_PROCS:
                continue
            p.cpu_percent(None)
            tracked_procs[p.pid] = p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.3)

    if not aggregate:
        procs = []
        for pid, p in tracked_procs.items():
            try:
                raw_cpu = p.cpu_percent(None)
                # Normaliza pelo número de núcleos (0% a 100% da capacidade total da máquina)
                normalized_cpu = raw_cpu / cpu_cores
                if normalized_cpu > 0.1:
                    mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1)
                    attributed_watts = round((normalized_cpu / 100.0) * instant_watts, 2)
                    procs.append({
                        "pid": pid,
                        "name": p.info['name'],
                        "cpu_percent": round(normalized_cpu, 1),
                        "memory_mb": mem_mb,
                        "estimated_watts": attributed_watts,
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return procs[:limit]

    # Visão Agrupada por Família de Aplicativos
    family_stats = defaultdict(lambda: {"cpu_sum": 0.0, "mem_sum": 0.0, "count": 0})
    for pid, p in tracked_procs.items():
        try:
            raw_cpu = p.cpu_percent(None)
            normalized_cpu = raw_cpu / cpu_cores
            if normalized_cpu > 0.1:
                name = p.info['name'].lower()
                mem = p.info['memory_info'].rss / (1024 * 1024)
                family_stats[name]["cpu_sum"] += normalized_cpu
                family_stats[name]["mem_sum"] += mem
                family_stats[name]["count"] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    aggregated_list = []
    for name, data in family_stats.items():
        attributed_watts = round((data["cpu_sum"] / 100.0) * instant_watts, 2)
        aggregated_list.append({
            "name": name,
            "instances": data["count"],
            "cpu_percent": round(data["cpu_sum"], 1),
            "memory_mb": round(data["mem_sum"], 1),
            "estimated_watts": attributed_watts,
        })

    aggregated_list.sort(key=lambda x: x['cpu_percent'], reverse=True)
    return aggregated_list[:limit]
