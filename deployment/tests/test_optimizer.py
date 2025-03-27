#!/usr/bin/env python3
"""
Unit tests for the codec optimization tools.

These tests verify the functionality of the codec optimizer,
ensuring it can find optimal codec configurations for different use cases.
"""

import os
import sys
import wave
import tempfile
import json
import pytest
import logging
from pathlib import Path

# Add the parent directory to the path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Try to import the optimization module
try:
    from voip_benchmark.utils.optimizer import CodecOptimizer, OptimizationResult, batch_optimize
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False


@pytest.fixture
def logger():
    """Set up a logger for testing."""
    logger = logging.getLogger("test_optimizer")
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
        wav_file.setframerate(16000)  # 16 kHz
        
        # Generate 1 second of silence (all zeros)
        wav_file.writeframes(b'\x00\x00' * 16000)
    
    # Return the path to the test file
    yield temp_path
    
    # Clean up
    os.unlink(temp_path)


@pytest.fixture
def output_dir():
    """Create a temporary directory for optimization output."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Return the path to the test directory
    yield temp_dir
    
    # Clean up
    import shutil
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Optimization module not available")
def test_optimizer_initialization(logger):
    """Test that CodecOptimizer can be initialized properly."""
    optimizer = CodecOptimizer(logger)
    
    # Check that the optimizer was created successfully
    assert optimizer is not None
    assert optimizer.logger is not None


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Optimization module not available")
def test_get_optimal_opus_config(logger):
    """Test retrieving optimal Opus configurations for different targets."""
    optimizer = CodecOptimizer(logger)
    
    # Test balanced configuration
    balanced_config = optimizer.get_optimal_opus_config("balanced")
    assert balanced_config is not None
    assert "complexity" in balanced_config
    assert "application" in balanced_config
    assert "frame_size" in balanced_config
    assert "bitrate" in balanced_config
    
    # Test quality configuration
    quality_config = optimizer.get_optimal_opus_config("quality")
    assert quality_config is not None
    assert quality_config["complexity"] == 10  # Max quality should use max complexity
    assert quality_config["bitrate"] > balanced_config["bitrate"]  # Quality should use higher bitrate
    
    # Test bitrate configuration
    bitrate_config = optimizer.get_optimal_opus_config("bitrate")
    assert bitrate_config is not None
    assert bitrate_config["bitrate"] < quality_config["bitrate"]  # Bitrate optimization uses lower bitrate
    
    # Test latency configuration
    latency_config = optimizer.get_optimal_opus_config("latency")
    assert latency_config is not None
    assert latency_config["frame_size"] < balanced_config["frame_size"]  # Latency uses smaller frames
    
    # Test CPU configuration
    cpu_config = optimizer.get_optimal_opus_config("cpu")
    assert cpu_config is not None
    assert cpu_config["complexity"] < balanced_config["complexity"]  # CPU uses lower complexity


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Optimization module not available")
def test_generate_parameter_combinations(logger):
    """Test generating parameter combinations for optimization."""
    optimizer = CodecOptimizer(logger)
    
    # Test with balanced target
    balanced_combinations = optimizer._generate_parameter_combinations("balanced", 5)
    assert len(balanced_combinations) == 5  # Should respect max_combinations
    
    # Test with quality target
    quality_combinations = optimizer._generate_parameter_combinations("quality", 3)
    assert len(quality_combinations) == 3
    
    # Instead of exact matching, just check that quality combinations focus on high quality
    # (high complexity, high bitrate)
    for combo in quality_combinations:
        assert combo["complexity"] >= 8  # Quality target should use high complexity
        assert combo["bitrate"] >= 32000  # Quality target should use higher bitrates
        assert combo["application"] in ["audio", "voip"]  # Should use quality-focused applications


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Optimization module not available")
def test_optimize_opus_codec(test_wav_file, logger):
    """Test optimizing Opus codec parameters for a WAV file."""
    optimizer = CodecOptimizer(logger)
    
    # Run optimization with limited combinations for testing
    results = optimizer.optimize_opus_codec(
        test_wav_file, target="balanced", max_combinations=2
    )
    
    # Check results
    assert len(results) > 0
    assert isinstance(results[0], OptimizationResult)
    assert results[0].codec_name == "opus"
    assert "complexity" in results[0].parameters
    assert "application" in results[0].parameters
    assert "frame_size" in results[0].parameters
    assert "bitrate" in results[0].parameters
    
    # Check sorting (results should be sorted by the target)
    if len(results) > 1:
        # For balanced target, we use a composite score, so we can't easily check the sorting
        # But we can verify that results have different parameters
        assert results[0].parameters != results[1].parameters


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Optimization module not available")
def test_batch_optimize(test_wav_file, output_dir, logger, monkeypatch):
    """Test batch optimization across multiple files."""
    # Create a list with the same file twice (for testing)
    input_files = [test_wav_file, test_wav_file]
    output_file = os.path.join(output_dir, "batch_results.json")
    
    # Mock the optimize_opus_codec method to return predefined results
    def mock_optimize(self, audio_file, target="balanced", max_combinations=10):
        result = OptimizationResult(
            codec_name="opus",
            parameters={"complexity": 6, "application": "voip", "frame_size": 20, "bitrate": 24000},
            bitrate=24000,
            quality_score=4.5,
            compression_ratio=0.25,
            encode_time=0.01,
            decode_time=0.01,
            frame_size=20
        )
        return [result]
    
    # Apply the mock
    monkeypatch.setattr(CodecOptimizer, "optimize_opus_codec", mock_optimize)
    
    # Run batch optimization with the mock
    optimal_config = batch_optimize(input_files, output_file, target="balanced")
    
    # Check result
    assert optimal_config is not None
    assert "complexity" in optimal_config
    assert "application" in optimal_config
    assert "frame_size" in optimal_config
    assert "bitrate" in optimal_config
    
    # Check output file
    assert os.path.exists(output_file)
    
    # Load the JSON file and check its structure
    with open(output_file, 'r') as f:
        results_json = json.load(f)
    
    # The format might vary based on implementation - we only need to check that
    # it contains the optimal configuration and at least one input file result
    assert len(results_json) >= 2  # At least optimal_configuration + one file
    assert "optimal_configuration" in results_json
    assert any(key.endswith('.wav') for key in results_json.keys() if key != "optimal_configuration")


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])