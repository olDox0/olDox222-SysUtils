import click
import os
import gc
import psutil
import struct
import subprocess
import tarfile
import time
import zstandard as zstd

from doxbackup.core.security import encrypt_file_stream, decrypt_file_stream, DoxEncryptor, DoxDecryptorStream, get_hint_from_file
from utils.path_utils        import normalize_path

IGNORE_FOLDERS = {
    'venv', '.venv', 'node_modules', '.git', 'thirdparty', 
    'models', 'zim', 'index', 'Audio', 'Video', 
    'bin', 'obj', '.vs', 'dist', 'build', 'tests', 'egg-info'
    '.tmp.driveupload', '.dropbox.cache', '.sync',
    'env', '__pycache__', 'tmp', 'temp', '.cache',
    '.doxoade', '.doxoade_cache', '.pytest_cache', '.orn', 'nppbackup',
}

# EXTENSÕES QUE NÃO DEVEM SER COMPRIMIDAS (OU SÃO LIXO)
IGNORE_EXT = {
    # Binários e Pesados
    '.gguf', '.zim', '.db', '.sqlite', '.exe', '.dll', '.bin', '.dox',
    '.wav', '.mp4', '.avi', '.mp3', '.xcf', '.pdn', '.iso',
    # Documentos que "engordam" o backup
    '.doc', '.pdf', '.pptx', '.download',
    #'.rtf', '.docx',
    '.bak', '.bkp', '.log', '.tmp', '.jsonl', '.xml', '.pyc', '.pyd', '.pyx', '.obj', # Lixo de sistema/temp
}

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
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_FOLDERS and not d.lower().endswith('.egg-info')]
        for f in files:
            if any(f.lower().endswith(ext) for ext in IGNORE_EXT): continue
            fp = os.path.join(root, f)
            if timestamp > 0:
                try:
                    mtime = os.path.getmtime(fp)
                    if int(mtime * 10000000 + 116444736000000000) <= timestamp: continue
                except: continue
            valid_files.append(fp)
    return valid_files

def backup_data(source_dir, output_file, password, timestamp=0, hint=""):
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
    contents = []
    dctx = zstd.ZstdDecompressor()
    with DoxDecryptorStream(source_file, password) as ds:
        with dctx.stream_reader(ds) as stream:
            while True:
                raw = stream.read(4)
                if not raw or len(raw) < 4: break
                nlen = struct.unpack('I', raw)[0]
                path = stream.read(nlen).decode('utf-8', errors='ignore')
                dlen = struct.unpack('Q', stream.read(8))[0]
                contents.append((path, dlen))
                # Pulo rápido
                to_skip = dlen
                while to_skip > 0:
                    chunk = stream.read(min(to_skip, 1024*1024))
                    if not chunk: break
                    to_skip -= len(chunk)
    return contents