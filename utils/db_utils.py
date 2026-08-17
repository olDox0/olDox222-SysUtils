# doxoade/doxoade/tools/db_utils.py
"""
Utilitários de Banco de Dados com Persistência Assíncrona.
Resolve o gargalo de latência (Hot Line) via Async Buffer Pattern.
"""
import threading
import queue
import os
# [DOX-UNUSED] import sys
import hashlib
from pathlib import Path

from doxoade.core_database import get_db_connection
from .git import _get_git_commit_hash 

_LOG_QUEUE = queue.Queue()
_WORKER_THREAD = None
_HADES_QUEUE = queue.Queue(maxsize=1000)
_STOP_EVENT = threading.Event()

def _db_worker():
    from doxoade.core_database import get_db_connection
    import time
    time.sleep(0.5) 
    conn = get_db_connection()
    
    try:
        conn.execute("SELECT 1 FROM events LIMIT 1")
    except Exception:
        # Se as tabelas não existem, o worker aguarda ou encerra
        conn.close()
        return
    
    conn.execute("PRAGMA busy_timeout = 10000") 
#    conn.execute("PRAGMA busy_timeout = 20000") 
    cursor = conn.cursor()
    batch_buffer = []
    while not _STOP_EVENT.is_set() or not _LOG_QUEUE.empty():
        try:
            item = _LOG_QUEUE.get(timeout=0.5)
            if item is None:
                break
            batch_buffer.append(item)
            if len(batch_buffer) >= 50:
                for query, params in batch_buffer:
                    cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
        except queue.Empty:
            if batch_buffer:
                for query, params in batch_buffer:
                    cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
            continue
    if batch_buffer:
        for query, params in batch_buffer:
            cursor.execute(query, params)
        conn.commit()
    conn.close()

def start_persistence_worker():
    global _WORKER_THREAD
    if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
        _STOP_EVENT.clear()
        _WORKER_THREAD = threading.Thread(target=_db_worker, daemon=True)
        _WORKER_THREAD.start()

def stop_persistence_worker():
    """Garante o sepultamento dos logs antes do encerramento do processo."""
    global _WORKER_THREAD
    if _WORKER_THREAD:
        _STOP_EVENT.set()
        _LOG_QUEUE.put(None)
        _WORKER_THREAD.join(timeout=3.0)
        _WORKER_THREAD = None

def _log_execution(command_name, path, results, arguments, execution_time_ms, exit_code=0, payload=None):
    """Gravador Mestre: Sincroniza Findings (Events) e Timeline (History)."""
    start_persistence_worker() 
    
    from datetime import datetime, timezone
    import json
    import uuid
    import sys

    _ts = datetime.now(timezone.utc).isoformat()
    _p_abs = os.path.abspath(path)
    _session = uuid.uuid4().hex
    _full_cmd = "doxoade " + " ".join(sys.argv[1:])

    # 1. Grava na tabela EVENTS (Para o sistema de Findings/History)
    # Retornamos o ID para que o findings_arena ou logger possa associar
    _query_events = '''
        INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status)
        VALUES (?, ?, ?, ?, ?, ?)
    '''
    _params_events = (_ts, "85.2", command_name, _p_abs, execution_time_ms, "completed")
    
    # 2. Grava na tabela COMMAND_HISTORY (Para a Timeline/Arqueologia)
    _query_hist = '''
        INSERT INTO command_history 
        (session_uuid, timestamp, command_name, full_command_line, working_dir, 
         exit_code, duration_ms, system_info, compressed_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    _sys_info = json.dumps({"args": arguments, "summary": results.get('summary', {})})
    _params_hist = (_session, _ts, command_name, _full_cmd, _p_abs, exit_code, execution_time_ms, _sys_info, payload)

    # Envia ambos para a fila de persistência
    _LOG_QUEUE.put((_query_events, _params_events))
    _LOG_QUEUE.put((_query_hist, _params_hist))

def _update_open_incidents(findings, project_path):
    """Sincroniza o estado atual do linter com o banco de dados."""
    if not isinstance(findings, list): return
    
    from doxoade.core_database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    project_path_abs = os.path.abspath(project_path)
    
    # [PLATINUM] Captura o Hash atual para satisfazer a constraint do banco
    current_git_hash = _get_git_commit_hash(project_path_abs) or "local"

    current_hashes = [f.get('finding_hash') for f in findings if isinstance(f, dict) and f.get('finding_hash')]
    
    # Limpa incidentes resolvidos
    if current_hashes:
        placeholders = ', '.join(['?'] * len(current_hashes))
        cursor.execute(f'DELETE FROM open_incidents WHERE project_path = ? AND finding_hash NOT IN ({placeholders})', (project_path_abs, *current_hashes))
    else:
        cursor.execute('DELETE FROM open_incidents WHERE project_path = ?', (project_path_abs,))

    from datetime import datetime, timezone
    for f in findings:
        if not isinstance(f, dict) or not f.get('finding_hash'): continue
        
        # [FIX] Query atualizada com commit_hash para evitar IntegrityError
        cursor.execute('''
            INSERT OR REPLACE INTO open_incidents 
            (finding_hash, file_path, line, message, severity, category, project_path, timestamp, commit_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['finding_hash'], f.get('file'), f.get('line'), 
            f.get('message'), f.get('severity'), f.get('category'), 
            project_path_abs, datetime.now(timezone.utc).isoformat(),
            current_git_hash
        ))
    conn.commit()
    conn.close()
    
def encrypt_payload(data_bytes, password):
    # Lógica simplificada de XOR com Hash para manter Silo sem dependências externas (como cryptography)
    # Para segurança máxima profissional, o ideal seria 'pip install cryptography'
    key = hashlib.sha256(password.encode()).digest()
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data_bytes)])

def _hades_worker():
    """Trabalhador de background que limpa o buffer de memória."""
    while not _STOP_EVENT.is_set():
        try:
            # Pega um lote de até 50 registros para gravar de uma vez (Efficiency)
            batch = []
            try:
                while len(batch) < 50:
                    item = _HADES_QUEUE.get(timeout=1.0)
                    if item is None: break
                    batch.append(item)
            except queue.Empty: pass

            if batch:
                conn = get_db_connection()
                for sql, params in batch:
                    conn.execute(sql, params)
                conn.commit()
                conn.close()
        except Exception: pass

# Inicia o worker automaticamente
threading.Thread(target=_hades_worker, daemon=True).start()

def async_db_exec(sql, params=()):
    """Joga o comando no buffer e libera a CPU imediatamente."""
    try:
        _HADES_QUEUE.put_nowait((sql, params))
    except queue.Full:
        # Se o buffer lotar (disco muito lento), cai para modo síncrono
        conn = get_db_connection()
        conn.execute(sql, params)
        conn.commit()
        conn.close()

def chief_heartbeat(subsystem: str, action: str, details: dict):
    """Grava telemetria. Síncrono em modo HORUS para evitar perda de dados."""
    import json, os
    from datetime import datetime
    from doxoade.core_database import get_db_connection
    
    data_payload = json.dumps(details, ensure_ascii=False)
    
    # [PLATINUM] Se o Horus está vigiando, grava imediatamente
    if os.environ.get('DOXOADE_HORUS_ACTIVE') == '1' or subsystem == 'HORUS':
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO operational_logs (timestamp, subsystem, action, data, pid)
                VALUES (?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), subsystem.upper(), action.upper(), data_payload, os.getpid()))
            conn.commit()
            conn.close()
            return
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f"[INFRA] chief_heartbeat: {e}")

    # Fluxo normal assíncrono
    from .db_utils import _LOG_QUEUE # Referência circular guard
    _query = 'INSERT INTO operational_logs (timestamp, subsystem, action, data, pid) VALUES (?, ?, ?, ?, ?)'
    _params = (datetime.now().isoformat(), subsystem.upper(), action.upper(), data_payload, os.getpid())
    _LOG_QUEUE.put((_query, _params))

# No momento de gravar:
#if vault_is_active:
#    final_blob = encrypt_payload(compressed_data, current_session_password)
#else:
#    final_blob = compressed_data # Ou bloqueia a gravação

def check_alexandria_compliance(file_path: Path):
    """Gatilho silencioso: se o arquivo usa sqlite3 direto, dispara um aviso ou refatora."""
    if is_violating_policy(file_path):
        # Aqui podemos chamar o refactorer de forma inteligente
        alexandria_refactor(file_path, dry_run=False)
