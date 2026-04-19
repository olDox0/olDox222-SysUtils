# doxoade/doxoade/tools/error_info.py
"""
EXEMPLOS

from doxoade.tools.error_info import handle_error
handle_error(e, context="NomeDaFuncaoOndeEstaOErro", debug=True)

except Exception as e:
    from doxoade.tools.error_info import handle_error
    handle_error(e, context="Clone Detection JSON Parse", debug=True)
"""

def handle_error(err: Exception, context: str='', silent: bool=False, debug: bool=False):
    """
    Manipulador padrão de erros do Doxoade.

    :param err: exceção capturada
    :param context: contexto da operação (ex: "carregando settings.json")
    :param silent: não exibe nada
    :param debug: exibe traceback completo
    """
    if silent:
        return
    err_type = type(err).__name__
    msg = str(err)
    prefix = '⚠️ [DOXOADE ERROR]'
    if context:
        print(f'{prefix} ({context}) -> {err_type}: {msg}')
    else:
        print(f'{prefix} {err_type}: {msg}')
    from traceback import print_exc
    if debug:
        print('---- TRACEBACK ----')
        print_exc()

def _extract_function_signatures(content: str) -> dict:
    """Extrai o mapa semântico de funções e seus argumentos (MPoT-7)."""
    if not content:
        return {}
    import ast
    try:
        tree = ast.parse(content)
        functions = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [arg.arg for arg in node.args.args]
                functions[node.name] = {'args': args, 'is_async': isinstance(node, ast.AsyncFunctionDef)}
        return functions
    except SyntaxError:
        return {}
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context='analysis._extract_function_signatures', silent=True)
        return {}