"""Setup script for Qlib Crypto Trading Platform"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="qlib-crypto-platform",
    version="1.0.0",
    description="AI-powered cryptocurrency trading platform built on Microsoft Qlib",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/qlib-crypto-platform",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pyqlib>=0.9.5",
        "numpy>=1.23.0",
        "pandas>=1.5.0",
        "ccxt>=4.0.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "mcp>=0.1.0",
        "torch>=2.0.0",
        "scikit-learn>=1.2.0",
        "lightgbm>=3.3.5",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "qlib-crypto-api=ui.api:main",
            "qlib-crypto-mcp=mcp_server.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="cryptocurrency trading machine-learning qlib ai backtesting",
)
