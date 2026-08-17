# doxoade/doxoade/tools/aegis/aegis_core.py
import os
import logging
from typing import Any, Dict

# Lista negra de termos sensíveis
NEXUS_FORBIDDEN = {
    '__import__', 'os.system', 'os.popen', 'subprocess', 
    'shutil', 'getattr', 'setattr', 'delattr', '__subclasses__',
    '__globals__', '__builtins__'
}

def nexus_eval(expression: str, globals_dict: Dict = None, locals_dict: Dict = None) -> Any:
    """Eval restrito com blindagem Aegis."""
    _validate_dynamic_payload(expression, "EVAL")
    
    # Se não passarem globals, cria um deserto de builtins
    if globals_dict is None:
        globals_dict = {"__builtins__": {}}
    elif "__builtins__" not in globals_dict:
        import builtins as _builtins_mod
        globals_dict["__builtins__"] = _builtins_mod.__dict__

        
    return eval(expression, globals_dict, locals_dict) # noqa

def nexus_exec(source: Any, globals_dict: Dict = None, locals_dict: Dict = None):
    """Exec monitorado com isolamento de ambiente."""
    # Se for código compilado, a validação já deve ter ocorrido na AST (aegis_utils)
    if isinstance(source, str):
        _validate_dynamic_payload(source, "EXEC")
    
    if globals_dict is None:
        globals_dict = {"__builtins__": {}}
    elif "__builtins__" not in globals_dict:
        import builtins as _builtins_mod
        globals_dict["__builtins__"] = _builtins_mod.__dict__

        
    return exec(source, globals_dict, locals_dict) # noqa

def _validate_dynamic_payload(payload: str, mode: str):
    """Analisa strings de payload em busca de escapes de sandbox."""
    
    # BYPASS INDUSTRIAL: Se for o próprio sistema rodando, libera shutil
    if os.environ.get('DOXOADE_AUTHORIZED_RUN') == '1':
        return

    payload_clean = payload.replace(" ", "").replace("\t", "").lower()
    for forbidden in NEXUS_FORBIDDEN:
        if forbidden.lower() in payload_clean:
            logging.warning(f"Aegis Breach Attempt: {mode} payload contém {forbidden}")
            raise PermissionError(
                f"AEGIS SHIELD: Bloqueio de {mode}. Termo proibido detectado: {forbidden}"
            )
