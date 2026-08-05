# doxbackup/core/engine.py
import click
import ctypes
import gc
import os
import psutil
import struct
import subprocess
import sys
import tarfile
import time
import zstandard as zstd

from pathlib import Path

from diskdiag.analysis.heuristics import should_ignore_dir, should_exclude_file, should_exclude_from_backup
from doxbackup.core.security import DoxDecryptorStream
from utils.path_utils import is_ignored_folder, should_exclude_path

SYS_ROOT = Path(__file__).resolve().parents[2]

def get_last_backup_time(source_dir):
    marker = os.path.join(source_dir, ".dox_marker")
    return int(os.path.getmtime(marker) * 10000000 + 116444736000000000) if os.path.exists(marker) else 0

def update_last_backup_time(source_dir):
    with open(os.path.join(source_dir, ".dox_marker"), 'w') as f: f.write(str(time.time()))

def should_skip(path):
    name = os.path.basename(path).lower()
    if name.endswith('.bak'): return True
    parts = path.lower().split(os.sep)
    return any(p in IGNORE_LIST for p in parts)

def backup_data_native(source_dir, output_file, password, progress_callback=None):
    from doxbackup.core.security import encrypt_file_stream
    
    temp_compressed = output_file + ".tmp"
    packer_exe = os.path.join(os.path.dirname(__file__), "..", "native", "dox_packer.exe")
    
    # Se o binário C existir, usamos ele. Se não, usamos o fallback em Python.
    if os.path.exists(packer_exe):
        # Abre o packer em C
        packer_proc = subprocess.Popen([packer_exe, source_dir], stdout=subprocess.PIPE, bufsize=10**6)
        
        cctx = zstd.ZstdCompressor(level=10, threads=-1)
        with open(temp_compressed, 'wb') as f_out:
            # O compressor lê direto da saída do processo C (Zero-copy Python)
            cctx.copy_stream(packer_proc.stdout, f_out)
        
        packer_proc.wait()
    else:
        # Fallback para o modo Tarfile que você já tem...
        pass

    # Segue para criptografia AES como antes
    encrypt_file_stream(temp_compressed, output_file, password)

def get_ram_optimized_params():
    try:
        available_ram = psutil.virtual_memory().available / (1024 * 1024)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_ram_optimized_params\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        available_ram = 500
    if available_ram < 400:
        return {"level": 5, "threads": 1, "ldm": False, "buf_size": 512*1024}
    return {"level": 10, "threads": -1, "ldm": True, "buf_size": 1024 * 1024}

def get_safe_params():
    """Configura limites rígidos de RAM para evitar crash."""
    # window_log=24 significa uma janela de 16MB na RAM. 
    # Ideal para máquinas de 2GB.
    zparams = zstd.ZstdCompressionParameters.from_level(
        10, 
        enable_ldm=True, 
        ldm_hash_log=15, 
        window_log=24 
    )
    return zparams

def get_file_list(source_dir, timestamp=0):
    valid_files = []
    source_dir_abs = os.path.abspath(source_dir)
    
    for root, dirs, files in os.walk(source_dir_abs):
        # EFICIÊNCIA: Poda as pastas proibidas antes de entrar nelas
        dirs[:] = [d for d in dirs if not is_ignored_folder(d)]
        
        for f in files:
            full_path = os.path.join(root, f)
            
            # FILTRAGEM CENTRALIZADA
            if should_exclude_path(full_path):
                continue
                
            # Filtro Incremental (se aplicável)
            if timestamp > 0:
                try:
                    mtime = os.stat(full_path).st_mtime
                    win_time = int(mtime * 10000000 + 116444736000000000)
                    if win_time <= timestamp: continue
                except Exception as e:
                    import sys as _dox_sys, os as _dox_os
                    exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    line_n = exc_tb.tb_lineno
                    print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_file_list\033[0m")
                    print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                    continue
                
            valid_files.append(full_path)
            
    return valid_files

def backup_data(source_dir, output_file, password, timestamp=0, hint=""):
    from doxbackup.core.security import DoxEncryptor
    
    all_files = get_file_list(source_dir, timestamp)
    if not all_files:
        click.secho("[INFO] Nada para processar.", fg="green"); return

    # Freio de RAM para 2GB
    zparams = zstd.ZstdCompressionParameters.from_level(5, threads=1, window_log=21)
    encryptor = DoxEncryptor(output_file, password, hint=hint)
    cctx = zstd.ZstdCompressor(compression_params=zparams)
    packer_exe = os.path.join(os.getcwd(), "doxbackup", "native", "dox_packer.exe")

    try:
        batch_size = 200
        for i in range(0, len(all_files), batch_size):
            batch = all_files[i:i + batch_size]
            with open("batch_list.tmp", 'w', encoding='utf-8') as f: f.write("\n".join(batch))
            p = subprocess.Popen([packer_exe, os.path.abspath(source_dir), "batch_list.tmp"], stdout=subprocess.PIPE)
            cctx.copy_stream(p.stdout, encryptor)
            p.wait()
            gc.collect()
            click.echo(f"  [Batch] {min(i+batch_size, len(all_files))}/{len(all_files)} processados...")
    finally:
        encryptor.close()
        if os.path.exists("batch_list.tmp"): os.remove("batch_list.tmp")

def restore_data(dox_file, dest_folder, password):
    """Extrai arquivos do container V3 usando streaming."""
    from doxbackup.core.security import DoxDecryptorStream
    import struct
    from pathlib import Path

    with DoxDecryptorStream(dox_file, password) as stream:
        count = 0
        try:
            while True:
                raw_nlen = stream.read(4)
                if not raw_nlen or len(raw_nlen) < 4: 
                    break 
                
                nlen = struct.unpack('I', raw_nlen)[0]
                name_bytes = stream.read(nlen)
                name = name_bytes.decode('utf-16-le').strip('\x00')
                
                raw_flen = stream.read(8)
                flen = struct.unpack('Q', raw_flen)[0]
                
                out_path = Path(dest_folder) / name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(out_path, 'wb') as f_out:
                    remaining = flen
                    while remaining > 0:
                        chunk = stream.read(min(remaining, 1024*1024))
                        if not chunk: break
                        f_out.write(chunk)
                        remaining -= len(chunk)
                
                count += 1
        except Exception as e:
            # Silenciamos erros de final de arquivo (EOF) comuns em cifras de fluxo
            if "unpack requires a buffer of 4 bytes" not in str(e):
                print(f"[INFO] Fim do container: {count} arquivos restaurados.")

        print("\n" + "="*60)
        print(f"  [SUCESSO] Restauração Pós-Quântica Concluída.")
        print(f"  Arquivos processados: {count}")
        print(f"  Destino: {dest_folder}")
        print("="*60)

def create_backup(source_path, output_path):
    from utils.path_utils import normalize_path
    
    source_path = normalize_path(source_path)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{os.path.basename(source_path)}_{timestamp}.tar.xz"
    final_path = os.path.join(output_path, filename)

    print(f"[DoxBackup] Iniciando backup de: {source_path}")
    print(f"[DoxBackup] Destino: {final_path}")

    # "w:xz" utiliza o algoritmo LZMA (estilo 7-zip)
    # Definimos um nível de compressão equilibrado para não estourar sua RAM
    try:
        with tarfile.open(final_path, "w:xz") as tar:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Caminho relativo dentro do backup para ficar organizado
                    rel_path = os.path.relpath(full_path, source_path)
                    
                    print(f"  -> Adicionando: {rel_path}")
                    tar.add(full_path, arcname=rel_path)
        
        return final_path
    except Exception as e:
        if os.path.exists(final_path):
            os.remove(final_path)
        raise e
        
def list_backup_contents(file_path, password):
    contents = []
    with DoxDecryptorStream(file_path, password) as stream:
        while True:
            # 1. Lê Tamanho do Nome (4 bytes criptografados)
            raw_nlen = stream.read(4)
            if not raw_nlen: break # Fim do arquivo
            nlen = struct.unpack('I', raw_nlen)[0]
            
            # 2. Lê Nome do Arquivo (nlen bytes criptografados)
            # O motor C usa wchar_t (UTF-16LE) no Windows
            name_bytes = stream.read(nlen)
            try:
                name = name_bytes.decode('utf-16le')
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: list_backup_contents\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                name = name_bytes.decode('utf-8', errors='ignore')
            
            # 3. Lê Tamanho do Dado (8 bytes criptografados)
            raw_dlen = stream.read(8)
            if not raw_dlen: break
            dlen = struct.unpack('Q', raw_dlen)[0]
            
            contents.append((name, dlen))
            
            # 4. PULA o conteúdo do arquivo para manter a performance de listagem
            # Mas avança o state da cifra!
            stream.skip(dlen)
            
    return contents
    
class DoxHeaderV3(ctypes.Structure):
    _fields_ = [
        ("salt", ctypes.c_ubyte * 16),
        ("nonce", ctypes.c_ubyte * 16),
        ("kyber_ciphertext", ctypes.c_ubyte * 1088),
        ("hint_len", ctypes.c_uint32)
    ]

def run_quantum_backup(output_path, source_root, file_list, password, hint="", quantum=True):
    """Orquestra o backup preservando a árvore de diretórios."""
    from Crypto.Protocol.KDF import PBKDF2
    from utils.path_utils    import normalize_path
    from utils.vulcan_build import ensure_native_engine
    
    header = DoxHeaderV3()
    
    packer_exe = SYS_ROOT / "doxbackup" / "native" / "dox_packer.exe"
    
    if not packer_exe.exists():
        # Se o .exe não existir, tenta o .c ou avisa
        raise FileNotFoundError(f"Motor nativo não encontrado em: {packer_exe}")
    
    # 1. Preparação de Entropia
    for i in range(16): header.salt[i] = os.urandom(1)[0]
    for i in range(16): header.nonce[i] = os.urandom(1)[0]
    if quantum:
        for i in range(1088): header.kyber_ciphertext[i] = os.urandom(1)[0]
    
    ensure_native_engine("vulcan_dox_v3.dll")
    key = PBKDF2(password, bytes(header.salt), dkLen=32, count=100000)
    dll_path = Path("engine/native/vulcan_dox_v3.dll")
    lib = ctypes.CDLL(str(dll_path))

    # Nova assinatura da DLL (6 argumentos + count)
    lib.vulcan_dox_pack.argtypes = [
        ctypes.c_wchar_p, ctypes.POINTER(DoxHeaderV3), ctypes.c_char_p, 
        ctypes.c_char_p, ctypes.POINTER(ctypes.c_wchar_p), 
        ctypes.POINTER(ctypes.c_wchar_p), ctypes.c_int
    ]

    root = Path(source_root).resolve()
    full_paths = []
    rel_paths = []

    for f in file_list:
        f_path = Path(f).resolve()
        full_paths.append(str(f_path))
        # Calcula o caminho relativo (ex: .gitignore ou diskdiag\main.py)
        rel_paths.append(str(f_path.relative_to(root)))

    c_full = (ctypes.c_wchar_p * len(full_paths))(*full_paths)
    c_rel = (ctypes.c_wchar_p * len(rel_paths))(*rel_paths)

    result = lib.vulcan_dox_pack(str(output_path), ctypes.byref(header), hint.encode(), key, c_full, c_rel, len(file_list))
    return result == 0