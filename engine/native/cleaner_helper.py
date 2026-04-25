# engine/native/cleaner_helper.py
import ctypes
import os
from pathlib import Path

def vulcan_batch_delete(file_paths):
    """
    Chama o binário Vulcan para deletar arquivos em paralelo.
    """
    # Em um cenário real, o Doxoade Vulcan compilaria o .c para um .pyd ou .dll
    dll_path = Path(__file__).parent / "vulcan_cleaner.dll"
    
    if not dll_path.exists():
        # Fallback para o modo lento se o binário não estiver compilado
        deleted = 0
        for p in file_paths:
            try:
                os.remove(p)
                deleted += 1
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: vulcan_batch_delete\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return deleted

    lib = ctypes.CDLL(str(dll_path))
    lib.batch_delete_parallel.argtypes = [ctypes.POINTER(ctypes.c_wchar_p), ctypes.c_int, ctypes.c_int]
    lib.batch_delete_parallel.restype = ctypes.c_int

    # Prepara a lista para o C
    c_array = (ctypes.c_wchar_p * len(file_paths))(*file_paths)
    
    # Usa 4 threads para processamento paralelo
    return lib.batch_delete_parallel(c_array, len(file_paths), 4)