# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# [VULCAN-SKIP] Proteção contra introspecção Click
# cli/main.py
import sys
import os
import hashlib
from pathlib import Path

# ------ INJEÇÃO DE PATH ------
# Garante que o diretório raiz esteja no topo do sys.path, não importa onde o comando seja chamado
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------------

import click
import traceback
import tempfile
import subprocess
from importlib import import_module

def sync_vital_bricks():
    """Garante que os Bricks do projeto batam com a Versão de Ouro do Acervo."""
    try:
        # ✅ Caminho atualizado para o novo nome do módulo
        from doxoade.core_database import get_db_connection
        import shutil
    except ImportError:
        # Se o Doxoade não estiver instalado, apenas ignora a sincronia silenciosamente
        return
    
    # Mapeamento: {Nome no Acervo: Caminho Local}
    VITALS = {
        'vulcan_dict':   'diskdiag/core/vulcan_dict.py',
        'vulcan_bitmap': 'diskdiag/core/vulcan_bitmap.py'
    }
    
    try:
        conn = get_db_connection()
        for name, local_path in VITALS.items():
            row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name=?", (name,)).fetchone()
            if not row: continue
            
            from doxoade.commands.moduloid_systems.moduloid_acervo import BRICKS_DIR
            source_brick = BRICKS_DIR / row[0]
            
            if not os.path.exists(local_path) or \
               hashlib.md5(source_brick.read_bytes()).hexdigest() != hashlib.md5(open(local_path, 'rb').read()).hexdigest():
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                shutil.copy2(source_brick, local_path)
        conn.close()
    except Exception:
        pass  # Falha na sincronia não deve impedir o uso da ferramenta

class SysUtilsLazyGroup(click.Group):
    """Orquestrador Zeus: Carrega os submódulos apenas quando invocados."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_map = {
            'disk':   'diskdiag.cli.commands:cli',
            'ram':    'ramdiag.cli.commands:cli',
            'backup': 'doxbackup.cli.commands:cli',
            'bloat':  'bloatbreaker.cli.commands:cli',
            'win':    'sysdiag.cli.commands:cli',
            'net':    'netdiag.cli.commands:cli',
        }

    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())

    def get_command(self, ctx, name):
        if name not in self._lazy_map:
            return None
        module_path, attr_name = self._lazy_map[name].split(':')
        try:
            mod = import_module(module_path)
            return getattr(mod, attr_name)
        except Exception as e:
            click.secho(f"\n[FATAL] Erro ao carregar comando '{name}': {e}", fg='red')
            return None

@click.group(cls=SysUtilsLazyGroup)
def cli():
    """SysUtils — Suite de Diagnóstico e Otimização de Sistema (Chief-Gold)."""
    pass

def main():
    sync_vital_bricks()
    try:
        # Injeção de Path para garantir que os módulos locais sejam achados
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            
        if "--no-sync" not in sys.argv:
            try:
                # Invoca o motor de sincronia do doxoade
                from doxoade.commands.macrothon_systems.macrothon_sync import run_sync_logic
                run_sync_logic(os.getcwd())
            except: pass 
        
        cli(obj={})
    except Exception as e:
        # Aciona o Protocolo Lazarus em caso de crash
        err_msg = traceback.format_exc()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')
        
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            subprocess.run([sys.executable, rescue_script, path], check=False)
        finally:
            try: os.remove(path)
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: main\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        sys.exit(1)

if __name__ == '__main__':
    main()