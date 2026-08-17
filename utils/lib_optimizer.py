# doxoade/doxoade/tools/vulcan/lib_optimizer.py
"""
LibOptimizer — Otimizador AST seguro para cópias de fontes de bibliotecas.
==========================================================================

Aplicado à cópia isolada dos .py ANTES do HybridIgnite.
O original no venv NUNCA é tocado.

Transformações (ordenadas do mais para o menos seguro):
  1. DocstringRemover        — remove docstrings de módulo/classe/função
  2. DeadBranchEliminator    — elimina `if False/True/0/1:`, `while False:`
  3. UnusedImportRemover     — remove `import X` nunca referenciado
  4. ImportCombiner          — funde imports consecutivos numa única instrução
  5. GlobalImportAliaser     — aplica alias (as _I1) em imports de nomes longos
  6. SafeLocalNameMinifier   — renomeia variáveis e aliases de forma segura

Regras de segurança:
  - Nunca renomeia nomes públicos (nível de módulo)
  - Nunca renomeia parâmetros de função
  - Nunca renomeia se a função usa locals()/vars()/exec()/eval()
  - Nunca renomeia nomes que aparecem como string literal na mesma função
    (proteção contra getattr(obj, 'varname'))
  - Nunca entra em funções aninhadas ao minificar
  - Smart Unparsing: Pula a rescrita em disco se a AST não foi modificada.
  - Thread-Local Pool: ThreadPoolExecutor com instâncias reutilizadas por thread.

Compliance:
  OSL-4: cada classe tem responsabilidade única
  OSL-5: optimize_file() nunca levanta exceção — revert em falha
  PASC-6: fail-graceful em qualquer etapa
"""
from __future__ import annotations
import ast
import os
import string
import itertools
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
try:
    _ast_unparse = ast.unparse
except AttributeError:
    try:
        import astor
        _ast_unparse = astor.to_source
    except Exception:
        _ast_unparse = None

@dataclass
class FileOptReport:
    """Resultado da otimização de um arquivo .py."""
    path: str
    original_bytes: int = 0
    final_bytes: int = 0
    docstrings_removed: int = 0
    dead_branches: int = 0
    imports_removed: int = 0
    locals_minified: int = 0
    skipped: bool = False
    skip_reason: str = ''

    @property
    def bytes_saved(self) -> int:
        return max(0, self.original_bytes - self.final_bytes)

    @property
    def was_changed(self) -> bool:
        return not self.skipped and self.bytes_saved > 0
_opt_thread_local = __import__('threading').local()

def _worker_optimize_file(path: Path) -> FileOptReport:
    """
    Otimiza um arquivo usando a instância LibOptimizer da thread atual.

    Thread-Local Pool: a instância é criada na primeira chamada de cada
    worker-thread e reutilizada para todos os arquivos seguintes.
    Isso elimina o overhead de instanciação O(N_arquivos) que o modelo
    original com ProcessPoolExecutor tinha por design (pickle exigia
    instâncias frescas — com threads, reutilização é segura).
    """
    if not hasattr(_opt_thread_local, 'optimizer'):
        _opt_thread_local.optimizer = LibOptimizer()
    return _opt_thread_local.optimizer.optimize_file(path)

class LibOptimizer:
    """
    Aplica pipeline de otimizações AST em todos os .py de um diretório.

    Uso:
        optimizer = LibOptimizer()
        stats = optimizer.optimize_directory(work_copy_path)
    """
    _SCOPE_ACCESSORS = frozenset({'locals', 'vars', 'exec', 'eval', 'globals', 'dir', 'inspect'})

    def _uses_structural_meta(self, tree: ast.AST) -> bool:
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and n.attr in {'_fields', '__dataclass_fields__', '__slots__'}:
                return True
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name) and n.func.id in {'namedtuple', 'dataclass'}:
                    return True
        return False

    def optimize_file(self, path: Path) -> FileOptReport:
        """
        Otimiza um único arquivo .py in-place (cópia de trabalho).

        PASC-6: nunca levanta exceção. Em qualquer falha, o arquivo
        original é restaurado e o relatório marca skipped=True.
        """
        report = FileOptReport(path=str(path))
        try:
            source = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as exc:
            report.skipped = True
            report.skip_reason = f'leitura falhou: {exc}'
            return report
        report.original_bytes = len(source.encode('utf-8'))
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            report.skipped = True
            report.skip_reason = f'parse error: {exc}'
            return report
        has_scope_access = self._has_scope_accessor(tree)
        uses_structural_meta = any((isinstance(n, ast.Attribute) and n.attr == '_fields' for n in ast.walk(tree)))
        total_mutations = 0
        try:
            ds = DocstringRemover()
            tree = ds.visit(tree)
            report.docstrings_removed = ds.count
            total_mutations += ds.count
            db = DeadBranchEliminator()
            tree = db.visit(tree)
            report.dead_branches = db.count
            total_mutations += db.count
            ui = UnusedImportRemover()
            tree = ui.process(tree)
            report.imports_removed = ui.count
            total_mutations += ui.count
            if not uses_structural_meta:
                ic = ImportCombiner()
                tree = ic.visit(tree)
                total_mutations += ic.count
            if not uses_structural_meta:
                ga = GlobalImportAliaser()
                tree = ga.visit(tree)
                total_mutations += len(ga.import_map)
            uses_structural_meta = self._uses_structural_meta(tree)
            if not has_scope_access and (not uses_structural_meta):
                mn = LocalNameMinifier()
                tree = mn.visit(tree)
                report.locals_minified = mn.count
                total_mutations += mn.count
            ast.fix_missing_locations(tree)
            if total_mutations == 0:
                report.final_bytes = report.original_bytes
                return report
            if not _ast_unparse:
                raise RuntimeError('ast.unparse indisponível.')
            optimized = _ast_unparse(tree)
            optimized = self.compact_lines_safely(optimized)
            ast.parse(optimized)
            path.write_text(optimized, encoding='utf-8')
            report.final_bytes = len(optimized.encode('utf-8'))
        except Exception as exc:
            try:
                path.write_text(source, encoding='utf-8')
            except Exception:
                pass
            report.skipped = True
            report.skip_reason = f'otimização revertida: {exc}'
            report.final_bytes = report.original_bytes
        return report

    def optimize_directory(self, directory: Path) -> dict:
        """
        Otimiza todos os .py do diretório recursivamente.

        Cirurgias aplicadas vs versão original:
          1. ProcessPoolExecutor → ThreadPoolExecutor:
             No Windows, ProcessPool faz 'spawn' de um novo interpretador Python
             completo para cada worker. Para libs pequenas (ex: click com 17 .py),
             o overhead de spawn supera o trabalho real. ThreadPool elimina isso
             e ainda compartilha o mesmo espaço de memória (sem pickle de args).
             As operações de AST (ast.parse, ast.walk) são majoritariamente
             código Python — o GIL não é o gargalo aqui, e sim o I/O de disco.

          2. Thread-Local Pool via _opt_thread_local:
             Cada worker-thread cria UMA instância de LibOptimizer e reutiliza
             para todos os arquivos daquela thread. N_CPU instâncias em vez de
             N_arquivos instâncias.

          3. Streaming summary com as_completed:
             Em vez de materializar todos os FileOptReport em RAM simultaneamente
             com list(executor.map(...)), acumula apenas os contadores numéricos.
             Para libs grandes (centenas de .py), isso reduz o pico de RAM.
        """
        files = sorted(directory.rglob('*.py'))
        max_workers = min(os.cpu_count() or 2, len(files)) if files else 1
        files_processed = 0
        files_optimized = 0
        files_skipped = 0
        bytes_saved = 0
        docstrings_removed = 0
        dead_branches = 0
        imports_removed = 0
        locals_minified = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_worker_optimize_file, f): f for f in files}
            for future in concurrent.futures.as_completed(futures):
                try:
                    r: FileOptReport = future.result()
                except Exception:
                    files_skipped += 1
                    files_processed += 1
                    continue
                files_processed += 1
                files_optimized += 1 if r.was_changed else 0
                files_skipped += 1 if r.skipped else 0
                bytes_saved += r.bytes_saved
                docstrings_removed += r.docstrings_removed
                dead_branches += r.dead_branches
                imports_removed += r.imports_removed
                locals_minified += r.locals_minified
        summary = {'files_processed': files_processed, 'files_optimized': files_optimized, 'files_skipped': files_skipped, 'bytes_saved': bytes_saved, 'docstrings_removed': docstrings_removed, 'dead_branches': dead_branches, 'imports_removed': imports_removed, 'locals_minified': locals_minified}
        return {**summary, 'summary': summary}

    def _has_scope_accessor(self, tree: ast.AST) -> bool:
        """True se o módulo usa calls que acessam locals por nome."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name and name in self._SCOPE_ACCESSORS:
                    return True
        return False

    @staticmethod
    def compact_lines_safely(code: str) -> str:
        """
        Agrupa instruções simples na mesma linha com ';' 
        aproveitando a previsibilidade absoluta do ast.unparse().
        """
        lines = code.split('\n')
        if not lines:
            return ''
        out_lines = []
        current_line = lines[0]

        def get_indent(s):
            return len(s) - len(s.lstrip())
        compound_keywords = ('if ', 'for ', 'while ', 'def ', 'class ', 'try:', 'with ', 'elif ', 'else:', 'except', 'finally:', '@', 'async ', 'match ', 'case ')
        in_multiline = False
        for i in range(1, len(lines)):
            nxt = lines[i]
            if not nxt.strip():
                continue
            if nxt.count('"""') % 2 != 0 or nxt.count("'''") % 2 != 0:
                in_multiline = not in_multiline
            curr_indent = get_indent(current_line)
            nxt_indent = get_indent(nxt)
            is_compound_curr = current_line.lstrip().startswith(compound_keywords)
            is_compound_nxt = nxt.lstrip().startswith(compound_keywords)
            ends_with_colon = current_line.rstrip().endswith(':')
            has_triple = '"""' in current_line or "'''" in current_line or '"""' in nxt or ("'''" in nxt)
            if curr_indent == nxt_indent and curr_indent > 0 and (not has_triple) and (not ends_with_colon) and (not is_compound_curr) and (not is_compound_nxt) and (curr_indent <= 8):
                current_line = current_line + '; ' + nxt.lstrip()
            else:
                out_lines.append(current_line)
                current_line = nxt
        out_lines.append(current_line)
        return '\n'.join(out_lines)

class DocstringRemover(ast.NodeTransformer):

    def __init__(self):
        self.count = 0

    def _strip(self, node):
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body.pop(0)
            self.count += 1
            if not node.body:
                node.body.append(ast.Pass())
        return node

    def visit_Module(self, node):
        self.generic_visit(node)
        return self._strip(node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return self._strip(node)
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        return self._strip(node)

class DeadBranchEliminator(ast.NodeTransformer):

    def __init__(self):
        self.count = 0

    def _always_false(self, test):
        return isinstance(test, ast.Constant) and (not bool(test.value)) and (test.value is not True)

    def _always_true(self, test):
        return isinstance(test, ast.Constant) and bool(test.value) and (not isinstance(test.value, str))

    def visit_If(self, node):
        self.generic_visit(node)
        if self._always_false(node.test):
            self.count += 1
            return node.orelse if node.orelse else None
        if self._always_true(node.test):
            self.count += 1
            return node.body
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        if self._always_false(node.test):
            self.count += 1
            return None
        return node

class UnusedImportRemover:
    _SIDE_EFFECT_KEEP = frozenset({'__future__', 'logging', 'warnings', 'traceback', 'atexit', 'signal', 'site', 'antigravity', 'this'})

    def __init__(self):
        self.count = 0

    def process(self, tree):
        used = self._collect_used_names(tree)
        transformer = _ImportTransformer(used, self._SIDE_EFFECT_KEEP)
        res = transformer.visit(tree)
        self.count = transformer.count
        return res

    @staticmethod
    def _collect_used_names(tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier():
                names.add(node.value)
        return names

class _ImportTransformer(ast.NodeTransformer):

    def __init__(self, used_names, side_effects):
        self._used = used_names
        self._side_effects = side_effects
        self.count = 0

    def visit_Import(self, node):
        kept = []
        for alias in node.names:
            root = alias.name.split('.')[0]
            if root in self._side_effects:
                kept.append(alias)
                continue
            bound = alias.asname if alias.asname else alias.name
            if bound.split('.')[0] in self._used:
                kept.append(alias)
            else:
                self.count += 1
        if not kept:
            return None
        node.names = kept
        return node

class ImportCombiner(ast.NodeTransformer):

    def __init__(self):
        self.count = 0

    def _combine(self, body):
        new_body = []
        curr_import = None
        for stmt in body:
            if not isinstance(stmt, ast.AST):
                new_body.append(stmt)
                continue
            if type(stmt) is ast.Import:
                if curr_import is None:
                    curr_import = stmt
                    new_body.append(curr_import)
                else:
                    curr_import.names.extend(stmt.names)
                    self.count += 1
            else:
                curr_import = None
                new_body.append(self.visit(stmt))
        return new_body

    def generic_visit(self, node):
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                setattr(node, field, self._combine(old_value))
            elif isinstance(old_value, ast.AST):
                setattr(node, field, self.visit(old_value))
        return node

class LocalNameMinifier(ast.NodeTransformer):
    """
    Minifica nomes de variáveis locais em funções simples (sem escopo aninhado).
    """
    _PROTECTED = frozenset({'self', 'cls', 'True', 'False', 'None', 'len', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round', 'any', 'all', 'isinstance', 'issubclass', 'type', 'id', 'hash', 'repr', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'bytes', 'bytearray', 'memoryview', 'object', 'super', 'hasattr', 'getattr', 'setattr', 'delattr', 'vars', 'dir', 'open', 'print', 'input', 'format', 'bin', 'hex', 'oct', 'chr', 'ord', 'iter', 'next', 'callable', 'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError', 'StopIteration', 'RuntimeError', 'OSError', 'IOError', 'FileNotFoundError', 'ImportError', 'NameError', 'NotImplementedError', 'OverflowError', 'ZeroDivisionError', 'BaseException', 'GeneratorExit', 'SystemExit', 'KeyboardInterrupt'})

    def __init__(self):
        self.count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        self._minify(node)
        return node
    visit_AsyncFunctionDef = visit_FunctionDef

    def _minify(self, func: ast.FunctionDef):
        for child in ast.walk(func):
            if child is func:
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return
        protected = set(self._PROTECTED)
        for arg in func.args.args + func.args.posonlyargs + func.args.kwonlyargs:
            protected.add(arg.arg)
        if func.args.vararg:
            protected.add(func.args.vararg.arg)
        if func.args.kwarg:
            protected.add(func.args.kwarg.arg)
        string_refs: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                string_refs.add(child.value)
        candidates: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                name = child.id
                if name not in protected and (not name.startswith('_')) and (not name.startswith('__')) and (name not in string_refs) and (len(name) > 2):
                    candidates.add(name)
        if not candidates:
            return
        existing_names = self._all_names_in(func)
        mapping: dict[str, str] = {}
        counter = 0
        for original in sorted(candidates):
            new = self._gen_name(counter)
            while new in existing_names or new in protected:
                counter += 1
                new = self._gen_name(counter)
            mapping[original] = new
            existing_names.add(new)
            counter += 1
        if not mapping:
            return
        _NameRenamer(mapping).generic_visit(func)
        self.count += len(mapping)

    @staticmethod
    def _all_names_in(func: ast.FunctionDef) -> set[str]:
        """Coleta todos os nomes referenciados na função (para evitar colisão)."""
        names: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Name):
                names.add(child.id)
            elif isinstance(child, ast.arg):
                names.add(child.arg)
        return names

    @staticmethod
    def _gen_name(n: int) -> str:
        """
        Gera nomes curtos com prefixo underscore:
          0 → _a, 1 → _b, ..., 25 → _z, 26 → _aa, 27 → _ab, ...
        O underscore evita conflito com builtins de letra única (e, f, i…).
        """
        chars = 'abcdefghijklmnopqrstuvwxyz'
        result = ''
        n += 1
        while n > 0:
            n -= 1
            result = chars[n % 26] + result
            n //= 26
        return f'_{result}'

class _NameRenamer(ast.NodeTransformer):
    """
    Visitor que renomeia Name nodes de acordo com um mapeamento.
    Não descende em FunctionDef/Lambda aninhados (escopo separado).
    """

    def __init__(self, mapping: dict[str, str]):
        self._m = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._m:
            node.id = self._m[node.id]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return node
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        return node

class GlobalImportAliaser(ast.NodeTransformer):

    def __init__(self):
        self.import_map = {}
        self.counter = 1

    def _get_alias(self):
        alias = f'Ia{self.counter}'
        self.counter += 1
        return alias

    def visit_ImportFrom(self, node):
        if getattr(node, '_framework_safe', False):
            return node
        for alias in node.names:
            if alias.name == '*':
                continue
            orig = alias.asname or alias.name
            if len(orig) > 6:
                new_alias = self._get_alias()
                alias.asname = new_alias
                self.import_map[orig] = new_alias
        return node

    def visit_Import(self, node):
        for alias in node.names:
            orig = alias.asname or alias.name
            if len(orig) > 6:
                new_alias = self._get_alias()
                alias.asname = new_alias
                self.import_map[orig] = new_alias
        return node

    def visit_Name(self, node):
        if getattr(node, '_framework_safe', False):
            return node
        if node.id in self.import_map:
            node.id = self.import_map[node.id]
        return node

class SafeLocalNameMinifier(ast.NodeTransformer):

    def __init__(self):
        super().__init__()
        self._name_generator = self._short_name_generator()
        self.scope_maps = []
        self.count = 0

    def _short_name_generator(self):
        chars = string.ascii_lowercase
        yield from (f'_{c}' for c in chars)
        for length in itertools.count(2):
            for p in itertools.product(chars, repeat=length):
                yield f"_{''.join(p)}"

    class _VarCollector(ast.NodeVisitor):

        def __init__(self, excluded_names):
            self.local_vars = set()
            self.excluded = set(excluded_names)
            self.is_unsafe = False
            self.globals_nonlocals = set()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in {'locals', 'vars', 'eval', 'exec'}:
                self.is_unsafe = True
            self.generic_visit(node)

        def visit_Global(self, node):
            self.globals_nonlocals.update(node.names)

        def visit_Nonlocal(self, node):
            self.globals_nonlocals.update(node.names)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store) and node.id not in self.excluded:
                self.local_vars.add(node.id)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

def _call_name(node: ast.Call) -> Optional[str]:
    """Extrai o nome de uma chamada de função de forma segura."""
    try:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    except Exception:
        pass
    return None
