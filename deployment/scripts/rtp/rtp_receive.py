#!/usr/bin/env python3
"""
rtp_receive.py - RTP Packet Receiver for VoIP Benchmarking

This script listens for incoming RTP packets, reconstructs the audio stream,
and saves it to a WAV file. It is designed to work with rtp_send.py for
benchmarking VoIP audio transmission.
"""

import argparse
import logging
import os
import socket
import struct
import sys
import time
import wave


# Constants for RTP packet reception
PAYLOAD_TYPE_PCMU = 0  # G.711 u-law
PAYLOAD_TYPE_PCMA = 8  # G.711 A-law
PAYLOAD_TYPE_L16 = 11  # 16-bit linear PCM

# RTP header size is 12 bytes
RTP_HEADER_SIZE = 12
# Standard settings for VoIP audio
SAMPLE_RATE = 8000
SAMPLE_WIDTH = 2  # 16-bit audio
CHANNELS = 1      # Mono audio


def setup_logging(debug=False):
    """Set up logging configuration."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def parse_rtp_header(packet):
    """
    Parse an RTP packet header.
    
    Args:
        packet: Complete RTP packet as bytes
        
    Returns:
        Tuple of (version, padding, extension, cc, marker, payload_type, 
                 sequence_number, timestamp, ssrc, payload)
    """
    if len(packet) < RTP_HEADER_SIZE:
        raise ValueError(f"Packet too small to be valid RTP: {len(packet)} bytes")
        
    # Unpack the header
    header = packet[:RTP_HEADER_SIZE]
    payload = packet[RTP_HEADER_SIZE:]
    
    # First byte contains version (2 bits), padding (1 bit), extension (1 bit), CSRC count (4 bits)
    # Second byte contains marker (1 bit) and payload type (7 bits)
    first_byte, second_byte, seq_num, timestamp, ssrc = struct.unpack('!BBHII', header)
    
    version = (first_byte >> 6) & 0x03
    padding = (first_byte >> 5) & 0x01
    extension = (first_byte >> 4) & 0x01
    cc = first_byte & 0x0F
    
    marker = (second_byte >> 7) & 0x01
    payload_type = second_byte & 0x7F
    
    return (version, padding, extension, cc, marker, payload_type, 
            seq_num, timestamp, ssrc, payload)


def receive_rtp_stream(listen_port, output_file, duration, logger):
    """
    Listen for incoming RTP packets and save to a WAV file.
    
    Args:
        listen_port: UDP port to listen on
        output_file: Path to output WAV file
        duration: Duration to listen in seconds (0 = indefinite)
        logger: Logger instance
        
    Returns:
        Tuple of (success, bytes_received, packets_received)
    """
    try:
        # Set up UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow socket reuse to avoid "address already in use" errors
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try to bind to all interfaces first
        try:
            sock.bind(('0.0.0.0', listen_port))
            logger.info(f"Listening on all interfaces (0.0.0.0:{listen_port})")
        except OSError as e:
            logger.warning(f"Could not bind to all interfaces: {e}")
            # Fall back to localhost only
            try:
                sock.bind(('127.0.0.1', listen_port))
                logger.info(f"Listening on localhost only (127.0.0.1:{listen_port})")
            except OSError as e2:
                logger.error(f"Could not bind to localhost either: {e2}")
                return False, 0, 0
        
        # Set a reasonable timeout for operations
        sock.settimeout(1.0)  
        
        logger.info(f"Listening for RTP packets on port {listen_port}")
        
        if duration > 0:
            logger.info(f"Will record for {duration} seconds")
            end_time = time.time() + duration
        else:
            logger.info("Will record until interrupted (Ctrl+C)")
            end_time = None
        
        # Prepare to receive data
        packets_received = 0
        bytes_received = 0
        last_seq_num = None
        missing_packets = 0
        out_of_order_packets = 0
        expected_payload_type = None
        
        # Buffer for audio data
        audio_buffer = bytearray()
        active_ssrc = None
        
        # Record start time for statistics
        start_time = time.time()
        last_report_time = start_time
        
        try:
            # Main reception loop
            while True:
                try:
                    # Check if we've reached the duration limit
                    if end_time and time.time() >= end_time:
                        logger.info(f"Reached recording duration of {duration} seconds")
                        break
                    
                    # Receive packet with timeout
                    packet, addr = sock.recvfrom(4096)
                    recv_time = time.time()
                    
                    # Parse RTP header
                    try:
                        (version, padding, extension, cc, marker, payload_type, 
                         seq_num, timestamp, ssrc, payload) = parse_rtp_header(packet)
                        
                        # Validate RTP version
                        if version != 2:
                            logger.warning(f"Received non-RTP or unsupported RTP version: {version}")
                            continue
                        
                        # Process first packet specially
                        if packets_received == 0:
                            logger.info(f"First RTP packet received from {addr[0]}:{addr[1]}")
                            logger.info(f"  SSRC: 0x{ssrc:08x}")
                            logger.info(f"  Sequence: {seq_num}")
                            logger.info(f"  Timestamp: {timestamp}")
                            logger.info(f"  Payload Type: {payload_type}")
                            
                            active_ssrc = ssrc
                            expected_payload_type = payload_type
                            last_seq_num = seq_num
                        
                        # Check if packet is from the same stream
                        if ssrc != active_ssrc:
                            logger.warning(f"Received packet with different SSRC: 0x{ssrc:08x} (expected 0x{active_ssrc:08x})")
                            continue
                        
                        # Check payload type
                        if payload_type != expected_payload_type:
                            logger.warning(f"Received unexpected payload type: {payload_type} (expected {expected_payload_type})")
                        
                        # Sequence number tracking
                        if last_seq_num is not None:
                            # Calculate expected sequence number with wrap-around
                            expected_seq = (last_seq_num + 1) & 0xFFFF
                            
                            if seq_num != expected_seq:
                                if ((seq_num < expected_seq) and (expected_seq - seq_num < 0x8000)) or \
                                   ((seq_num > expected_seq) and (seq_num - expected_seq > 0x8000)):
                                    # Out of order packet
                                    out_of_order_packets += 1
                                    if logger.level <= logging.DEBUG:
                                        logger.debug(f"Out-of-order packet: got {seq_num}, expected {expected_seq}")
                                else:
                                    # Missing packet(s)
                                    gap = (seq_num - expected_seq) & 0xFFFF
                                    missing_packets += gap
                                    if logger.level <= logging.DEBUG:
                                        logger.debug(f"Missing {gap} packet(s): got {seq_num}, expected {expected_seq}")
                        
                        # Update sequence tracking
                        last_seq_num = seq_num
                        
                        # Add payload to audio buffer
                        audio_buffer.extend(payload)
                        
                        # Update counters
                        packets_received += 1
                        bytes_received += len(packet)
                        
                        # Periodic status reporting
                        if recv_time - last_report_time > 5.0:
                            elapsed = recv_time - start_time
                            rate = bytes_received / elapsed / 1024
                            logger.info(f"Received {packets_received} packets ({bytes_received} bytes) in {elapsed:.1f}s ({rate:.2f} KB/s)")
                            logger.info(f"  Missing packets: {missing_packets}, Out-of-order: {out_of_order_packets}")
                            last_report_time = recv_time
                            
                    except Exception as e:
                        logger.warning(f"Error parsing RTP packet: {e}")
                        continue
                        
                except socket.timeout:
                    # Just a timeout, continue listening
                    continue
                    
        except KeyboardInterrupt:
            logger.info("Recording stopped by user")
        
        # Close the socket
        sock.close()
        
        # Calculate statistics
        total_time = time.time() - start_time
        
        logger.info(f"RTP reception complete:")
        logger.info(f"  Packets received: {packets_received}")
        logger.info(f"  Bytes received: {bytes_received}")
        logger.info(f"  Missing packets: {missing_packets}")
        logger.info(f"  Out-of-order packets: {out_of_order_packets}")
        logger.info(f"  Duration: {total_time:.2f} seconds")
        if total_time > 0:
            logger.info(f"  Receive rate: {bytes_received / total_time / 1024:.2f} KB/s")
        
        # Save audio buffer to WAV file if we received anything
        if audio_buffer:
            logger.info(f"Writing {len(audio_buffer)} bytes of audio data to {output_file}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            try:
                # Only log file operations in debug mode with condensed messages
                if logger.level <= logging.DEBUG:
                    logger.debug(f"Creating WAV file: {output_file} (dir exists: {os.path.exists(os.path.dirname(os.path.abspath(output_file)))})")
                
                # Create WAV file
                with wave.open(output_file, 'wb') as wav_file:
                    if logger.level <= logging.DEBUG:
                        logger.debug("WAV file opened successfully")
                    
                    # Set WAV file parameters
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(SAMPLE_WIDTH)
                    wav_file.setframerate(SAMPLE_RATE)
                    
                    # Write audio data
                    wav_file.writeframes(audio_buffer)
                    
                # Verify file was created
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    logger.info(f"WAV file created successfully: {output_file} ({file_size} bytes)")
                    return True, bytes_received, packets_received
                else:
                    logger.error(f"WAV file creation failed: file does not exist after writing")
                    return False, bytes_received, packets_received
                    
            except Exception as e:
                logger.error(f"Error creating WAV file: {e}")
                # More   error for file permission issues
                if isinstance(e, PermissionError):
                    logger.error(f"Permission denied when creating {output_file}")
                    logger.error(f"File directory permissions: {oct(os.stat(os.path.dirname(os.path.abspath(output_file))).st_mode)}")
                return False, bytes_received, packets_received
        else:
            logger.warning("No audio data received, not creating WAV file")
            return False, bytes_received, packets_received
        
    except Exception as e:
        logger.error(f"Error in RTP reception: {e}")
        return False, 0, 0


def main():
    """Main entry point for the RTP receiver script."""
    parser = argparse.ArgumentParser(description='RTP Stream Receiver for VoIP Benchmarking')
    parser.add_argument('--port', type=int, default=12345,
                      help='Port to listen on (default: 12345)')
    parser.add_argument('--output', default='received_audio.wav',
                      help='Output WAV file (default: received_audio.wav)')
    parser.add_argument('--duration', type=int, default=0,
                      help='Duration to record in seconds, 0 for unlimited (default: 0)')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.debug)
    
    logger.info("RTP Stream Receiver")
    logger.info("==================")
    
    # Run receiver
    success, bytes_received, packets_received = receive_rtp_stream(
        args.port, args.output, args.duration, logger
    )
    
    if success:
        logger.info("RTP stream received and saved successfully")
        sys.exit(0)
    else:
        logger.error("Failed to receive and save RTP stream")
        sys.exit(1)


if __name__ == "__main__":
    main() 