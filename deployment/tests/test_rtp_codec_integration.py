#!/usr/bin/env python3
"""
Unit tests for the RTP codec integration.

These tests verify that the Opus codec can be properly used with RTP packets
for sending and receiving audio data.
"""

import os
import sys
import wave
import socket
import tempfile
import threading
import time
import pytest
from pathlib import Path

# Add the parent directory to the path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voip_benchmark.codecs.opus import OpusCodec, PAYLOAD_TYPE_OPUS
from voip_benchmark.rtp.packet import create_rtp_packet, parse_rtp_header
from voip_benchmark.rtp.sender import send_rtp_stream
from voip_benchmark.rtp.receiver import receive_rtp_stream
import logging


@pytest.fixture
def logger():
    """Set up a logger for testing."""
    logger = logging.getLogger("test_logger")
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
def test_output_wav():
    """Create a temporary path for output WAV file."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Return the path to the test file
    yield temp_path
    
    # Clean up
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_rtp_packet_with_opus_payload():
    """Test creating an RTP packet with Opus-encoded payload."""
    # Create an Opus codec instance
    codec = OpusCodec(
        sample_rate=8000,
        channels=1,
        bitrate=16000,
        frame_size=160  # 20ms at 8kHz
    )
    
    # Create a simple audio payload (silence)
    pcm_data = b'\x00\x00' * 160  # 20ms of silence at 8kHz, 16-bit
    
    # Encode with Opus
    encoded_data = codec.encode(pcm_data)
    
    # Confirm encoding reduces data size
    assert len(encoded_data) < len(pcm_data)
    
    # Create RTP packet with Opus payload
    seq_num = 1000
    timestamp = 160000
    ssrc = 0x12345678
    
    packet = create_rtp_packet(
        payload=encoded_data,
        sequence_number=seq_num,
        timestamp=timestamp,
        ssrc=ssrc,
        payload_type=PAYLOAD_TYPE_OPUS
    )
    
    # Verify packet structure
    assert len(packet) > len(encoded_data)  # Packet should include header + payload
    
    # Parse the packet header
    header = parse_rtp_header(packet[:12])
    
    # Verify header fields
    assert header['version'] == 2
    assert header['payload_type'] == PAYLOAD_TYPE_OPUS
    assert header['sequence_number'] == seq_num
    assert header['timestamp'] == timestamp
    assert header['ssrc'] == ssrc
    
    # Verify payload matches
    extracted_payload = packet[12:]
    assert extracted_payload == encoded_data


def test_rtp_send_receive_with_opus(test_wav_file, test_output_wav, logger):
    """Test sending and receiving RTP packets with Opus codec."""
    # Define test parameters
    send_port = 12345
    duration = 2  # seconds
    
    # Define a threading event to signal completion
    receive_complete = threading.Event()
    
    # Define receiver thread function
    def receive_thread():
        try:
            success, bytes_received, packets_received = receive_rtp_stream(
                listen_port=send_port,
                output_file=test_output_wav,
                duration=duration,
                codec_name='opus',
                bitrate=16000,
                logger=logger
            )
            # Signal completion
            receive_complete.set()
            
            # Additional assertions in the receiver thread
            assert success, "RTP receiver reported failure"
            assert bytes_received > 0, "No bytes received"
            assert packets_received > 0, "No packets received"
            assert os.path.exists(test_output_wav), "Output WAV file not created"
            
        except Exception as e:
            logger.error(f"Receiver thread error: {e}")
            receive_complete.set()
    
    # Start receiver in a separate thread
    receiver_thread = threading.Thread(target=receive_thread)
    receiver_thread.daemon = True
    receiver_thread.start()
    
    # Give receiver time to start
    time.sleep(1)
    
    # Send RTP stream with Opus codec
    success, bytes_sent, packets_sent = send_rtp_stream(
        wav_file=test_wav_file,
        dest_ip='127.0.0.1',
        dest_port=send_port,
        codec_name='opus',
        bitrate=16000,
        logger=logger
    )
    
    # Wait for receiver to complete
    receive_complete.wait(timeout=duration + 5)
    
    # Verify sender results
    assert success, "RTP sender reported failure"
    assert bytes_sent > 0, "No bytes sent"
    assert packets_sent > 0, "No packets sent"
    
    # Verify output WAV file exists and has content
    assert os.path.exists(test_output_wav), "Output WAV file not created"
    assert os.path.getsize(test_output_wav) > 0, "Output WAV file is empty"
    
    # Verify WAV file format
    with wave.open(test_output_wav, 'rb') as wav_out:
        assert wav_out.getnchannels() == 1, "Expected mono audio"
        assert wav_out.getsampwidth() == 2, "Expected 16-bit audio"
        assert wav_out.getframerate() == 48000, "Expected 48kHz sample rate"
        assert wav_out.getnframes() > 0, "No audio frames in output file"


def test_rtp_send_receive_compression_ratio(test_wav_file, test_output_wav, logger):
    """Test that using Opus codec reduces the amount of data sent over RTP."""
    # Define test parameters
    send_port = 12346
    duration = 2  # seconds
    
    # First run without codec to get baseline
    # Define a threading event to signal completion
    receive_complete = threading.Event()
    
    # Define receiver thread function
    def receive_thread_no_codec():
        try:
            success, bytes_received, packets_received = receive_rtp_stream(
                listen_port=send_port,
                output_file=test_output_wav,
                duration=duration,
                codec_name=None,  # No codec
                logger=logger
            )
            # Signal completion
            receive_complete.set()
        except Exception as e:
            logger.error(f"Receiver thread error: {e}")
            receive_complete.set()
    
    # Start receiver in a separate thread
    receiver_thread = threading.Thread(target=receive_thread_no_codec)
    receiver_thread.daemon = True
    receiver_thread.start()
    
    # Give receiver time to start
    time.sleep(1)
    
    # Send RTP stream without codec
    success_no_codec, bytes_sent_no_codec, packets_sent_no_codec = send_rtp_stream(
        wav_file=test_wav_file,
        dest_ip='127.0.0.1',
        dest_port=send_port,
        codec_name=None,  # No codec
        logger=logger
    )
    
    # Wait for receiver to complete
    receive_complete.wait(timeout=duration + 5)
    receive_complete.clear()
    
    # Now run with Opus codec
    # Define receiver thread function with codec
    def receive_thread_with_codec():
        try:
            success, bytes_received, packets_received = receive_rtp_stream(
                listen_port=send_port,
                output_file=test_output_wav,
                duration=duration,
                codec_name='opus',
                bitrate=16000,
                logger=logger
            )
            # Signal completion
            receive_complete.set()
        except Exception as e:
            logger.error(f"Receiver thread error: {e}")
            receive_complete.set()
    
    # Start receiver in a separate thread
    receiver_thread = threading.Thread(target=receive_thread_with_codec)
    receiver_thread.daemon = True
    receiver_thread.start()
    
    # Give receiver time to start
    time.sleep(1)
    
    # Send RTP stream with Opus codec
    success_with_codec, bytes_sent_with_codec, packets_sent_with_codec = send_rtp_stream(
        wav_file=test_wav_file,
        dest_ip='127.0.0.1',
        dest_port=send_port,
        codec_name='opus',
        bitrate=16000,
        logger=logger
    )
    
    # Wait for receiver to complete
    receive_complete.wait(timeout=duration + 5)
    
    # Verify both tests were successful
    assert success_no_codec, "RTP sender without codec reported failure"
    assert success_with_codec, "RTP sender with codec reported failure"
    
    # Verify packets were sent in both cases
    assert packets_sent_no_codec > 0, "No packets sent without codec"
    assert packets_sent_with_codec > 0, "No packets sent with codec"
    
    # Calculate compression ratio
    # The number of packets should be the same, but bytes should be fewer with codec
    compression_ratio = bytes_sent_with_codec / bytes_sent_no_codec
    
    # Opus should provide significant compression
    assert compression_ratio < 0.5, f"Expected at least 50% compression, got {compression_ratio*100:.1f}%"
    
    logger.info(f"Compression Test Results:")
    logger.info(f"  Bytes sent without codec: {bytes_sent_no_codec}")
    logger.info(f"  Bytes sent with codec: {bytes_sent_with_codec}")
    logger.info(f"  Compression ratio: {compression_ratio:.4f} ({compression_ratio*100:.1f}%)")
    logger.info(f"  Bandwidth savings: {(1-compression_ratio)*100:.1f}%")


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])