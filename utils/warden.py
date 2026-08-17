# doxoade/tools/aegis/warden.py
# [DOX-UNUSED] import os
# [DOX-UNUSED] import sys
import click

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

def parse_size(size_str):
    if not size_str: return None
    size_str = str(size_str).lower()
    units = {'kb': 1024, 'mb': 1024**2, 'gb': 1024**3}
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                return int(size_str.replace(unit, '').strip()) * multiplier
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] parse_size: {e}")
                return None
    try:
        return int(size_str)
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] parse_size: {e}")
        return None

def apply_resource_limits(limits: dict):
    """Aplica restrições de hardware. No Windows, emite aviso e prossegue."""
    
    if not HAS_RESOURCE:
        # Se houver qualquer limite definido, avisa que no Windows não terá efeito real
        if limits and any(v is not None for v in limits.values()):
            click.secho("⚠️  [WARDEN] Limites de recursos (-pl, -rl, -dl) ignorados: módulo 'resource' indisponível no Windows.", fg='yellow')
        return

    # --- Lógica para Linux / Unix ---
    
    # 1. Limite de Memória (RAM)
    ram_bytes = parse_size(limits.get('ram'))
    if ram_bytes:
        resource.setrlimit(resource.RLIMIT_AS, (ram_bytes, ram_bytes))

    # 2. Limite de Disco (Escrita)
    disk_bytes = parse_size(limits.get('disk'))
    if disk_bytes:
        resource.setrlimit(resource.RLIMIT_FSIZE, (disk_bytes, disk_bytes))

    # 3. Limite de CPU (Tempo de processo)
    cpu_limit = limits.get('cpu')
    if cpu_limit:
        # No Linux, limitamos o tempo total de CPU em segundos para evitar loops infinitos
        soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
        resource.setrlimit(resource.RLIMIT_CPU, (60, hard))
