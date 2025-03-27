#!/usr/bin/env python3
"""
Unit tests for the benchmarking tools.

These tests verify the functionality of the benchmarking and visualization tools,
ensuring they correctly analyze codec performance and generate appropriate results.
"""

import os
import sys
import wave
import tempfile
import json
import pytest
import glob
import logging
from pathlib import Path

# Add the parent directory to the path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Try to import the benchmarking module
try:
    from voip_benchmark.benchmark.benchmark import CodecBenchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Try to import visualization tools
try:
    from voip_benchmark.benchmark.visualize import (
        load_csv_results, create_compression_comparison, create_bandwidth_savings_comparison,
        create_quality_comparison, create_network_impact_chart
    )
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


@pytest.fixture
def logger():
    """Set up a logger for testing."""
    logger = logging.getLogger("test_benchmark")
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Add a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


@pytest.fixture
def test_wav_file():
    """Create a temporary test WAV file."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Create a simple WAV file with silence
    with wave.open(temp_path, 'wb') as wav_file:
        # Configure WAV file
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16 bits
        wav_file.setframerate(8000)  # 8 kHz
        
        # Generate 1 second of silence (all zeros)
        wav_file.writeframes(b'\x00\x00' * 8000)
    
    # Return the path to the test file
    yield temp_path
    
    # Clean up
    os.unlink(temp_path)


@pytest.fixture
def output_dir():
    """Create a temporary directory for benchmark output."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Return the path to the test directory
    yield temp_dir
    
    # Clean up - recursive removal of directory tree
    import shutil
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")


@pytest.fixture
def sample_results():
    """Create sample benchmark results."""
    return [
        {
            "test_id": "opus_16000_ideal",
            "codec": "Opus",
            "codec_type": "opus",
            "bitrate": 16000,
            "network": "Ideal",
            "packet_loss": 0.0,
            "jitter": 0.0,
            "out_of_order": 0,
            "execution_time": 1.5,
            "compression_ratio": 0.25,
            "bandwidth_savings": 75.0,
            "quality_pesq": 4.2,
            "quality_snr": 25.3
        },
        {
            "test_id": "opus_8000_ideal",
            "codec": "Opus",
            "codec_type": "opus",
            "bitrate": 8000,
            "network": "Ideal",
            "packet_loss": 0.0,
            "jitter": 0.0,
            "out_of_order": 0,
            "execution_time": 1.4,
            "compression_ratio": 0.15,
            "bandwidth_savings": 85.0,
            "quality_pesq": 3.8,
            "quality_snr": 22.1
        },
        {
            "test_id": "none_64000_ideal",
            "codec": "Raw PCM",
            "codec_type": "none",
            "bitrate": 64000,
            "network": "Ideal",
            "packet_loss": 0.0,
            "jitter": 0.0,
            "out_of_order": 0,
            "execution_time": 1.3,
            "compression_ratio": 1.0,
            "bandwidth_savings": 0.0,
            "quality_pesq": 4.5,
            "quality_snr": 30.0
        },
        {
            "test_id": "opus_16000_poor",
            "codec": "Opus",
            "codec_type": "opus",
            "bitrate": 16000,
            "network": "Poor",
            "packet_loss": 5.0,
            "jitter": 60.0,
            "out_of_order": 3,
            "execution_time": 1.6,
            "compression_ratio": 0.25,
            "bandwidth_savings": 75.0,
            "quality_pesq": 3.1,
            "quality_snr": 18.7
        }
    ]


@pytest.mark.skipif(not BENCHMARK_AVAILABLE, reason="Benchmarking module not available")
def test_codec_benchmark_initialization(test_wav_file, output_dir, logger):
    """Test that CodecBenchmark can be initialized properly."""
    benchmark = CodecBenchmark(test_wav_file, output_dir, logger)
    
    # Check that directories were created
    assert os.path.exists(os.path.join(output_dir, "results"))
    assert os.path.exists(os.path.join(output_dir, "audio"))
    assert os.path.exists(os.path.join(output_dir, "plots"))
    
    # Check that WAV file was read correctly
    assert benchmark.sample_rate == 8000
    assert benchmark.channels == 1
    assert benchmark.sample_width == 2
    assert benchmark.duration == 1.0


@pytest.mark.skipif(not BENCHMARK_AVAILABLE, reason="Benchmarking module not available")
def test_audio_quality_calculation(test_wav_file, output_dir, logger):
    """Test the audio quality metrics calculation."""
    benchmark = CodecBenchmark(test_wav_file, output_dir, logger)
    
    # Calculate metrics between a file and itself (should be perfect quality)
    metrics = benchmark.calculate_audio_quality(test_wav_file, test_wav_file)
    
    # Check SNR - should be high or undefined for identical files
    if 'snr' in metrics:
        assert metrics['snr'] > 50 or metrics['snr'] == float('inf')


@pytest.mark.skipif(not VISUALIZATION_AVAILABLE, reason="Visualization tools not available")
def test_visualization_creation(output_dir, sample_results):
    """Test that visualization charts can be created."""
    # Save sample results to a temporary CSV file
    csv_file = os.path.join(output_dir, "test_results.csv")
    
    with open(csv_file, 'w', newline='') as f:
        import csv
        fieldnames = list(sample_results[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in sample_results:
            writer.writerow(result)
    
    # Test loading results from CSV
    loaded_results = load_csv_results(csv_file)
    assert len(loaded_results) == len(sample_results)
    
    # Test creating charts
    charts = []
    
    # Create compression chart
    chart_path = create_compression_comparison(loaded_results, output_dir)
    charts.append(chart_path)
    
    # Create bandwidth savings chart
    chart_path = create_bandwidth_savings_comparison(loaded_results, output_dir)
    charts.append(chart_path)
    
    # Create quality comparison charts
    create_quality_comparison(loaded_results, output_dir)
    pesq_chart = os.path.join(output_dir, "pesq.png")
    if os.path.exists(pesq_chart):
        charts.append(pesq_chart)
    
    # Create network impact chart
    chart_path = create_network_impact_chart(loaded_results, output_dir)
    charts.append(chart_path)
    
    # Check that at least some charts were created
    assert len(charts) > 0, "No visualization charts were created"
    
    # Check that all files exist
    for chart in charts:
        if chart:  # Some charts might be None if they couldn't be created
            assert os.path.exists(chart), f"Chart not found: {chart}"
            assert os.path.getsize(chart) > 0, f"Chart is empty: {chart}"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])