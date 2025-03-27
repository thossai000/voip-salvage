#!/usr/bin/env python3
"""
Setup script for the voip_benchmark package
"""

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = fh.read().splitlines()

setup(
    name="voip_benchmark",
    version="1.0.0",
    author="VoIP Benchmark Team",
    author_email="voip@benchmark.org",
    description="A framework for benchmarking VoIP audio quality",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/voip-benchmark/voip-benchmark",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Telecommunications Industry",
        "Topic :: Communications :: Internet Phone",
        "Topic :: Multimedia :: Sound/Audio",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "voip-benchmark=voip_benchmark.examples.simple_benchmark:main",
        ],
    },
) 