# -*- coding: utf-8 -*-
# diskdiag/core/vulcan_dict.py
import zlib

def train_dictionary(corpus_list):
    """Gera um blob de dicionario fixo (Deterministico)."""
    if not corpus_list: return b""
    unified = b" ".join(s.encode('utf-8', errors='ignore') for s in corpus_list)
    return unified[:4000]

def compress_to_binary(data, dictionary):
    """Compacta para binario puro (Raw Deflate)."""
    co = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15, zdict=dictionary)
    return co.compress(data.encode('utf-8', errors='ignore')) + co.flush()

def decompress_from_binary(compressed_bytes, dictionary):
    """Descompacta de binario bruto."""
    try:
        do = zlib.decompressobj(wbits=-15, zdict=dictionary)
        return do.decompress(compressed_bytes).decode('utf-8', errors='ignore')
    except Exception as e:
        return f"[VULCAN_FAIL: {str(e)[:10]}]"
