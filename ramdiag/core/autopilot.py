# ramdiag/core/autopilot.py
import time
import psutil
from ramdiag.core.monitor import trim_memory
from diskdiag.analysis.disk_analysis import _format_size

def run_autopilot(threshold_percent=85, interval=5):
    """
    Monitora a RAM continuamente. 
    Se o uso ultrapassar o threshold, dispara o RAM Trim nativo.
    """
    print(f"[VULCAN] Autopilot ativado (Gatilho: {threshold_percent}% | Check: {interval}s)")
    
    try:
        while True:
            mem = psutil.virtual_memory()
            if mem.percent > threshold_percent:
                before = mem.used
                # Chama a DLL nativa vulcan_ram.dll
                count = trim_memory()
                
                # Aguarda um momento para o Windows processar o trim
                time.sleep(1)
                after = psutil.virtual_memory().used
                saved = before - after
                
                if saved > 0:
                    print(f"  [!] Alerta de RAM ({mem.percent}%): {_format_size(saved)} recuperados em {count} processos.")
                else:
                    print(f"  [i] RAM em {mem.percent}%, mas o Working Set já está otimizado.")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[VULCAN] Autopilot desativado.")