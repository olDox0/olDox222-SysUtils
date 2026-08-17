# doxbackup/core/dct1.py
"""
DCT1 — Domain Context Transform v1
Perfil de compressão extrema lossless para DoxBackup.
"""

from dataclasses import dataclass
# [DOX-UNUSED] from pathlib import Path

try:
    import zstandard as zstd
except ImportError:
    zstd = None


DCT1_VERSION = "DCT1.0"


DCT1_DICT_GROUPS = {
    "python": {
        ".py",
    },

    "native": {
        ".c",
        ".h",
    },

    "docs": {
        ".md",
        ".txt",
        ".rst",
    },

    "config": {
        ".toml",
        ".ini",
        ".cfg",
        ".json",
        ".yaml",
        ".yml",
    },
}


DCT1_STORE_ONLY = {
    # Binários executáveis
    ".dll",
    ".exe",
    ".pyd",
    ".obj",
    ".so",
    ".bin",

    # Já compactados
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".7z",
    ".rar",
    ".zst",

    # Mídia
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mkv",

    # Containers/bancos
    ".db",
    ".sqlite",
    ".sqlite3",
    ".dox",
    ".iso",
    ".whl",
    ".gguf",
    ".zim",

    # Lixo temporário
    ".tmp",
    ".temp",
    ".bak",
    ".old",
    ".log",
}


@dataclass
class DCT1Profile:
    version: str
    level: int
    threads: int
    enable_ldm: bool
    window_log: int
    use_dictionaries: bool
    extreme: bool


def get_dct1_profile(extreme: bool = False) -> DCT1Profile:
    """
    Retorna o perfil DCT1.

    extreme=False:
      perfil forte, porém mais seguro para máquinas modestas.

    extreme=True:
      perfil máximo, para compressão extrema, exige mais RAM/CPU.
    """
    if extreme:
        return DCT1Profile(
            version=DCT1_VERSION,
            level=22,
            threads=1,
            enable_ldm=True,
            window_log=27,
            use_dictionaries=True,
            extreme=True
        )

    return DCT1Profile(
        version=DCT1_VERSION,
        level=19,
        threads=1,
        enable_ldm=True,
        window_log=25,
        use_dictionaries=True,
        extreme=False
    )


def get_dct1_zstd_params(extreme: bool = False):
    """
    Retorna parâmetros ZSTD para DCT1.
    """
    if zstd is None:
        raise RuntimeError("zstandard não está instalado.")

    profile = get_dct1_profile(extreme=extreme)

    return zstd.ZstdCompressionParameters.from_level(
        profile.level,
        threads=profile.threads,
        enable_ldm=profile.enable_ldm,
        window_log=profile.window_log
    )


def classify_extension(ext: str) -> str:
    """
    Classifica uma extensão para o DCT1.
    """
    ext = (ext or "").lower()

    if not ext:
        ext = "<sem_ext>"

    if ext in DCT1_STORE_ONLY:
        return "store"

    for group, extensions in DCT1_DICT_GROUPS.items():
        if ext in extensions:
            return group

    return "general"


def should_use_dictionary_for_ext(ext: str) -> bool:
    """
    Diz se vale a pena usar dicionário para essa extensão.
    """
    group = classify_extension(ext)

    return group in DCT1_DICT_GROUPS