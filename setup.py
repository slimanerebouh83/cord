from setuptools import setup, find_packages

setup(
    name="cord-cli",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "rich>=13.0.0",
        "prompt-toolkit>=3.0.30",
        "httpx>=0.24.0",
    ],
    entry_points={
        "console_scripts": [
            "cord=cord.main:main",
        ],
    },
)
