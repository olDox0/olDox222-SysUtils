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
            except: pass
        return deleted

    lib = ctypes.CDLL(str(dll_path))
    lib.batch_delete_parallel.argtypes = [ctypes.POINTER(ctypes.c_wchar_p), ctypes.c_int, ctypes.c_int]
    lib.batch_delete_parallel.restype = ctypes.c_int

    # Prepara a lista para o C
    c_array = (ctypes.c_wchar_p * len(file_paths))(*file_paths)
    
    # Usa 4 threads para processamento paralelo
    return lib.batch_delete_parallel(c_array, len(file_paths), 4)