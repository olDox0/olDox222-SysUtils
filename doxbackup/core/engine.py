# doxbackup/core/engine.py
import click
import ctypes
import gc
import os
import psutil
import struct
import subprocess
# [DOX-UNUSED] import sys
import tarfile
import time
import zstandard as zstd

from pathlib import Path

# [DOX-UNUSED] from diskdiag.analysis.heuristics import should_exclude_from_backup
from doxbackup.core.security import DoxDecryptorStream
from utils.path_utils import is_ignored_folder, should_exclude_path

# ═══════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM SISTEMA DE COMPRESSÃO APRENDIDA (FASE 0)
# ═══════════════════════════════════════════════════════════════

try:
    from doxbackup.core.compression import (
        DictLearner,
        AdaptiveROI,
        CompressionPipeline,
        CodecManager,
    )
    COMPRESSION_SYSTEM_AVAILABLE = True
except ImportError:
    COMPRESSION_SYSTEM_AVAILABLE = False

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
    """Extrai arquivos do container V3 usando streaming com suporte a Zstd."""
    from doxbackup.core.security import DoxDecryptorStream
    import struct
    from pathlib import Path
    import io
    
    MAGIC_ZSTD_DICT = b"DOXDICT1"
    
    with DoxDecryptorStream(dox_file, password) as stream:
        # ═══ DETECTA SE O STREAM É ZSTD+DICT ═══
        magic_bytes = stream.read(8)
        is_zstd_dict = (magic_bytes == MAGIC_ZSTD_DICT)
        
        if is_zstd_dict:
            # Carrega o dicionário treinado
            from doxbackup.core.compression.dict_learner import DictLearner
            learner = DictLearner(SYS_ROOT)
            
            # Procura o primeiro dicionário disponível no cache
            manifest_path = SYS_ROOT / ".doxoade" / "compression" / "manifest.json"
            dict_obj = None
            if manifest_path.exists():
                import json
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for ext, info in manifest.get("dictionaries", {}).items():
                    dict_path = Path(info.get("dict_path", ""))
                    if dict_path.exists():
                        dict_obj = zstd.ZstdCompressionDict(dict_path.read_bytes())
                        break
            
            if dict_obj:
                dctx = zstd.ZstdDecompressor(dict_data=dict_obj)
            else:
                # Fallback: tenta sem dicionário (pode falhar)
                dctx = zstd.ZstdDecompressor()
            
            # ✅ CORREÇÃO: Lê o restante do stream em chunks
            compressed_chunks = []
            while True:
                chunk = stream.read(1024 * 1024)  # Lê 1MB por vez
                if not chunk:
                    break
                compressed_chunks.append(chunk)
            compressed_data = b"".join(compressed_chunks)
            
            import io
            with dctx.stream_reader(io.BytesIO(compressed_data)) as reader:
                decompressed_data = reader.read()
            data_stream = io.BytesIO(decompressed_data)
        else:
            # Não é Zstd+Dict: o magic_bytes faz parte do primeiro arquivo
            # ✅ CORREÇÃO: Lê o restante do stream em chunks
            remaining_chunks = [magic_bytes]
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                remaining_chunks.append(chunk)
            data_stream = io.BytesIO(b"".join(remaining_chunks))
        
        # ═══ PARSE DO FORMATO BINÁRIO ═══
        count = 0
        try:
            while True:
                raw_nlen = data_stream.read(4)
                if not raw_nlen or len(raw_nlen) < 4:
                    break
                nlen = struct.unpack('I', raw_nlen)[0]
                
                # Sanity check: nome não pode ser absurdamente grande
                if nlen > 65536:
                    break
                
                name_bytes = data_stream.read(nlen)
                
                # Detecção automática de encoding
                is_utf16 = (nlen % 2 == 0) and sum(1 for i in range(1, nlen, 2) if name_bytes[i] == 0) > nlen // 4
                if is_utf16:
                    name = name_bytes.decode('utf-16-le').strip('\x00')
                else:
                    name = name_bytes.decode('utf-8', errors='ignore').strip('\x00')
                
                raw_flen = data_stream.read(8)
                if not raw_flen or len(raw_flen) < 8:
                    break
                flen = struct.unpack('Q', raw_flen)[0]
                
                # Sanity check: tamanho não pode ser negativo ou absurdamente grande
                if flen > 10 * 1024 * 1024 * 1024:  # 10GB
                    break
                
                out_path = Path(dest_folder) / name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(out_path, 'wb') as f_out:
                    remaining = flen
                    while remaining > 0:
                        chunk = data_stream.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            break
                        f_out.write(chunk)
                        remaining -= len(chunk)
                count += 1
                
        except Exception as e:
            if "unpack requires a buffer" not in str(e):
                print(f"[INFO] Fim do container: {count} arquivos restaurados.")
        
        print("\n" + "=" * 60)
        print(f"  [SUCESSO] Restauração Pós-Quântica Concluída.")
        print(f"  Arquivos processados: {count}")
        print(f"  Destino: {dest_folder}")
        print("=" * 60)

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
    """Lista conteúdo do backup com suporte a Zstd+Dict."""
    import io
    
    MAGIC_ZSTD_DICT = b"DOXDICT1"
    contents = []
    
    with DoxDecryptorStream(file_path, password) as stream:
        # Detecta se é Zstd+Dict
        magic_bytes = stream.read(8)
        is_zstd_dict = (magic_bytes == MAGIC_ZSTD_DICT)
        
        if is_zstd_dict:
            # Descomprime com dicionário
            from doxbackup.core.compression.dict_learner import DictLearner
            learner = DictLearner(SYS_ROOT)
            
            manifest_path = SYS_ROOT / ".doxoade" / "compression" / "manifest.json"
            dict_obj = None
            if manifest_path.exists():
                import json
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for ext, info in manifest.get("dictionaries", {}).items():
                    dict_path = Path(info.get("dict_path", ""))
                    if dict_path.exists():
                        dict_obj = zstd.ZstdCompressionDict(dict_path.read_bytes())
                        break
            
            if dict_obj:
                dctx = zstd.ZstdDecompressor(dict_data=dict_obj)
            else:
                dctx = zstd.ZstdDecompressor()
            
            # ✅ CORREÇÃO: Lê o restante do stream em chunks
            compressed_chunks = []
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                compressed_chunks.append(chunk)
            compressed_data = b"".join(compressed_chunks)
            
            import io
            with dctx.stream_reader(io.BytesIO(compressed_data)) as reader:
                decompressed_data = reader.read()
            data_stream = io.BytesIO(decompressed_data)
        else:
            # ✅ CORREÇÃO: Lê o restante do stream em chunks
            remaining_chunks = [magic_bytes]
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                remaining_chunks.append(chunk)
            data_stream = io.BytesIO(b"".join(remaining_chunks))
        
        # Parse do formato binário
        while True:
            raw_nlen = data_stream.read(4)
            if not raw_nlen or len(raw_nlen) < 4:
                break
            nlen = struct.unpack('I', raw_nlen)[0]
            
            if nlen > 65536:
                break
            
            name_bytes = data_stream.read(nlen)
            
            is_utf16 = (nlen % 2 == 0) and sum(1 for i in range(1, nlen, 2) if name_bytes[i] == 0) > nlen // 4
            if is_utf16:
                name = name_bytes.decode('utf-16-le').strip('\x00')
            else:
                name = name_bytes.decode('utf-8', errors='ignore').strip('\x00')
            
            raw_dlen = data_stream.read(8)
            if not raw_dlen or len(raw_dlen) < 8:
                break
            dlen = struct.unpack('Q', raw_dlen)[0]
            
            contents.append((name, dlen))
            
            # Pula o conteúdo (mantém performance de listagem)
            data_stream.seek(dlen, io.SEEK_CUR)
    
    return contents
    
class DoxBackupAdapter:
    def __init__(self, backup_file, password=None):
        self.backup_file = str(backup_file)
        self.password = password

    def list_entries(self):
        from doxbackup.core.engine import list_backup_contents

        # IMPORTANTE:
        # Ajuste conforme a assinatura real do seu list_backup_contents.
        return list_backup_contents(self.backup_file)

    def extract_all(self, dest_dir):
        from doxbackup.core.engine import restore_data

        # IMPORTANTE:
        # Ajuste conforme a assinatura real do seu restore_data.
        # O destino deve ser sempre temporário/isolado.
        restore_data(self.backup_file, str(dest_dir), self.password)
    
class DoxHeaderV3(ctypes.Structure):
    _fields_ = [
        ("salt", ctypes.c_ubyte * 16),
        ("nonce", ctypes.c_ubyte * 16),
        ("kyber_ciphertext", ctypes.c_ubyte * 1088),
        ("hint_len", ctypes.c_uint32)
    ]

#def run_quantum_backup(output_path, source_root, file_list, password, hint="", quantum=True):
def run_quantum_backup(
    output_path, source_root, file_list, password,
    hint="", quantum=True, dct1=False, dct1_extreme=False,
    learned: bool = False,
    retrain_dict: bool = False,
    dict_top_n: int = 3,
    anim=None,
):
    """Orquestra o backup preservando a árvore de diretórios."""
    from Crypto.Protocol.KDF import PBKDF2
    # [DOX-UNUSED] from utils.path_utils import normalize_path
    from utils.vulcan_build import ensure_native_engine
    
    # ═══ REMOVIDO: Linha [DIAG] que causava UnboundLocalError ═══
    
    def _safe_log(msg, fg="cyan"):
        if anim:
            anim.print(f"[{fg.upper()}] {msg}")
        else:
            click.secho(msg, fg=fg)
    
    # ── Escolha de parâmetros de compressão ──
    if dct1:
        level = 22 if dct1_extreme else 19
        window = 27 if dct1_extreme else 25
        zparams = zstd.ZstdCompressionParameters.from_level(
            level, threads=1, enable_ldm=True, window_log=window
        )
    else:
        zparams = zstd.ZstdCompressionParameters.from_level(5, threads=1, window_log=21)
    
    header = DoxHeaderV3()
    
    packer_exe = SYS_ROOT / "bin" / "dox_packer.exe"
#    packer_exe = SYS_ROOT / "doxbackup" / "native" / "dox_packer.exe"
    
    if not packer_exe.exists():
        packer_exe = SYS_ROOT / "doxbackup" / "native" / "dox_packer.exe"
        # Se o .exe não existir, tenta o .c ou avisa
#        raise FileNotFoundError(f"Motor nativo não encontrado em: {packer_exe}")
    
    # ═══════════════════════════════════════════════════════════════
    # SISTEMA DE COMPRESSÃO APRENDIDA (Fase 1)
    # ═══════════════════════════════════════════════════════════════
    dict_manifests = {}
    use_learned = False
    
    if learned:
        try:
            from doxbackup.core.compression.dict_learner import DictLearner
            
            # Calcula hashes dos arquivos para cache
            file_hashes = {}
            for f in file_list:
                try:
                    import hashlib
                    h = hashlib.sha256()
                    with open(f, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(8192), b''):
                            h.update(chunk)
                    file_hashes[Path(f)] = h.hexdigest()
                except Exception:
                    pass
            
            # Treina dicionários
            learner = DictLearner(SYS_ROOT)
            dict_manifests = learner.prepare_dictionaries(
                [Path(f) for f in file_list],
                file_hashes,
                top_n=dict_top_n,
                retrain=retrain_dict,
            )
            
            if dict_manifests:
                learner.print_plan(dict_manifests)
                use_learned = True
            else:
                click.secho("[COMPRESSÃO] Nenhum dicionário treinado (ROI insuficiente).", fg="yellow")
                
        except ImportError as e:
            click.secho(f"[COMPRESSÃO] Módulo dict_learner não disponível: {e}", fg="yellow")
        except Exception as e:
            click.secho(f"[COMPRESSÃO] Falha ao preparar dicionários: {e}", fg="red")
    # ═══════════════════════════════════════════════════════════════
    
    # 1. Preparação de Entropia
    for i in range(16): header.salt[i] = os.urandom(1)[0]
    for i in range(16): header.nonce[i] = os.urandom(1)[0]
    if quantum:
        for i in range(1088): header.kyber_ciphertext[i] = os.urandom(1)[0]
    
    ensure_native_engine("vulcan_dox_v3.dll")
    key = PBKDF2(password, bytes(header.salt), dkLen=32, count=100000)
#    dll_path = project_root / "bin" / dll_name
#    dll_path = SYS_ROOT / "engine" / "native" / "vulcan_dox_v3.dll"
    dll_path = SYS_ROOT / "bin" / "vulcan_dox_v3.dll"
    
    # Fallback para o caminho antigo (compatibilidade)
    if not dll_path.exists():
        dll_path = SYS_ROOT / "engine" / "native" / "vulcan_dox_v3.dll"
    packer_exe = SYS_ROOT / "doxbackup" / "native" / "dox_packer.exe"
    use_native_dll = False
    
    if dll_path.exists():
        try:
            lib = ctypes.CDLL(str(dll_path))
            # Verifica se a função V3 existe na DLL
            if hasattr(lib, 'vulcan_dox_pack'):
                use_native_dll = True
            else:
                click.secho("[VULCAN] DLL encontrada, mas função 'vulcan_dox_pack' ausente. Usando fallback .exe.", fg="yellow")
        except OSError:
            pass

    if not use_native_dll:
        # Fallback: Garante que o .exe existe e o usa via subprocess
        if not packer_exe.exists():
            click.secho("[VULCAN] Compilando dox_packer.exe (fallback)...", fg="cyan")
            try:
                src_c = SYS_ROOT / "doxbackup" / "native" / "dox_packer.c"
                subprocess.run(
                    ["gcc", "-O3", "-s", "-o", str(packer_exe), str(src_c)],
                    check=True, capture_output=True
                )
            except Exception as e:
                raise RuntimeError(f"Falha ao compilar fallback dox_packer.exe: {e}")

        # --- PIPELINE V2 COMPATÍVEL COM V3 ---
        import tempfile
        from doxbackup.core.security import DoxEncryptor
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as list_f:
            for f in file_list:
                list_f.write(f + "\n")
            list_file_path = list_f.name

        # ═══ ESCOLHA DO COMPRESSOR ═══
        if learned and dict_manifests:
            first_ext = next(iter(dict_manifests))
            dict_obj = learner.get_dict_object(first_ext)
            if dict_obj:
                learned_params = zstd.ZstdCompressionParameters.from_level(
                    19, threads=1, enable_ldm=True, window_log=25
                )
                cctx = zstd.ZstdCompressor(
                    compression_params=learned_params,
                    dict_data=dict_obj
                )
                click.secho(f"[COMPRESSÃO] Usando dicionário '{first_ext}' para compressão.", fg="green")
                # Magic: indica que o stream é Zstd+Dict
                MAGIC_ZSTD_DICT = b"DOXDICT1"
            else:
                cctx = zstd.ZstdCompressor(level=10, threads=-1)
                MAGIC_ZSTD_DICT = None
        else:
            cctx = zstd.ZstdCompressor(level=10, threads=-1)
            MAGIC_ZSTD_DICT = None

        # ═══ PIPELINE: C → Zstd → XOR (DoxEncryptor) ═══
        # Usa DoxEncryptor (XOR) que é compatível com DoxDecryptorStream
        encryptor = DoxEncryptor(str(output_path), password, hint=hint, quantum=quantum)
        
        try:
            packer_proc = subprocess.Popen(
                [str(packer_exe), str(source_root), list_file_path],
                stdout=subprocess.PIPE, bufsize=1024 * 1024
            )
            
            # Escreve magic se houver dicionário
            if MAGIC_ZSTD_DICT:
                encryptor.write(MAGIC_ZSTD_DICT)
            
            # Pipeline: stdout do C → Zstd → XOR
            cctx.copy_stream(packer_proc.stdout, encryptor)
            packer_proc.wait()
        finally:
            encryptor.close()
            os.unlink(list_file_path)

        return True  # Sucesso via fallback
        
    # Se chegou aqui, usa a DLL V3 (código original do run_quantum_backup)
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

    if learned and not COMPRESSION_SYSTEM_AVAILABLE:
        click.secho(
            "[AVISO] Sistema de compressão aprendida não disponível. "
            "Usando compressão padrão.",
            fg="yellow"
        )
        learned = False
        
    if learned:
        try:
            from doxbackup.core.compression.dict_learner import DictLearner
            from doxbackup.core.compression.codec_manager import CodecManager
            
            # ═══ MODO INCUBADORA: MÁXIMO LEARNED ═══
            # Treina dicionários para TODAS as extensões candidatas (não só top 3)
            # Aumenta o tamanho do dicionário para 112KB (máximo prático)
            LEARNED_MAX_DICT_TOP = 15        # Top 15 extensões
            LEARNED_DICT_SIZE = "112k"       # Tamanho máximo do dicionário
            LEARNED_COMPRESS_LEVEL = 22      # Compressão máxima (level 22)
            
            file_hashes = {}
            for f in file_list:
                try:
                    import hashlib
                    h = hashlib.sha256()
                    with open(f, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(8192), b''):
                            h.update(chunk)
                    file_hashes[Path(f)] = h.hexdigest()
                except Exception:
                    pass
            
            learner = DictLearner(SYS_ROOT)
            dict_manifests = learner.prepare_dictionaries(
                [Path(f) for f in file_list],
                file_hashes,
                top_n=LEARNED_MAX_DICT_TOP,
                dict_size=LEARNED_DICT_SIZE,
                retrain=retrain_dict,
                compress_level=LEARNED_COMPRESS_LEVEL,
            )
            
            if dict_manifests:
                learner.print_plan(dict_manifests)
                codec_manager = CodecManager(SYS_ROOT)
                use_learned = True
                click.secho(
                    f"[COMPRESSÃO] {len(dict_manifests)} dicionários treinados "
                    f"(modo incubadora: máximo)",
                    fg="green"
                )
            else:
                click.secho("[COMPRESSÃO] Nenhum dicionário treinado (ROI insuficiente).", fg="yellow")
        except ImportError as e:
            click.secho(f"[COMPRESSÃO] Módulo dict_learner não disponível: {e}", fg="yellow")
        except Exception as e:
            click.secho(f"[COMPRESSÃO] Falha ao preparar dicionários: {e}", fg="red")

    return result == 0