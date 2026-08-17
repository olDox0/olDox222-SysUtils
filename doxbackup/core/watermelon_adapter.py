# -*- coding: utf-8 -*-
# doxbackup/core/watermelon_adapter.py
"""
DCT1 Watermelon Backup Adapter
Adaptador seguro para ler o backup .dox atual sem acoplar o Fidelity ao formato interno.
"""
from __future__ import annotations
import inspect
from pathlib import Path

def _call_list(func, backup_file, password):
    try:
        sig = inspect.signature(func)
    except Exception:
        return func(str(backup_file))
    
    names = sig.parameters
    if "password" in names:
        try: return func(str(backup_file), password=password)
        except TypeError: pass
    try: return func(str(backup_file))
    except TypeError as exc:
        raise RuntimeError("Ajuste o watermelon_adapter.py para a assinatura real do list_backup_contents.") from exc

def _call_restore(func, backup_file, dest_dir, password):
    try:
        sig = inspect.signature(func)
    except Exception:
        return func(str(backup_file), str(dest_dir))
        
    names = sig.parameters
    dest_keywords = ("dest", "dest_dir", "destination", "output_dir", "target", "restore_dir", "path", "out_dir")
    
    for dest_kw in dest_keywords:
        if dest_kw in names:
            kwargs = {dest_kw: str(dest_dir)}
            if "password" in names: kwargs["password"] = password
            try: return func(str(backup_file), **kwargs)
            except TypeError: pass
            
    if "password" in names:
        try: return func(str(backup_file), str(dest_dir), password=password)
        except TypeError: pass
        
    try: return func(str(backup_file), str(dest_dir))
    except TypeError as exc:
        raise RuntimeError("Ajuste o watermelon_adapter.py para a assinatura real do restore_data.") from exc

class DoxBackupAdapter:
    def __init__(self, backup_file, password=None):
        self.backup_file = str(backup_file)
        self.password = password

    def list_entries(self):
        from doxbackup.core.engine import list_backup_contents
        return _call_list(list_backup_contents, self.backup_file, self.password)

    def extract_all(self, dest_dir):
        from doxbackup.core.engine import restore_data
        _call_restore(restore_data, self.backup_file, dest_dir, self.password)
        return Path(dest_dir)