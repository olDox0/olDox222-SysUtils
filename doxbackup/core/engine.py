import psutil
import os
import struct
import subprocess
import tarfile
import time
import zstandard as zstd

from doxbackup.core.security import encrypt_file_stream, decrypt_file_stream
from utils.path_utils        import normalize_path

IGNORE_LIST = {
    'venv', '.venv', 'env', '__pycache__', '.git', 
    'node_modules', 'tmp', 'temp', '.cache',
    'dist', 'build', 'nppbackup' # Adicionado nppbackup
}

def should_skip(path):
    name = os.path.basename(path).lower()
    if name.endswith('.bak'): return True
    parts = path.lower().split(os.sep)
    return any(p in IGNORE_LIST for p in parts)

def backup_data_native(source_dir, output_file, password, progress_callback=None):
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
    except:
        available_ram = 500
    if available_ram < 400:
        return {"level": 5, "threads": 1, "ldm": False, "buf_size": 512*1024}
    return {"level": 10, "threads": -1, "ldm": True, "buf_size": 1024 * 1024}

def backup_data(source_dir, output_file, password):
    params = get_ram_optimized_params()
    temp_compressed = output_file + ".tmp"
    
    # Localização do executável Native (Híbrido Python/Vulcan)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    packer_exe = os.path.abspath(os.path.join(current_file_dir, "..", "native", "dox_packer.exe"))
    if not os.path.exists(packer_exe):
        packer_exe = os.path.join(os.getcwd(), "doxbackup", "native", "dox_packer.exe")

    if params["ldm"]:
        c_params = zstd.ZstdCompressionParameters.from_level(
            params["level"], threads=params["threads"], enable_ldm=True, ldm_hash_log=17
        )
        cctx = zstd.ZstdCompressor(compression_params=c_params)
    else:
        cctx = zstd.ZstdCompressor(level=params["level"], threads=params["threads"])

    packer_proc = subprocess.Popen(
        [packer_exe, os.path.abspath(source_dir)], 
        stdout=subprocess.PIPE, 
        bufsize=params["buf_size"]
    )

    with open(temp_compressed, 'wb') as f_out:
        cctx.copy_stream(packer_proc.stdout, f_out)

    packer_proc.wait()
    encrypt_file_stream(temp_compressed, output_file, password)
    if os.path.exists(temp_compressed): os.remove(temp_compressed)

def restore_data(source_file, dest_dir, password):
    temp_decrypted = source_file + ".dec"
    decrypt_file_stream(source_file, temp_decrypted, password)

    dctx = zstd.ZstdDecompressor()
    with open(temp_decrypted, 'rb') as f_in:
        with dctx.stream_reader(f_in) as stream:
            while True:
                raw_name_len = stream.read(4)
                if not raw_name_len: break
                
                name_len = struct.unpack('I', raw_name_len)[0]
                path = stream.read(name_len).decode('utf-8', errors='ignore')
                
                raw_data_len = stream.read(8)
                if not raw_data_len: break
                data_len = struct.unpack('Q', raw_data_len)[0]
                
                full_path = os.path.join(dest_dir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # --- TRATAMENTO DE PERMISSÃO ---
                try:
                    with open(full_path, 'wb') as f_out:
                        remaining = data_len
                        while remaining > 0:
                            chunk = stream.read(min(remaining, 128 * 1024))
                            if not chunk: break
                            f_out.write(chunk)
                            remaining -= len(chunk)
                except PermissionError:
                    print(f"  [AVISO] Ignorado por falta de permissão: {path}")
                    # Importante: Mesmo ignorando a escrita, PRECISAMOS ler os bytes 
                    # do stream para não dessincronizar o cabeçalho do próximo arquivo
                    remaining = data_len
                    while remaining > 0:
                        chunk = stream.read(min(remaining, 128 * 1024))
                        if not chunk: break
                        remaining -= len(chunk)
                # -------------------------------

    if os.path.exists(temp_decrypted):
        os.remove(temp_decrypted)

def create_backup(source_path, output_path):
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
        
def list_backup_contents(source_file, password):
    temp_decrypted = source_file + ".dec"
    decrypt_file_stream(source_file, temp_decrypted, password)
    contents = []
    dctx = zstd.ZstdDecompressor()
    try:
        with open(temp_decrypted, 'rb') as f_in:
            with dctx.stream_reader(f_in) as stream:
                while True:
                    raw_name_len = stream.read(4)
                    if not raw_name_len: break
                    name_len = struct.unpack('I', raw_name_len)[0]
                    path = stream.read(name_len).decode('utf-8', errors='ignore')
                    raw_data_len = stream.read(8)
                    data_len = struct.unpack('Q', raw_data_len)[0]
                    contents.append((path, data_len))
                    bytes_to_skip = data_len
                    while bytes_to_skip > 0:
                        chunk = stream.read(min(bytes_to_skip, 1024*1024))
                        if not chunk: break
                        bytes_to_skip -= len(chunk)
    finally:
        if os.path.exists(temp_decrypted): os.remove(temp_decrypted)
    return contents