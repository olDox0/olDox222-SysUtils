# setup.py
from setuptools import setup, find_packages

setup(
    name="sysutils",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "psutil",
        "pycryptodome",
        "zstandard",
        "colorama"
    ],
    entry_points={
        "console_scripts": [
            "sysutils=cli.main:main",
        ],
    },
)