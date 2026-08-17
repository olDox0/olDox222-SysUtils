# -*- coding: utf-8 -*-
# doxoade/doxoade/rescue.py
""" PROTOCOLO LÁZARO v2.2 — Necropsia de Falhas Mode-Aware.
• complete: Relatório forense completo + menu de intervenção.
• direct:   Falha rápida — 1 linha de diagnóstico + LOG BRUTO. Sem menu,
            sem Cena do Crime, sem Cadeia de Envolvimento.
A Cena do Crime aponta para o frame REAL da exceção (intelligence.py:44),
não para o call-site do lazy loader (cli.py:271). """
import os
import subprocess
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from .doxcolors import Fore, Style, Back
except Exception:
    class _NoColor:
        def __getattr__(self, _): return ''
    Fore = _NoColor(); Style = _NoColor()

from .aegis.aegis_utils import restricted_safe_exec

# --- CONSTANTES TÁTICAS (Chief-Gold Standard) ---
C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                         Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                         Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

WIN_SIGNALS = {
  3221225477: ("AccessViolation (0xc0000005)", "Tentativa ilegal de violar a RAM física."),
  3221225481: ("DivideByZero", "Erro aritmético de hardware."),
  3221225621: ("StackOverflow", "A pilha de recursão explodiu."),
  3221226505: ("StackBufferOverrun (0xc0000409)", "A integridade da pilha foi destruída (Stack Smashing).")
}

_CONTRACT_ERRORS = {'KeyError', 'AttributeError', 'IndexError'}

_LAUDOS = {
  'ModuleNotFoundError':('Falha de Suprimentos', 'Módulo inexistente no ambiente.'),
  'FileNotFoundError':  ('Recurso Ausente',      'Arquivo/diretório não localizado.'),
  'IndentationError':   ('Violação de Gramática','Recuo de blocos inconsistente.'),
  'PermissionError':    ('Bloqueio de Aegis',    'Permissão negada pelo sistema.'),
  
  'AttributeError': ('Falha de Contrato',    'Atributo inexistente no objeto.'),
  'SyntaxError':    ('Violação de Gramática','Código possui erro de sintaxe'),
  'ImportError':    ('Falha de Suprimentos', 'Módulo/símbolo não pôde ser importado.'),
  'IndexError':     ('Falha de Contrato',    'Índice fora dos limites garantidos.'),
  'KeyError':       ('Falha de Contrato',    'Chave inexistente em estrutura de dados.'),
}

# ──────────────────────────── AUXILIARES ───────────────────────────

def _collect_fixes_for_crime(info):
    """🛠️ ANÚBIS-LINK: consulta o motor de check p/ a linha do crime (silencioso)."""
    try:
        import contextlib, io as _io
        from doxoade.commands.check_systems.check_io import CheckIO
        from doxoade.commands.check_systems.check_state import CheckState
        from doxoade.commands.check_systems.check_engine import run_audit_engine
        io_ = CheckIO(info['file'])
        state = CheckState(root=io_.project_root, target_path=io_.target_abs, is_full_power=True)
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):  # mantém o Lázaro limpo
            run_audit_engine(state, io_, full_power=True)
        return [f for f in state.findings
                if f.get('line') == info.get('line') and f.get('suggestion_action')]
    except Exception:
        return []

def _fix_workflow(info):
    """🛠️ Dry-Run da correção + aplicação segura (valida com compile antes de salvar)."""
    fixes = _collect_fixes_for_crime(info)
    with open(info['file'], 'r', encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()
    # Candidato extra: correção de contrato (chave errada → chave real)
    ct = info.get('contract') or {}
    if ct.get('hint') and info.get('line'):
        idx = info['line'] - 1
        if idx < len(lines):
            fixes = list(fixes) + [{
                'line': info['line'],
                'suggestion_action': 'FIX_CONTRACT_KEY',
                'suggestion_content': lines[idx].strip().replace(ct['assumed'], ct['hint']),
            }]
    if not fixes:
        print(f"  {Y}⚠ Nenhuma correção automática mapeada para a linha do crime.{RST}")
        return
    for f in fixes:  # --- DRY-RUN ---
        idx = f['line'] - 1
        orig = lines[idx].rstrip('\n') if idx < len(lines) else ''
        indent = orig[:len(orig) - len(orig.lstrip())]          # ← preserva o recuo
        print(f"\n  {C}■ DRY-RUN [{f['suggestion_action']}] {os.path.basename(info['file'])}:{f['line']}{RST}")
        print(f"    {R}- {orig}{RST}")
        print(f"    {G}+ {indent}{f['suggestion_content'].strip()}{RST}")   # ← prévia fiel
    if input(f"\n  {W}Aplicar correções? [y/N]: {RST}").strip().lower() != 'y':
        print(f"  {Y}✔ Dry-run encerrado sem alterações.{RST}")
        return
    for f in fixes:  # --- APLICAÇÃO ---
        idx = f['line'] - 1
        if idx >= len(lines):
            continue
        indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
        lines[idx] = indent + f['suggestion_content'].strip() + '\n'
    new_src = ''.join(lines)
    try:
        compile(new_src, info['file'], 'exec')  # Ma'at: nunca salvar código quebrado
    except SyntaxError as e:
        print(f"  {R}✘ Correção abortada: geraria SyntaxError ({e}).{RST}")
        return
    with open(info['file'], 'w', encoding='utf-8') as fh:
        fh.write(new_src)
    print(f"  {G}✔ Correção aplicada em {os.path.basename(info['file'])}. Ma'at restaurada.{RST}")

def _extract_contract(crime):
    """⚖️ HERA: reconstrói o contrato REAL da fronteira onde o KeyError nasceu.
    Exibe o que a interface oferece vs. o que o código assumiu."""
    if not crime:
        return None
    m = re.search(r"([\w\.]+)\[['\"](.+?)['\"]\]", crime.get('code', ''))
    if not m:
        return None
    target, assumed = m.group(1), m.group(2)
    contract = {'target': target, 'assumed': assumed, 'keys': [], 'hint': None}
    try:
        import ast, difflib
        with open(crime['file'], 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
               and node.lineno <= crime['line'] <= (node.end_lineno or node.lineno):
                if target.endswith('params'):  # contrato Click: args da função
                    contract['keys'] = [a.arg for a in node.args.args if a.arg not in ('self', 'cls', 'ctx')]
                else:                          # contrato de dict: literal atribuído ao alvo
                    var_name = target.split('.')[-1]
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Dict):
                            if any(isinstance(t, ast.Name) and t.id == var_name for t in sub.targets):
                                contract['keys'] = [str(k.value) for k in sub.value.keys if isinstance(k, ast.Constant)]
                break
    except Exception:
        pass
    if contract['keys']:
        close = difflib.get_close_matches(assumed, contract['keys'], n=1, cutoff=0.4)
        contract['hint'] = close[0] if close else None
    return contract

def _direct_report(trace, mined):
    """🏹 DIRECT MODE: mesma estética do complete, porém compacta.
    Header + Causa Raiz + Cena do Crime (snippet) + LOG BRUTO. Sem menu."""
    mined = mined or {}
    crime = mined.get('crime')
    sep = '_' * 110
    evento = hashlib.md5(trace.encode('utf-8', 'ignore')).hexdigest()[:8].upper()
    laudo, _desc = _LAUDOS.get(mined.get('error_type', ''), ('Falha Desconhecida', ''))

    out = sys.stderr
    out.write(f"\n{C}{sep}{RST}\n")
    out.write(f"  {W}🆔 ID EVENTO : {RST}{Y}{evento:<12}{RST} {W}🚪 EXIT CODE : {RST}{Y}1{RST}\n")
    out.write(f"  {C}■ CAUSA RAIZ : {RST}{R}{laudo}{RST} {W}({mined.get('error_type', '?')}: {mined.get('error_msg', '')}){RST}\n")
    if crime:
        out.write(f"  {C}■ CENA DO CRIME : {RST}{Y}{os.path.basename(crime['file'])}{RST} | {Y}COORDENADA: {crime['file']}:{crime['line']}{RST}\n")
        snip = _get_snippet(crime['file'], crime['line'], ctx=1)  # snippet enxuto (3 linhas)
        if snip:
            out.write(snip + '\n')
    ct = _extract_contract(crime)
    if ct and ct.get('hint'):
        sys.stderr.write(f"{G}   ✔ contrato real oferece '{ct['hint']}' (não '{ct['assumed']}'){RST}\n")
    out.write(f"{sep}\n")
    out.write(f"{R}--- [LOG BRUTO] ---{RST}\n{trace}\n{R}-------------------{RST}\n")
    sys.exit(1)

def _correct_crime_scene(info: dict, trace: str) -> dict:
    """🎯 Sobrescreve o veredito do CrashProcessor com o frame REAL da exceção
    (intelligence.py:44) e reconstrói a Cadeia de Envolvimento."""
    mined = _mine_traceback(trace)
    crime = (mined or {}).get('crime')                   # ← defensivo
    if not crime:
        return info
    info['file'] = crime['file']
    info['line'] = crime['line']
    info['chain'] = [(fr['ctx'], f"{fr['file']}:{fr['line']}") for fr in mined.get('frames', [])]
    return info

def _correct_crime_scene(info: dict, trace: str) -> dict:
    mined = _mine_traceback(trace)
    crime = (mined or {}).get('crime')
    if not crime:
        return info
    info['file'] = crime['file']
    info['line'] = crime['line']
    info['chain'] = [(fr['ctx'], f"{fr['file']}:{fr['line']}") for fr in mined.get('frames', [])]
    # ⚖️ ESCLARECIMENTO DE CONTRATO (Ma'at)
    if mined.get('error_type') in _CONTRACT_ERRORS:
        info['technical_error'] = 'FALHA_DE_CONTRATO'
        info['explanation'] = (
            f"{mined['error_type']}: o código assumiu uma garantia que o contrato não oferece "
            f"(chave/atributo/índice inexistente). {mined['error_msg']}"
        )
        info['contract'] = _extract_contract(crime)   # ← HERA
    return info

def _read_trace(trace):
    if trace and os.path.exists(str(trace)):
        with open(trace, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    return trace or ''

def _mine_traceback(trace):
    """Mineração NORMALIZADA: sempre retorna 'crime' e 'frames',
    além das chaves legadas (file/line/context/code) p/ compatibilidade.
    Cláusula 'in' opcional captura frames de SyntaxError (alvo do compile)."""
    if not trace:
        return None
    frames = [{
        'file': m.group('file'), 'line': int(m.group('line')),
        'ctx': (m.group('ctx') or '<compile>').strip(),
        'code': m.group('code').strip(),
    } for m in re.finditer(
        r'File "(?P<file>.+?)", line (?P<line>\d+)(?:, in (?P<ctx>.+?))?\s*\n\s*(?P<code>.+)',
        trace)]
    err = re.search(r'\n([A-Za-z_]+(?:Error|Exception)): (.+)', trace)
    if not err:
        err = re.search(r'\n([A-Za-z_]+): (.+)', trace)
    if not err:
        return None
    crime = frames[-1] if frames else None
    out = {
        'frames': frames,
        'crime': crime,                                   # ← forma nova
        'error_type': err.group(1),
        'error_msg': err.group(2).strip(),
        'message': err.group(2).strip(),
    }
    # Chaves legadas (compatibilidade com consumers antigos)
    if crime:
        out.update({'file': crime['file'], 'line': crime['line'],
                    'context': crime['ctx'], 'code': crime['code']})
    else:
        out.update({'file': None, 'line': None, 'context': None, 'code': None})
    return out

def _get_snippet(file_path, line, ctx=2):
    """Snippet do arquivo REAL onde o erro nasceu."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        out = []
        for i in range(max(0, line - ctx - 1), min(len(lines), line + ctx)):
            marker = '>>' if i == line - 1 else '  '
            out.append(f'     {marker} {i + 1:>4} | {lines[i].rstrip()}')
        return '\n'.join(out)
    except Exception:
        return '     (snippet indisponível)'

def _open_npp(file_path, line):
    for cmd in (['notepad++', f'-n{line}', file_path], ['npp', f'-n{line}', file_path]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    try:
        os.startfile(file_path)
        return True
    except Exception:
        return False

def _view_align(text, width):
    """Alinha o texto compensando os caracteres invisíveis de cor ANSI."""
    import re
    # Regex que remove os códigos ANSI para contar o tamanho real visível
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean_text = ansi_escape.sub('', text)
    padding = width - len(clean_text)
    return text + (" " * max(0, padding))


def _find_production_source(filename: str) -> Optional[Path]:
    if not filename or len(filename) < 3 or filename in ["N/A", "NATIVO"]: return None
    p = Path(filename)
    if p.exists(): return p
    try:
        candidates = [c for c in Path('.').rglob(p.name) if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build', 'shadow'])]
        return candidates[0] if candidates else None
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _find_production_source\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")

def get_code_context(filepath: str, linenum: int, context_lines: int = 2) -> Optional[str]:
    path = _find_production_source(filepath)
    if not path or linenum <= 0: return None
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        start = max(0, linenum - context_lines - 1)
        end = min(len(lines), linenum + context_lines)
        ctx = ""
        for i in range(start, end):
            is_target = (i == linenum - 1)
            marker = " >> " if is_target else "    "
            color = R if is_target else Style.DIM
            ctx += f"    {color}{marker}{i+1:4} | {lines[i].strip()}{RST}\n"
        return ctx.rstrip()
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_code_context\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")

# ─────────────────────────── CORE ENGINE ───────────────────────────

def _find_remedy_in_lexicon(error_msg):
    """Busca no acervo tático um remédio para o erro atual."""
    try:
        from doxoade.core_database import get_db_connection
        conn = get_db_connection()
        # Busca semântica simples: o erro atual contém o padrão do acervo?
        query = "SELECT snippet_fixed FROM knowledge_lexicon WHERE ? LIKE '%' || message || '%'"
        res = conn.execute(query, (error_msg,)).fetchone()
        conn.close()
        return res[0] if res else None
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_type, exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _find_remedy_in_lexicon\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")

def analyze_crash(traceback_text: str, exit_code: int = None) -> Dict[str, Any]:
    from .tools.vulcan.diagnostic.soteria.analyze_crash import CrashProcessor

    if "Errno 2" in traceback_text and " " in os.getcwd():
        info['explanation'] += (
            "\n\n\x1b[43;1m ⚠ ALERTA DE ROOT PLAGUE \x1b[0m\n"
            "Detectado espaço no caminho do projeto e falha de localização de arquivo.\n"
            "Sugestão: Use aspas duplas ou verifique o mapeamento de volumes no Warden." )

    processor = CrashProcessor(project_root=".")
    return processor.process(traceback_text, exit_code)

def _interactive_inspection(d: dict):
    from .doxcolors import Fore, Style
    print("\n\x1b[42;1m 💻 CONSOLE INTERATIVO LAZARUS v2.0 \x1b[0m")
    print(f"{Style.DIM}Snapshot 'info' ativo. Dica: Use ':' no final para blocos multilinhas.")
    print(f"Use 'exit' para voltar.{Style.RESET_ALL}")
    
    context = {
        'info': d, 'vars': d.get('variables', {}), 'chain': d.get('chain', []),
        'io': d.get('io_history', []), 'print': print, 'hex': hex, 'len': len
    }
    
    def show_keys():
        print(f"Chaves em 'info': {list(d.keys())}")
    context['keys'] = show_keys
    
    while True:
        try:
            line = input(f"{Fore.GREEN}inspect>{Style.RESET_ALL} ").strip()
            if line.lower() in ['exit', 'quit', '0']: break
            if not line: continue

            # --- [ MODO MULTILINHAS ] ---
            if line.endswith(':'):
                lines = [line]
                while True:
                    next_line = input(f"{Fore.BLUE}...{Style.RESET_ALL} ")
                    if not next_line: break # Linha vazia finaliza o bloco
                    lines.append(next_line)
                user_code = "\n".join(lines)
            else:
                user_code = line

            # Execução do bloco ou linha única
            restricted_safe_exec(user_code, context, allow_imports=True)
#            restricted_safe_exec(user_code, {"__builtins__": __builtins__}, context)
            
        except Exception as e:
            print(f"{Fore.RED}Erro no comando: {e}{Style.RESET_ALL}")

def _render_io_analysis(d: dict):
    """Renderizador especializado para inspeção de Variáveis e I/O (Opção 5)."""
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT,
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT,
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)
    
    print('\n' + Fore.MAGENTA + Style.BRIGHT + '_' * 110 + RST)
    print(f"{M}■ ANÁLISE DE ESTADO E I/O (Soteria-Link):{RST}")

    # 1. Variáveis Python (Snapshot do momento do erro)
    if d.get('variables'):
        print(f"\n    {C}Variable Table (Snapshot Python):{RST}")
        for k, v in d['variables'].items():
            val_str = str(v)
            if len(val_str) > 60: val_str = val_str[:57] + "..."
            print(f"      {Fore.BLUE}{k:<18} {W}│ {Style.DIM}{val_str}")

    # 2. Histórico de I/O Nativo (C/C++)
    if d.get('io_history'):
        print(f"\n    {Y}Native IO Trace (Fluxo de Dados):{RST}")
        for ev in d['io_history']:
            print(f"      {W}➔ {ev}")

    # 3. Inventário de Memória (Hades Arena)
    if d.get('inventory'):
        print(f"\n    {G}Memory Inventory (Alocações Ativas):{RST}")
        for obj, size in d['inventory']:
            print(f"      {W}● {obj:<25} {M}{size:>8} bytes")
    
    if not any([d.get('variables'), d.get('io_history'), d.get('inventory')]):
        print(f"\n    {Style.DIM}(Nenhum dado de estado ou I/O capturado para este incidente){RST}")

def _render_tactical_dossier(d: dict):
    """Interface de Auditoria de Diamante - Renderização Pura."""
    w = 110
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

    DIM = Style.DIM
    
    # --- [CÁLCULO DE FORMATAÇÃO DO EXIT CODE] ---
    exit_raw = d.get('exit_code')
    is_nt_error = exit_raw is not None and (exit_raw > 255 or exit_raw < -1)
    if is_nt_error:
        # Se for erro de hardware, brilha em Vermelho
        exit_display = f"{Fore.RED}0x{exit_raw & 0xFFFFFFFF:08X}{RST}"
    else:
        exit_display = f"{Fore.YELLOW}{exit_raw}{RST}"

    print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
    print(Fore.CYAN + Style.BRIGHT + '[RELATÓRIO SOB ERRO]'.center(110) + RST + '\n')
    
    # Linha 1 do Header
    print(f"  {W}🆔 ID EVENTO   : {RST}{Fore.YELLOW}{d.get('id', 'N/A'):<20} {W}📅 HORÁRIO : {RST}{Fore.YELLOW}{d.get('timestamp', 'N/A')}")
    # Linha 2 do Header (Invocação + Exit Code)
    print(f"  {W}🚀 INVOCAÇÃO   : {RST}{Fore.YELLOW}{d.get('invocation', 'doxoade'):<20} {W}🚪 EXIT CODE : {RST}{Fore.YELLOW}{exit_display}{RST}")

    # --- SEÇÃO 2: DIAGNÓSTICO TÉCNICO ---
    print(f"\n  {C}■ CAUSA RAIZ (Necropsia de Sistema):{RST}")
    print(f"    {W}STATUS : {R}{d.get('technical_error', 'SYSTEM_FAULT')}{RST}")
    print(f"    {W}LAUDO  : {W}{d.get('explanation', 'Sem detalhes técnicos disponíveis.')}{RST}")
    
    # Análise Especial do Chief para NULL Pointers ou Corrupções
    sot = d.get('soteria', {})
    if sot.get('REG_RAX'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        # Exibe os 4 registradores principais
        print(f"    RAX: {Y}{sot.get('REG_RAX', 'N/A')}{RST} | RBX: {Y}{sot.get('REG_RBX', 'N/A')}{RST}")
        print(f"    RCX: {Y}{sot.get('REG_RCX', 'N/A')}{RST} | RDX: {Y}{sot.get('REG_RDX', 'N/A')}{RST}")

    # --- SEÇÃO 3: EVIDÊNCIAS DE HARDWARE ---
    if sot.get('RIP'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        # Formatação em grid para leitura rápida
        print(f"    RIP: {Y}{sot.get('RIP'):<18}{RST} | RSP: {Y}{sot.get('RSP', 'N/A')}{RST}")
        print(f"    RAX: {Y}{sot.get('RAX', '0x0'):<18}{RST} | RBX: {Y}{sot.get('RBX', '0x0')}{RST}")
        print(f"    RCX: {Y}{sot.get('RCX', '0x0'):<18}{RST} | RDX: {Y}{sot.get('RDX', '0x0')}{RST}")
    if sot.get('REG_RIP'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        print(f"    {W}RAX (Acumulador) : {Y}{sot.get('REG_REG_RAX', 'N/A')}{RST}")
        print(f"    {W}RIP (Instrução) : {Y}{sot.get('REG_RIP', 'N/A')}{RST} | {W}RAX (Acumulador) : {Y}{sot.get('REG_RAX', 'N/A')}")
        print(f"    {W}RSP (Pilha)       : {Y}{sot.get('REG_RSP', 'N/A')}{RST}")

    # --- SEÇÃO 4: INVENTÁRIO DE ARENA (A Mesa do Crime) ---
    if d.get('inventory'):
        print(f"\n  {C}■ INVENTÁRIO DE OBJETOS (Uso da Memória Arena):{RST}")
        from collections import Counter
        counts = Counter([obj[0] for obj in d['inventory']])
        for tipo, qty in counts.items():
            # Barra visual de impacto proporcional (limitada a 20 chars)
            bar_size = min(qty, 20)
            bar = f"{C}{'█' * bar_size}{DIM}{'░' * (20 - bar_size)}"
            print(f"    {W}• {tipo:<20} {bar} {RST}{qty:>3} instâncias")

    if d.get('inventory_raw'):
        print(f"\n  {C}■ INVENTÁRIO DE ARENA (Objetos na RAM):{RST}")
        for item in d['inventory_raw']:
            # Formata: "memory_block | 1024 bytes"
            print(f"    {W}• {item}{RST}")

    # --- SEÇÃO 5: CENA DO CRIME (Lazarus Protocol) ---
    print(f"\n  {C}■ CENA DO CRIME (Triangulação de Código):{RST}")
    file_path = d.get('file', 'NATIVO')
    line_num = d.get('line', 0)
    print(f"    {W}ALVO FONTE  : {RST}{Fore.YELLOW}{os.path.basename(file_path)}{RST} | {W}COORDENADA: {RST}{Fore.YELLOW}{file_path}:{line_num}{RST}")
    
    context = get_code_context(file_path, line_num)
    if context: 
        print(context)
    else:
        print(f"    {DIM}(O código-fonte original não pôde ser resgatado para este frame){RST}")

    # --- SEÇÃO 5.5: CONTRATO DA FRONTEIRA (Hera) ---
    ct = d.get('contract')
    if ct:
        print(f"\n  {M}■ CONTRATO DA FRONTEIRA (o que a interface realmente oferece):{RST}")
        print(f"    {W}ALVO            : {RST}{Y}{ct['target']}{RST}")
        if ct['keys']:
            print(f"    {W}CHAVES VÁLIDAS ({len(ct['keys']):>2}) : {RST}{G}{', '.join(ct['keys'])}{RST}")
        print(f"    {R}✘ ASSUMIDO       : '{ct['assumed']}'{RST}")
        if ct.get('hint'):
            print(f"    {G}✔ VOCÊ QUIS DIZER : '{ct['hint']}'{RST}")

    # --- SEÇÃO 6: CADEIA DE ENVOLVIMENTO ---
    if d.get('chain'):
        print(f"\n  {C}■ CADEIA DE ENVOLVIMENTO (Anatomia da Queda):{RST}")
        for idx, (func_name, loc) in enumerate(d['chain']):
            f_p, l_n = loc.rsplit(':', 1)
            is_py = ".py" in f_p.lower()
            label = "[PY]" if is_py else "[C]"
            color_f = Fore.YELLOW if is_py else G
            
            print(f"    {DIM}[{idx}]{RST} {M}{label}{RST} ↳ {color_f}{func_name:<25}{RST} ({os.path.basename(f_p)}:{l_n})")
            
            # [UPGRADE] Solicita 2 linhas de contexto para gerar o snippet de 5 linhas
            snip = get_code_context(f_p, int(l_n), context_lines=2)
            if snip:
                print(f"{snip}")

    # --- SEÇÃO 7: IO_DEBUG ---
    if d.get('io_history'):
        print(f"\n  {C}■ RASTRO DE OPERAÇÕES (Enriquecido com IO_Content):{RST}")
        for ev in d['io_history'][-10:]:
            # Exemplo de saída: ➔ Operation: printf | Data: "Corrompendo a Zona..."
            print(f"    {W}➔ {ev}{RST}")

    error_raw = d.get('explanation', '')
    remedy = _find_remedy_in_lexicon(error_raw)
    if remedy:
        print(f"\n  {G}💡 [ACERVO] SOLUÇÃO SUGERIDA:{RST}")
        print(f"    {W}Baseado em correções anteriores, tente:{RST}")
        print(f"    {Y}{remedy}{RST}")
        print(f"    {Style.DIM}" + "─" * 40 + RST)

def activate_protocol(error_text: str, exit_code: int = None, trace=None, **kwargs): # <-- ADICIONADO **kwargs
    """Protocolo Lazarus: Menu de Intervenção Imediata (Mode-Aware)."""
    from .tools.telemetry_tools.logger import chief_heartbeat
    import sys as _sys
    import os as _os
    import re

    # Agora kwargs existe no escopo e esta linha não vai mais dar NameError
    context_vars = kwargs.get('context', {})
    trace_text = _read_trace(trace) or error_text or ''
    
    if not error_text: 
        return

    # 🏹 0. DIRECT MODE: falha rápida antes de qualquer necropsia pesada
    if _os.environ.get('DOXOADE_MODE') == 'direct':
        _direct_report(trace_text, _mine_traceback(trace_text))  # nunca retorna

    # --- 1. RESOLUÇÃO DE CÓDIGO TÉCNICO ---
    # Se o exit_code não foi passado pelo SO, tentamos extrair do log bruto da Sotéria
    if exit_code is None:
        match = re.search(r"TAG_MOTIVO:\s*(0x[0-9a-fA-F]+|\d+)", error_text)
        if match:
            val = match.group(1)
            exit_code = int(val, 16) if val.startswith('0x') else int(val)
        else:
            exit_code = 1 # Fallback para erro genérico Python

    # --- 2. NECROPSIA (Análise Única) ---
    from .tools.vulcan.diagnostic.soteria.analyze_crash import CrashProcessor
    processor = CrashProcessor(project_root=".")
    # Processamos o erro uma única vez para obter todos os metadados
    info = processor.process(error_text, exit_code)
    
    # Filtro de Aborto: Se for um encerramento normal, não fazemos nada
    if info.get('technical_error') == "NORMAL_EXIT": 
        return

    info = _correct_crime_scene(info, trace_text)

    # --- 3. TELEMETRIA ENRIQUECIDA (Hades Engine) ---
    # Agora o log registra o VEREDITO real (ex: Memory Corruption) em vez de apenas "Process Crash"
    chief_heartbeat("CHIEF", "RESCUE_ACTIVATED", {
        "verdict": info.get('technical_error', 'Process Crash'),
        "target": _os.path.basename(info.get('file', 'NATIVO')),
        "file": info.get('file', 'NATIVO'),        # ← âncora p/ Hórus
        "f": "activate_protocol",                  # ← nome p/ timeline
        "motivo": info.get('technical_error', 'Process Crash'),
        "exit_code": exit_code
    })

    # --- 4. INTERFACE VISUAL ---
    print('\n' + Back.RED + '[SYSTEM CRASH DETECTED]'.center(110) + Style.RESET_ALL)
    
    # Renderiza o dossiê tático (Aquele com as coordenadas do crime)
    _render_tactical_dossier(info)
    
    # 3. Loop de Intervenção
    try:
#        from .tools.vulcan.diagnostic.soteria.analyze_crash import CrashProcessor
#        processor = CrashProcessor(project_root=".")
#        info = processor.process(error_text, exit_code)
        
        while True:
            print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
            print(Fore.CYAN + Style.BRIGHT + '[OPÇÕES DE INTERVENÇÃO]'.center(110) + RST + '\n\n')
            file_label   = _os.path.basename(info["file"])
            
            opt1                            = f"{Back.RED}1.{RST} {Fore.GREEN} [GIT]  Reverter {Y}{file_label}{RST}"
            if file_label == "NATIVO": opt1 = f"{Style.DIM}[1] [GIT]  (Indisponível p/ falha nativa){RST}"

            opt2 = f"{Back.RED}2.{RST} {Fore.CYAN} [EDIT] Abrir Notepad++ Linha {Y}{info['line']}{RST}"
            opt3 = f"{Back.RED}3.{RST} {Fore.RED} [INFO] Ver logs brutos{RST}"
            opt4 = f"{Back.RED}4.{RST} {RST}{Fore.YELLOW} [DEBUG] Diagnóstico Pipeline{RST}"
            opt5 = f"{Back.RED}5.{RST} {Fore.MAGENTA} [IO]    Analisar Dados e Memória{RST}"
            opt6 = f"{Back.RED}6.{RST} {Fore.GREEN} [CODE]  Console Interativo{RST}"
            opt7 = f"{Back.RED}7.{RST} {Fore.CYAN} [HORUS] Ver Timeline NSR (Shadow){RST}" 
            opt8 = f"{Back.RED}8.{RST} {Fore.YELLOW} [FIX]  Dry-Run da Correção (Anúbis){RST}"
            opt0 = f"{Back.RED}0.{RST} {Fore.LIGHTMAGENTA_EX} [EXIT] Encerrar sessão{RST}"

            # Renderização em Grade 2x2 usando o alinhador inteligente
            # Largura de 55 para caber bem em telas padrão de 110/120 colunas
            print(f"  {_view_align(opt1, 55)} {opt2}")
            print(f"  {_view_align(opt3, 55)} {opt4}")
            print(f"  {_view_align(opt5, 55)} {opt6}")
            print(f"  {_view_align(opt7, 55)} {opt0}")
            print(f"  {opt8}")
#            print(f"  {_view_align(opt0, 55)}")

#            choices = input("\n  Sua decisão (ex: 34): ").strip()
#            if '0' in choices: break

            raw = input("\n  Sua decisão (ex: 34): ").strip()
            # 🛡️ Ignora caracteres que não são opções (evita executar letra por letra)
            choices = [c for c in raw if c in '0123456789fF']
            if not choices:
                continue  # texto sem opção válida → volta ao menu
            if '0' in choices: break

            try:
                for choice in choices:
                    if len(choices) > 1:
                        print(f"\n  {Style.DIM}▶ executando ação [{choice}]...{RST}")
                    if choice == '1' and file_label != "NATIVO":
                        subprocess.run(['git', 'checkout', '--', info['file']], capture_output=True)
                        print(f'  {Fore.GREEN}✔ Sucesso: {file_label} restaurado.{Style.RESET_ALL}')
                        
                    elif choice == '2':
                        # Localização Industrial do Notepad++ (Evita 'file not found' no Windows)
                        import shutil
                        npp_candidates = [
                            r"C:\Program Files\Notepad++\notepad++.exe",
                            r"C:\Program Files (x86)\Notepad++\notepad++.exe",
                            "notepad++.exe"
                        ]
                        npp_bin = next((p for p in npp_candidates if _os.path.exists(p) or shutil.which(p)), 'notepad.exe')
                        
                        print(f'  {C}[*] Invocando editor...{RST}')
                        # Flag -n pula direto para a linha do erro no Notepad++
                        target_abs = _os.path.abspath(info['file'])
                        subprocess.Popen([npp_bin, f"-n{info['line']}", "-nosession", target_abs], shell=False)
                        print(f'  {G}✔ Editor aberto em {file_label} L{info["line"]}.{RST}')
                        
                    elif choice == '3':
                        print('\n' + Fore.RED+Style.BRIGHT + '_' * 110 + RST)
                        print(f"\n  {Fore.RED+Style.BRIGHT}■ [BRUTE LOG] Soteria Engine:{RST}\n")
                        # Exibição do log sem as tags Sotéria para limpeza visual
                        clean_log = error_text.replace("@SOTERIA_BEGIN@", "").replace("@SOTERIA_END@", "")
                        print(f'\n{R}--- [ INÍCIO DO LOG BRUTO ] ---{RST}')
                        print(f"{Style.DIM}{clean_log}{RST}")
                        print(f'{R}--- [ FIM DO LOG ] ---{RST}')
            #            input(f'\n{Style.DIM}Pressione Enter para prosseguir para a saída...{RST}')
            
                    elif choice == '4':
                        print('\n' + Fore.RED+Style.BRIGHT + '_' * 110 + RST)
                        print(f"\n  {Fore.RED+Style.BRIGHT}■ [PIPELINE PROBE] Hades Engine:{RST}\n")
                        try:
                            from doxoade.core_database import get_db_connection
                            import json
                            conn = get_db_connection()
                            rows = conn.execute('SELECT timestamp, subsystem, action, data FROM operational_logs ORDER BY id DESC LIMIT 12').fetchall()
                            for r in reversed(rows):
                                # FIX: Corrigido de 's11' para '[11:19]'
                                ts = r['timestamp'][11:19] 
                                sys_label = f"{r['subsystem']:<10}"
                                act_label = f"{r['action']:<22}"
                                try:
                                    d_obj = json.loads(r['data'])
                                    # Limpa a visualização do JSON para o terminal
                                    d_str = ", ".join([f'"{k}": {v}' for k, v in d_obj.items()])
                                except Exception as e:
                                    import sys as _dox_sys, os as _dox_os
                                    from traceback import print_tb as exc_trace
                                    exc_obj, exc_tb = _dox_sys.exc_info()
                                    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                    line_n = exc_tb.tb_lineno
                                    exc_trace(exc_tb)
                                    print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: activate_protocol\033[0m")
                                    print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                                    d_str = r['data']
                                
                                print(f"  {Style.DIM}[{ts}]{RST} {Fore.YELLOW}{sys_label}{RST} │ {C}{act_label}{RST} >> {W}{d_str}{RST}")
                            conn.close()
                        except Exception as e:
                            print(f"  {R}✘ Falha ao consultar Hades: {e}{RST}")
                            
                    elif choice == '5':                      # ← era: '5' in choices
                        _render_io_analysis(info)
                    elif choice == '6':                      # ← era: '6' in choices
                        _interactive_inspection(info)
                    elif choice == '7':                      # ← era: '7' in choices
                        print('\n' + Fore.CYAN + Style.BRIGHT + '─' * 110 + RST)
                        print(f"\n  {Fore.CYAN + Style.BRIGHT}👁️  INQUÉRITO HÓRUS: Rastro Próximo ao Incidente{RST}\n")
                        try:
                            from .commands.horus_cmd import run_horus_view_logic
                            f_name = _os.path.basename(info.get('file', ''))
                            if f_name == "<string>": f_name = None
                            run_horus_view_logic(limit=50, full=True, focus=f_name)
                        except Exception as e:
                            print(f"  {Fore.RED}✘ Falha ao recuperar rastro tático: {e}{RST}")
                    elif choice in ('8', 'f', 'F'):          # ← agora alcançável
                        _fix_workflow(info)
                break
            except Exception as e:
                from .error_info import handle_error
                handle_error(e, context="activate_protocol", debug=True)
    except Exception as e:
        # --- [ MODO DE EMERGÊNCIA: SOTÉRIA OFFLINE ] ---
        print("\n\x1b[41m[ CRITICAL ] O Motor de Diagnóstico Sotéria falhou!\x1b[0m")
        print(f"\x1b[33mCausa: {e}\x1b[0m")
        # Criamos um dossiê mínimo para não quebrar a UI
        info = {
            'technical_error': "DIAGNOSTIC_ENGINE_FAILURE",
            'explanation': "Ocorreu um erro interno no Doxoade ao analisar esta falha.",
            'file': "DESCONHECIDO", 'line': 0, 'exit_code': exit_code, 'chain': []
        }
#        from .error_info import handle_error
 #       handle_error(e, context="activate_protocol", debug=True)

    # --- FOOTER ---
    print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
    
    # --- O SELO FINAL ---
    # os._exit garante que o Lazarus não tente se auto-diagnosticar ao fechar
# [DOX-UNUSED]     import os
#    _os._exit(1) # obs: vejo que é melhor sys._exit.
    _sys.exit(exit_code if exit_code is not None else 1)

if __name__ == '__main__':
    activate_protocol(sys.argv[1] if len(sys.argv) > 1 else None)
