# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/aegis/nexus_db.py
"""
Nexus Safe DB - Aegis Layer para SQLite3.
Proteção contra Injeção e Auditoria de Comandos Críticos.
"""
import sqlite3 as real_sqlite3  # noqa
import logging

# Exporta as exceções padrão para manter compatibilidade com código que usa sqlite3
Error = real_sqlite3.Error
OperationalError = real_sqlite3.OperationalError
IntegrityError = real_sqlite3.IntegrityError
DatabaseError = real_sqlite3.DatabaseError
ProgrammingError = real_sqlite3.ProgrammingError
Row = real_sqlite3.Row

class AegisCursor:
    """Cursor blindado contra comandos destrutivos não autorizados."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, parameters=()):
        # Nexus Policy: Bloqueio de comandos que podem comprometer a integridade estrutural
        forbidden = ['DROP TABLE', 'TRUNCATE', 'ATTACH DATABASE', 'DETACH DATABASE']
        sql_upper = sql.upper()
        
        for cmd in forbidden:
            if cmd in sql_upper:
                logging.error(f"Aegis DB Block: Tentativa de executar comando proibido: {cmd}")
                raise PermissionError(f"Aegis DB Firewall: O comando '{cmd}' foi bloqueado por política de segurança.")
        
        return self._cursor.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)

class AegisConnection:
    """Conexão monitorada pela camada Aegis."""
    def __init__(self, conn):
        self._conn = conn

    # Permite que o row_factory seja definido na conexão real
    @property
    def row_factory(self):
        return self._conn.row_factory
    
    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def cursor(self):
        return AegisCursor(self._conn.cursor())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def connect(*args, **kwargs):
    """Fábrica de conexão segura Nexus."""
    # Garante que check_same_thread seja False para compatibilidade com ambiente multithread do Doxoade
    if 'check_same_thread' not in kwargs:
        kwargs['check_same_thread'] = False
        
    conn = real_sqlite3.connect(*args, **kwargs)
    return AegisConnection(conn)

def __getattr__(name):
    """Proxy para constantes do sqlite3 (ex: sqlite3.PARSE_DECLTYPES)"""
    return getattr(real_sqlite3, name)
