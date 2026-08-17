# setup.py
import os
from setuptools import setup, find_packages

# Lê a lista de dependências diretamente do requirements.txt
requirements = [
    "click>=8.1.0",
    "colorama>=0.4.6",
    "psutil>=5.9.5",
    "pycryptodome>=3.19.0",
    "zstandard>=0.22.0",
]

setup(
    name="sysutils",
    version="3.0.0",
    description="Suíte de Diagnóstico de Sistema, Trim de RAM e Backup Pós-Quântico",
    author="olDox22",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["*.dll", "*.exe", "*.toml"],
    },
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "sysutils=cli.main:main",
        ],
    },
)