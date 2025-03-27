#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="voip_benchmark",
    version="0.1.0",
    description="VoIP Benchmarking Tool",
    author="VoIP Benchmark Team",
    author_email="info@voipbenchmark.org",
    url="https://github.com/voipbenchmark/voip_benchmark",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=[
        "numpy>=1.19.0",
        "pyyaml>=5.1",
        "soundfile>=0.10.0",
    ],
    extras_require={
        "opus": ["opuslib>=3.0.1"],
        "pesq": ["pesq>=0.0.2"],
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=20.8b1",
            "flake8>=3.8.0",
            "mypy>=0.782",
        ],
    },
    entry_points={
        "console_scripts": [
            "voip-benchmark=voip_benchmark.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Communications :: Internet Phone",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Software Development :: Testing",
    ],
) 