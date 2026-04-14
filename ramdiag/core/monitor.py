# ramdiag/core/monitor.py

import psutil
import time

from datetime   import datetime
from collections import defaultdict

def get_ram_usage():
    """Retorna um resumo global da memória."""
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used,
        "free": mem.free
    }

def get_top_processes(limit=10):
    """Retorna os processos que mais consomem RAM."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            pinfo = proc.info
            # memory_info.rss é a memória física real (Resident Set Size)
            processes.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'],
                'memory': pinfo['memory_info'].rss
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Ordena por consumo de memória
    processes.sort(key=lambda x: x['memory'], reverse=True)
    return processes[:limit]
    
def get_aggregated_usage():
    """Agrupa o consumo de memória por nome de processo."""
    totals = defaultdict(int)
    counts = defaultdict(int)
    
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            name = proc.info['name']
            mem = proc.info['memory_info'].rss
            totals[name] += mem
            counts[name] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    # Converte para uma lista de tuplas e ordena
    summary = []
    for name, total_mem in totals.items():
        summary.append({
            'name': name,
            'total_memory': total_mem,
            'instances': counts[name]
        })
        
    summary.sort(key=lambda x: x['total_memory'], reverse=True)
    return summary

def get_detailed_processes(limit=10):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'ppid', 'memory_info', 'cmdline']):
        try:
            pinfo = proc.info
            # Obtemos o nome do processo pai se possível
            parent_name = "N/A"
            try:
                parent = psutil.Process(pinfo['ppid'])
                parent_name = parent.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Contagem de processos filhos
            children = proc.children()
            
            processes.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'],
                'ppid': pinfo['ppid'],
                'parent_name': parent_name,
                'memory': pinfo['memory_info'].rss,
                'cmdline': " ".join(pinfo['cmdline']) if pinfo['cmdline'] else "Acesso Negado",
                'children_count': len(children)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    processes.sort(key=lambda x: x['memory'], reverse=True)
    return processes[:limit]
