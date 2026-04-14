from setuptools import setup, find_packages

setup(
    name="sysutils",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "psutil",
    ],
    entry_points={
        "console_scripts": [
            "sysutils=cli.main:cli",      # Comando principal
            "diskdiag=cli.main:diskdiag", # Atalho opcional
        ],
    },
)