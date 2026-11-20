
# energy_sys/core/process_tuner.py
from __future__ import annotations
import psutil
from typing import List, Dict, Tuple
from energy_sys.core import power_strategies

def get_core_indices(core_type: str = "e-cores") -> List[int]:
    """Retorna a lista de índices lógicos dos núcleos (E-Cores ou P-Cores)."""
    total_threads = psutil.cpu_count(logical=True) or 8
    topology = power_strategies.get_hybrid_cpu_topology(total_threads)
    
    target_indices = []
    for idx, label in topology.items():
        if core_type == "e-cores" and "E-Core" in label:
            target_indices.append(idx)
        elif core_type == "p-cores" and "P-Core" in label:
            target_indices.append(idx)
        elif core_type == "all":
            target_indices.append(idx)
            
    # Se a topologia falhar em detectar (retornar "Núcleo Padrão"), 
    # assume que os últimos 50% são E-Cores (heurística para Intel 12th gen)
    if not target_indices and core_type != "all":
        half = total_threads // 2
        target_indices = list(range(half, total_threads)) if core_type == "e-cores" else list(range(0, half))
        
    return target_indices

def pin_process(process_name: str, core_type: str = "e-cores") -> Tuple[bool, str, int]:
    """
    Aplica a afinidade de CPU a todos os processos com o nome informado.
    Retorna (sucesso, mensagem, quantidade_de_processos_afetados).
    """
    cores = get_core_indices(core_type)
    if not cores:
        return False, f"Não foi possível mapear os núcleos para {core_type}.", 0

    affected = 0
    process_name = process_name.lower()
    if not process_name.endswith(".exe"):
        process_name += ".exe"

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == process_name:
                proc.cpu_affinity(cores)
                affected += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue

    if affected == 0:
        return False, f"Nenhum processo '{process_name}' em execução para ser modificado.", 0

    return True, f"Sucesso. Núcleos atribuídos: {cores}", affected
