#!/usr/bin/env python3
"""
rtp_send.py - RTP Packet Generator for VoIP Benchmarking

This script takes a WAV file optimized for VoIP (8kHz, mono, PCM_S16LE) and
converts it into properly formatted RTP packets that can be sent to a 
specified destination. This provides a more accurate simulation of real
VoIP traffic compared to just sending raw UDP data.
"""

import argparse
import logging
import os
import random
import socket
import struct
import sys
import time
import wave


# Constants for RTP packet creation
PAYLOAD_TYPE_PCMU = 0  # G.711 u-law
PAYLOAD_TYPE_PCMA = 8  # G.711 A-law
PAYLOAD_TYPE_L16 = 11  # 16-bit linear PCM

# RTP packet header size is 12 bytes
RTP_HEADER_SIZE = 12
# Standard packet interval for 8kHz audio (usually 20ms)
PACKET_INTERVAL_MS = 20
# Number of samples per packet at 8kHz with 20ms packets
SAMPLES_PER_PACKET = int(8000 * (PACKET_INTERVAL_MS / 1000))
# For 16-bit audio, each sample is 2 bytes
BYTES_PER_SAMPLE = 2
# Resulting payload size per packet
PAYLOAD_SIZE = SAMPLES_PER_PACKET * BYTES_PER_SAMPLE


def setup_logging(debug=False):
    """Set up logging configuration."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def create_rtp_packet(payload, seq_num, timestamp, ssrc=0):
    """
    Create an RTP packet with the given payload and parameters.
    
    Args:
        payload: Audio data payload
        seq_num: RTP sequence number (16 bits)
        timestamp: RTP timestamp (32 bits)
        ssrc: Synchronization source identifier (32 bits)
        
    Returns:
        Complete RTP packet as bytes
    """
    # RTP version 2, no padding, no extension, no CSRC
    version = 2
    padding = 0
    extension = 0
    cc = 0  # CSRC count
    
    # No marker, payload type 11 (L16 audio)
    marker = 0
    payload_type = PAYLOAD_TYPE_L16
    
    # First byte: version (2 bits), padding (1 bit), extension (1 bit), CSRC count (4 bits)
    first_byte = (version << 6) | (padding << 5) | (extension << 4) | cc
    
    # Second byte: marker (1 bit), payload type (7 bits)
    second_byte = (marker << 7) | payload_type
    
    # Create header
    header = struct.pack('!BBHII', first_byte, second_byte, seq_num, timestamp, ssrc)
    
    # Return complete packet
    return header + payload


def send_rtp_stream(wav_file, dest_ip, dest_port, logger):
    """
    Send the contents of a WAV file as an RTP stream.
    
    Args:
        wav_file: Path to the WAV file to stream
        dest_ip: Destination IP address
        dest_port: Destination port number
        logger: Logger instance
        
    Returns:
        Tuple of (success, bytes_sent, packets_sent)
    """
    try:
        # Open and validate WAV file
        with wave.open(wav_file, 'rb') as wav:
            # Check WAV format
            if wav.getnchannels() != 1:
                logger.error(f"WAV file must be mono, found {wav.getnchannels()} channels")
                return False, 0, 0
                
            if wav.getsampwidth() != 2:
                logger.error(f"WAV file must use 16-bit samples, found {wav.getsampwidth() * 8} bits")
                return False, 0, 0
                
            if wav.getframerate() != 8000:
                logger.warning(f"WAV file sample rate is {wav.getframerate()} Hz, " 
                             f"expected 8000 Hz for optimal VoIP compatibility")
            
            # Calculate stream parameters
            total_samples = wav.getnframes()
            duration_seconds = total_samples / wav.getframerate()
            
            logger.info(f"WAV file: {os.path.basename(wav_file)}")
            logger.info(f"  Format: {wav.getsampwidth() * 8}-bit, {wav.getnchannels()} channel(s), {wav.getframerate()} Hz")
            logger.info(f"  Duration: {duration_seconds:.2f} seconds")
            logger.info(f"  Total frames: {total_samples}")
            
            # Set up UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Allow broadcasts and set TTL
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 64)
            
            # Verify destination IP is reachable
            try:
                # Try to resolve hostname if needed
                if not dest_ip[0].isdigit():
                    logger.info(f"Resolving hostname: {dest_ip}")
                    dest_ip = socket.gethostbyname(dest_ip)
                    logger.info(f"Resolved to IP: {dest_ip}")
                
                logger.info(f"Destination: {dest_ip}:{dest_port}")
            except socket.gaierror as e:
                logger.error(f"Could not resolve destination address: {e}")
                return False, 0, 0
            
            # Initialize RTP parameters
            ssrc = random.randint(0, 0xFFFFFFFF)  # Random synchronization source
            seq_num = random.randint(0, 0xFFFF)   # Random starting sequence number
            timestamp = random.randint(0, 0xFFFFFFFF)  # Random initial timestamp
            
            logger.info(f"RTP Stream Parameters:")
            logger.info(f"  SSRC: 0x{ssrc:08x}")
            logger.info(f"  Initial Sequence: {seq_num}")
            logger.info(f"  Initial Timestamp: {timestamp}")
            logger.info(f"  Payload Size: {PAYLOAD_SIZE} bytes")
            logger.info(f"  Packet Interval: {PACKET_INTERVAL_MS} ms")
            
            # Start streaming
            logger.info(f"Starting RTP stream to {dest_ip}:{dest_port}")
            
            bytes_sent = 0
            packets_sent = 0
            start_time = time.time()
            
            # Read and send in chunks matching the packet size
            while True:
                # Read payload size worth of audio data
                payload = wav.readframes(SAMPLES_PER_PACKET)
                
                # If we reach end of file or have insufficient data, we're done
                if not payload or len(payload) < PAYLOAD_SIZE:
                    if payload:  # Handle the last partial packet if needed
                        logger.debug(f"Sending final partial packet: {len(payload)} bytes")
                        packet = create_rtp_packet(payload, seq_num, timestamp, ssrc)
                        sock.sendto(packet, (dest_ip, dest_port))
                        bytes_sent += len(packet)
                        packets_sent += 1
                    break
                
                # Create and send RTP packet
                packet = create_rtp_packet(payload, seq_num, timestamp, ssrc)
                sock.sendto(packet, (dest_ip, dest_port))
                
                # Update counters
                bytes_sent += len(packet)
                packets_sent += 1
                seq_num = (seq_num + 1) & 0xFFFF  # Wrap at 16 bits
                timestamp += SAMPLES_PER_PACKET   # Timestamp increases by samples sent
                
                # Real-time pacing - sleep to maintain proper timing
                elapsed = time.time() - start_time
                target_time = (packets_sent * PACKET_INTERVAL_MS) / 1000
                if target_time > elapsed:
                    time.sleep(target_time - elapsed)
                
                # Periodic logging
                if packets_sent % 50 == 0:
                    logger.debug(f"Sent {packets_sent} packets ({bytes_sent} bytes)")
            
            # Close socket
            sock.close()
            
            # Summary
            total_time = time.time() - start_time
            logger.info(f"RTP stream complete:")
            logger.info(f"  Packets sent: {packets_sent}")
            logger.info(f"  Bytes sent: {bytes_sent}")
            logger.info(f"  Duration: {total_time:.2f} seconds")
            logger.info(f"  Transfer rate: {bytes_sent / total_time / 1024:.2f} KB/s")
            
            return True, bytes_sent, packets_sent
            
    except Exception as e:
        logger.error(f"Error sending RTP stream: {e}")
        return False, 0, 0


def main():
    """Main entry point for the RTP sender script."""
    parser = argparse.ArgumentParser(description='RTP Stream Generator for VoIP Benchmarking')
    parser.add_argument('wav_file', help='Path to the WAV file to stream')
    parser.add_argument('--dest-ip', default='127.0.0.1',
                        help='Destination IP address (default: 127.0.0.1)')
    parser.add_argument('--dest-port', type=int, default=10000,
                        help='Destination port (default: 10000)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.debug)
    
    logger.info("RTP Stream Generator")
    logger.info("==================")
    
    # Validate WAV file
    if not os.path.isfile(args.wav_file):
        logger.error(f"WAV file not found: {args.wav_file}")
        sys.exit(1)
    
    # Send RTP stream
    success, bytes_sent, packets_sent = send_rtp_stream(
        args.wav_file, args.dest_ip, args.dest_port, logger
    )
    
    if success:
        logger.info("RTP stream sent successfully")
        sys.exit(0)
    else:
        logger.error("Failed to send RTP stream")
        sys.exit(1)


if __name__ == "__main__":
    main() 