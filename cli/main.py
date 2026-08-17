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
import json
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
    """Orquestrador Zeus: Carrega os submódulos apenas quando invocados.
    Prioridade de resolução:
      1. Comandos locais do projeto (_lazy_map)
      2. Comandos Doxoade portados (port_commands.json)
    Regras de conflito:
      - Se um comando Doxoade tem o mesmo nome de um comando local,
        ele é automaticamente renomeado via alias.
      - priority: "local_first" (padrão) garante que o projeto vence.
    """
    PORT_MANIFEST = Path(".doxoade") / "port_commands.json"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ═══ COMANDOS LOCAIS DO PROJETO (PRIORIDADE MÁXIMA) ═══
        self._lazy_map = {
            'disk':   'diskdiag.cli.commands:cli',
            'ram':    'ramdiag.cli.commands:cli',
            'backup': 'doxbackup.cli.commands:cli',
            'bloat':  'bloatbreaker.cli.commands:cli',
            'win':    'sysdiag.cli.commands:cli',
            'net':    'netdiag.cli.commands:cli',
            'verify': 'doxbackup.core.verify:cli',
        }
        # ═══ COMANDOS DOXOADE PORTADOS (PRIORIDADE SECUNDÁRIA) ═══
        self._ported_map = self._load_ported_commands()

    def _load_ported_commands(self):
        """
        Lê .doxoade/port_commands.json e resolve conflitos de nome.
        
        Formato suportado:
          - Lista simples: ["horus", "flow", "search"]
          - Dicionário com aliases:
            {"backup": {"alias": "doxbackup"}, "horus": {}}
        """
        try:
            if not self.PORT_MANIFEST.exists(): return {}
            data = json.loads(self.PORT_MANIFEST.read_text(encoding="utf-8"))
            raw_commands = data.get("commands", {})
            priority = data.get("priority", "local_first")
            resolved = {}
            # ── Formato antigo: lista simples ──
            if isinstance(raw_commands, list):
                for cmd_name in raw_commands:
                    resolved[cmd_name] = {"doxoade_name": cmd_name}
            # ── Formato novo: dicionário com metadados ──
            elif isinstance(raw_commands, dict):
                for cmd_name, meta in raw_commands.items():
                    if not isinstance(meta, dict):
                        meta = {}
                    resolved[cmd_name] = {"doxoade_name": cmd_name, **meta}
            # ── Resolver conflitos: local_first ──
            if priority == "local_first":
                final = {}
                for cmd_name, meta in resolved.items():
                    alias = meta.get("alias", cmd_name)
                    # Se o alias conflita com comando local, prefixar com "dox"
                    if alias in self._lazy_map:
                        alias = f"dox{cmd_name}"
                        meta["alias"] = alias
                        meta["reason"] = f"Conflito com comando local '{cmd_name}'"
                    final[alias] = meta
                return final
            return resolved
        except Exception:
            return {}

    def _validate_syntax(self, module_path: str) -> bool:
        """
        Valida a sintaxe de um módulo antes de importá-lo.
        Retorna True se OK, False se houver erro de sintaxe.
        """
        import py_compile
        import tempfile
        
        # Converte 'doxbackup.cli.commands:cli' para caminho de arquivo
        if ':' in module_path:
            module_path = module_path.split(':')[0]
        
        # Converte 'doxbackup.cli.commands' para 'doxbackup/cli/commands.py'
        file_path = module_path.replace('.', '/') + '.py'
        
        if not os.path.exists(file_path):
            return True  # Não existe, não é erro de sintaxe
        
        try:
            py_compile.compile(file_path, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            # Extrai informações do erro
            error_msg = str(e)
            line_num = "desconhecida"
            
            # Tenta extrair número da linha
            import re
            match = re.search(r'line (\d+)', error_msg)
            if match:
                line_num = match.group(1)
            
            # Mostra diagnóstico forense
            print(f"\n\x1b[41;1m 🔥 ERRO DE SINTAXE DETECTADO \x1b[0m")
            print(f"\x1b[1;31m  ■ Arquivo: \x1b[0m{file_path}")
            print(f"\x1b[1;31m  ■ Linha:   \x1b[0m{line_num}")
            print(f"\x1b[1;31m  ■ Erro:    \x1b[0m{error_msg.split('(')[0].strip()}")
            print(f"\n\x1b[33m  💡 Dica: Use 'doxoade check -fp {file_path}' para diagnóstico completo.\x1b[0m")
            print(f"\x1b[33m  💡 Ou abra no Notepad++: notepad++ -n{line_num} {file_path}\x1b[0m\n")
            
            return False

    def list_commands(self, ctx):
        """Lista todos os comandos: locais + portados (sem duplicatas)."""
        all_names = set(self._lazy_map.keys()) | set(self._ported_map.keys())
        return sorted(all_names)

    def get_command(self, ctx, name):
        """
        Resolução de comandos com prioridade:
          1. Comando local do projeto
          2. Comando Doxoade portado (via alias)
        """
        # ── PRIORIDADE 1: Comando local ──
        if name in self._lazy_map:
            module_path = self._lazy_map[name]

            # Valida sintaxe antes de importar
            if not self._validate_syntax(module_path):
                @click.command(name=name)
                def syntax_error_placeholder():
                    click.secho(f"[ERRO] Comando '{name}' não pode ser carregado devido a erro de sintaxe.", fg="red", bold=True)
                    click.secho("Veja o diagnóstico acima para detalhes.", fg="yellow")
                return syntax_error_placeholder

            # ✅ CORREÇÃO: Split correto do module_path
            module_path, attr_name = self._lazy_map[name].split(':')
            
            try:
                mod = import_module(module_path)
                return getattr(mod, attr_name)
            except Exception as e:
                err_msg = traceback.format_exc()
                click.secho(f"\n[FATAL] Erro ao carregar comando '{name}': {e}err: \n {err_msg}", fg='red')
                return None

        # ── PRIORIDADE 2: Comando Doxoade portado ──
        if name in self._ported_map:
            meta = self._ported_map[name]
            doxoade_cmd_name = meta.get("doxoade_name", name)
            try:
                from utils.doxoade_bridge import load_command
                return load_command(doxoade_cmd_name)
            except Exception as e:
                err_msg = traceback.format_exc()
                click.secho(
                    f"\n[FATAL] Erro ao carregar comando Doxoade '{doxoade_cmd_name}' "
                    f"(alias: '{name}'): {e}\n err: \n {err_msg}", fg='red'
                )
                return None
        return None

@click.group(cls=SysUtilsLazyGroup)
def cli():
    """SysUtils — Suite de Diagnóstico e Otimização de Sistema (Chief-Gold)."""
    pass

MAIN_PORT_IMPORT_OLD = """import sys
import os
import hashlib"""

MAIN_PORT_IMPORT_NEW = """import sys
import os
import json
import hashlib"""


MAIN_PORT_INIT_OLD = """        self._lazy_map = {
            'disk':   'diskdiag.cli.commands:cli',
            'ram':    'ramdiag.cli.commands:cli',
            'backup': 'doxbackup.cli.commands:cli',
            'bloat':  'bloatbreaker.cli.commands:cli',
            'win':    'sysdiag.cli.commands:cli',
            'net':    'netdiag.cli.commands:cli',
        }"""

MAIN_PORT_INIT_NEW = """        self._lazy_map = {
            'disk':   'diskdiag.cli.commands:cli',
            'ram':    'ramdiag.cli.commands:cli',
            'backup': 'doxbackup.cli.commands:cli',
            'bloat':  'bloatbreaker.cli.commands:cli',
            'win':    'sysdiag.cli.commands:cli',
            'net':    'netdiag.cli.commands:cli',
        }

        self._ported_commands = self._load_ported_commands()"""


MAIN_PORT_LIST_OLD = """    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())"""

MAIN_PORT_LIST_NEW = """    PORT_MANIFEST = Path(".doxoade") / "port_commands.json"

    def _load_ported_commands(self):
        try:
            if self.PORT_MANIFEST.exists():
                data = json.loads(self.PORT_MANIFEST.read_text(encoding="utf-8"))
                return set(data.get("commands", []))
        except Exception:
            pass

        return set()

    def list_commands(self, ctx):
        return sorted(set(self._lazy_map.keys()) | self._ported_commands)"""


MAIN_PORT_GET_OLD = """    def get_command(self, ctx, name):
        if name not in self._lazy_map:
            return None
        module_path, attr_name = self._lazy_map[name].split(':')
        try:
            mod = import_module(module_path)
            return getattr(mod, attr_name)
        except Exception as e:
            click.secho(f"\\n[FATAL] Erro ao carregar comando '{name}': {e}", fg='red')
            return None"""

MAIN_PORT_GET_NEW = """    def get_command(self, ctx, name):
        if name in self._ported_commands:
            try:
                from utils.doxoade_bridge import load_command
                return load_command(name)
            except Exception as e:
                click.secho(f"\\n[FATAL] Erro ao carregar comando portado '{name}': {e}", fg='red')
                return None

        if name not in self._lazy_map:
            return None

        module_path, attr_name = self._lazy_map[name].split(':')

        try:
            mod = import_module(module_path)
            return getattr(mod, attr_name)
        except Exception as e:
            click.secho(f"\\n[FATAL] Erro ao carregar comando '{name}': {e}", fg='red')
            return None"""


def _patch_main_for_ported_commands(root: Path, apply_changes: bool = False):
    main_path = root / "cli" / "main.py"

    if not main_path.exists():
        click.secho("[AVISO] cli/main.py não encontrado.", fg="yellow")
        return False

    original = _read_text_safe(main_path)

    if "_load_ported_commands" in original:
        click.secho("[OK] cli/main.py já suporta comandos portados.", fg="green")
        return True

    replacements = [
        (MAIN_PORT_IMPORT_OLD, MAIN_PORT_IMPORT_NEW),
        (MAIN_PORT_INIT_OLD, MAIN_PORT_INIT_NEW),
        (MAIN_PORT_LIST_OLD, MAIN_PORT_LIST_NEW),
        (MAIN_PORT_GET_OLD, MAIN_PORT_GET_NEW),
    ]

    content = original
    failed = []

    for old, new in replacements:
        if old not in content:
            failed.append(old.splitlines()[0])
            continue

        content = content.replace(old, new, 1)

    if failed:
        click.secho("[FALHA] cli/main.py não bate com o padrão esperado.", fg="red")
        click.echo("Padrões não encontrados:")

        for f in failed:
            click.echo(f"  - {f}")

        click.echo("Aplicação automática abortada. Use o snippet manual.")
        return False

    if not apply_changes:
        click.secho("[DRY] cli/main.py seria patcheado.", fg="yellow")
        return True

    backup_path = main_path.with_name("main.py.dox_port.bak")
    backup_path.write_text(original, encoding="utf-8")

    main_path.write_text(content, encoding="utf-8")
    click.secho("  [APPLIED] cli/main.py", fg="green")
    click.echo(f"Backup: {backup_path}")

    return True

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