#!/usr/bin/env python3

import socket
import wave
import time
import struct
import threading
import queue
import os
import sys
import logging
import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from voip_benchmark.rtp.packet import RTPPacket
from voip_benchmark.codecs.opus import OpusCodec

class RTPReceiver:
    """
    Receives RTP packets and reconstructs the audio stream.
    Basic implementation without advanced features like RTCP.
    """
    def __init__(self, bind_ip="0.0.0.0", bind_port=12345, buffer_size=4096):
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.buffer_size = buffer_size
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, bind_port))
        self.running = False
        self.packet_queue = queue.Queue()
        self.last_seq_num = None
        self.packets_received = 0
        self.bytes_received = 0
        self.out_of_order_packets = 0
        self.expected_packets = float('inf')  # Set to a specific value for tracking
        
    def start_receiving(self, timeout=None):
        """
        Start receiving RTP packets in a separate thread.
        
        Args:
            timeout: How long to receive for in seconds (None = indefinite)
        """
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_packets, args=(timeout,))
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
    def _receive_packets(self, timeout=None):
        """
        Continuously receive packets and add them to the queue.
        
        Args:
            timeout: How long to receive for in seconds (None = indefinite)
        """
        if timeout:
            self.sock.settimeout(0.1)  # Short timeout to check running state
            end_time = time.time() + timeout
        else:
            self.sock.settimeout(None)
            
        while self.running:
            try:
                if timeout and time.time() > end_time:
                    self.running = False
                    break
                    
                data, addr = self.sock.recvfrom(self.buffer_size)
                packet = RTPPacket()
                if packet.parse_packet(data):
                    # Check sequence number for tracking out of order packets
                    if self.last_seq_num is not None:
                        expected_seq = (self.last_seq_num + 1) % 65536
                        if packet.sequence_number != expected_seq:
                            self.out_of_order_packets += 1
                            
                    self.last_seq_num = packet.sequence_number
                    self.packets_received += 1
                    self.bytes_received += len(data)
                    self.packet_queue.put(packet)
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Error receiving packet: {e}")
                
    def save_audio(self, output_file, codec=None, sample_width=2, channels=1, 
                   sample_rate=48000, timeout=None):
        """
        Process received packets and save as WAV file.
        
        Args:
            output_file: Path to save the output WAV file
            codec: Audio codec to use for decoding (default: None = raw PCM)
            sample_width: Sample width in bytes (default: 2 = 16-bit)
            channels: Number of audio channels (default: 1 = mono)
            sample_rate: Sample rate in Hz (default: 48000)
            timeout: How long to wait for packets in seconds
            
        Returns:
            Tuple of (packets_processed, bytes_processed, output_file_size)
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            wav = wave.open(output_file, 'wb')
            wav.setnchannels(channels)
            wav.setsampwidth(sample_width)
            wav.setframerate(sample_rate)
            
            # Initialize codec if specified
            if codec:
                if isinstance(codec, str) and codec.lower() == 'opus':
                    codec = OpusCodec(sample_rate=sample_rate, channels=channels)
                codec.initialize()
            
            packets_processed = 0
            bytes_processed = 0
            start_time = time.time()
            
            print(f"Receiving audio data to {output_file}")
            print(f"Sample rate: {sample_rate}Hz, Channels: {channels}, "
                  f"Sample width: {sample_width} bytes")
            
            # Process all packets in the queue
            while self.running or not self.packet_queue.empty():
                try:
                    # Wait for packets with timeout
                    if timeout and (time.time() - start_time) > timeout:
                        break
                        
                    try:
                        packet = self.packet_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    # Decode payload if codec is specified
                    if codec:
                        decoded_data = codec.decode(packet.payload)
                    else:
                        decoded_data = packet.payload
                    
                    wav.writeframes(decoded_data)
                    
                    packets_processed += 1
                    bytes_processed += len(packet.payload)
                    
                except Exception as e:
                    logging.error(f"Error processing packet: {e}")
            
            wav.close()
            
            # Get output file size
            output_size = os.path.getsize(output_file)
            
            print(f"Processed {packets_processed} packets ({bytes_processed} bytes)")
            print(f"Created WAV file: {output_file} ({output_size} bytes)")
            
            return packets_processed, bytes_processed, output_size
            
        except Exception as e:
            logging.error(f"Error saving audio: {e}")
            return 0, 0, 0
            
    def stop(self):
        """Stop receiving packets"""
        self.running = False
        if hasattr(self, 'receive_thread'):
            self.receive_thread.join(timeout=1.0)
        self.sock.close()
        
    def get_stats(self):
        """Get reception statistics"""
        return {
            'packets_received': self.packets_received,
            'bytes_received': self.bytes_received,
            'out_of_order_packets': self.out_of_order_packets,
            'packet_loss': max(0, self.expected_packets - self.packets_received) 
                           if self.expected_packets != float('inf') else 0
        }


class AdaptiveRTPReceiver(RTPReceiver):
    """
    Enhanced RTP receiver with jitter buffer and packet loss concealment
    """
    def __init__(self, bind_ip="0.0.0.0", bind_port=12345, buffer_size=4096, 
                 jitter_buffer_size=100):
        super().__init__(bind_ip, bind_port, buffer_size)
        self.jitter_buffer_size = jitter_buffer_size
        self.jitter_buffer = {}  # Sequence number -> packet
        self.next_seq_to_play = None
        
    def save_audio(self, output_file, codec=None, sample_width=2, channels=1, 
                   sample_rate=48000, timeout=None, use_jitter_buffer=True,
                   debug_log=False):
        """
        Process received packets with jitter buffer and save as WAV file.
        
        Args:
            output_file: Path to save the output WAV file
            codec: Audio codec to use for decoding
            sample_width: Sample width in bytes
            channels: Number of audio channels
            sample_rate: Sample rate in Hz
            timeout: How long to wait for packets in seconds
            use_jitter_buffer: Whether to use jitter buffer
            debug_log: Whether to enable debug logging
            
        Returns:
            Tuple of (packets_processed, bytes_processed, output_file_size)
        """
        try:
            if debug_log:
                logging.basicConfig(level=logging.DEBUG)
                
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(os.path.abspath(output_file))
            if output_dir and not os.path.exists(output_dir):
                if debug_log:
                    logging.debug(f"Creating output directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
            
            if debug_log:
                logging.debug(f"Opening output WAV file: {output_file}")
                
            wav = wave.open(output_file, 'wb')
            wav.setnchannels(channels)
            wav.setsampwidth(sample_width)
            wav.setframerate(sample_rate)
            
            # Initialize codec if specified
            if codec:
                if isinstance(codec, str) and codec.lower() == 'opus':
                    codec = OpusCodec(sample_rate=sample_rate, channels=channels)
                codec.initialize()
                if debug_log:
                    logging.debug(f"Initialized codec: {codec.__class__.__name__}")
            
            packets_processed = 0
            bytes_processed = 0
            start_time = time.time()
            
            print(f"Receiving audio data to {output_file}")
            print(f"Sample rate: {sample_rate}Hz, Channels: {channels}, "
                  f"Sample width: {sample_width} bytes")
            
            # Process packets
            if use_jitter_buffer:
                if debug_log:
                    logging.debug("Using jitter buffer for processing")
                # With jitter buffer
                while self.running or not self.packet_queue.empty() or self.jitter_buffer:
                    # Check timeout
                    if timeout and (time.time() - start_time) > timeout:
                        if debug_log:
                            logging.debug(f"Timeout reached after {timeout} seconds")
                        break
                    
                    # Fill jitter buffer
                    self._fill_jitter_buffer()
                    
                    # Process packets from jitter buffer in sequence
                    processed = self._process_jitter_buffer(wav, codec, debug_log)
                    packets_processed += processed[0]
                    bytes_processed += processed[1]
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.001)
            else:
                # Without jitter buffer (simple processing)
                if debug_log:
                    logging.debug("Using simple processing (no jitter buffer)")
                while self.running or not self.packet_queue.empty():
                    # Check timeout
                    if timeout and (time.time() - start_time) > timeout:
                        if debug_log:
                            logging.debug(f"Timeout reached after {timeout} seconds")
                        break
                    
                    try:
                        packet = self.packet_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    # Decode payload if codec is specified
                    if codec:
                        if debug_log:
                            logging.debug(f"Decoding packet {packet.sequence_number}")
                        try:
                            decoded_data = codec.decode(packet.payload)
                        except Exception as e:
                            if debug_log:
                                logging.error(f"Decode error: {e}")
                            continue
                    else:
                        decoded_data = packet.payload
                    
                    try:
                        if debug_log:
                            logging.debug(f"Writing {len(decoded_data)} bytes to WAV")
                        wav.writeframes(decoded_data)
                    except Exception as e:
                        if debug_log:
                            logging.error(f"WAV write error: {e}")
                        continue
                    
                    packets_processed += 1
                    bytes_processed += len(packet.payload)
            
            if debug_log:
                logging.debug("Closing WAV file")
            wav.close()
            
            # Get output file size
            try:
                output_size = os.path.getsize(output_file)
                if debug_log:
                    logging.debug(f"Output file size: {output_size} bytes")
            except Exception as e:
                if debug_log:
                    logging.error(f"Error getting file size: {e}")
                output_size = 0
            
            print(f"Processed {packets_processed} packets ({bytes_processed} bytes)")
            print(f"Created WAV file: {output_file} ({output_size} bytes)")
            
            return packets_processed, bytes_processed, output_size
            
        except Exception as e:
            logging.error(f"Error saving audio: {e}")
            return 0, 0, 0
            
    def _fill_jitter_buffer(self):
        """Fill the jitter buffer with packets from the queue"""
        # Don't overfill buffer
        while (not self.packet_queue.empty() and 
               len(self.jitter_buffer) < self.jitter_buffer_size):
            try:
                packet = self.packet_queue.get(block=False)
                self.jitter_buffer[packet.sequence_number] = packet
                
                # Initialize next_seq_to_play if not set
                if self.next_seq_to_play is None:
                    self.next_seq_to_play = packet.sequence_number
            except queue.Empty:
                break
                
    def _process_jitter_buffer(self, wav_file, codec=None, debug_log=False):
        """
        Process packets from jitter buffer in sequence.
        
        Returns:
            Tuple of (packets_processed, bytes_processed)
        """
        if self.next_seq_to_play is None:
            return 0, 0
            
        packets_processed = 0
        bytes_processed = 0
        
        # Process all packets in sequence until we hit a gap
        while self.next_seq_to_play in self.jitter_buffer:
            packet = self.jitter_buffer.pop(self.next_seq_to_play)
            
            # Decode payload if codec is specified
            if codec:
                try:
                    decoded_data = codec.decode(packet.payload)
                except Exception as e:
                    if debug_log:
                        logging.error(f"Decode error: {e}")
                    self.next_seq_to_play = (self.next_seq_to_play + 1) % 65536
                    continue
            else:
                decoded_data = packet.payload
            
            try:
                wav_file.writeframes(decoded_data)
            except Exception as e:
                if debug_log:
                    logging.error(f"WAV write error: {e}")
                
            packets_processed += 1
            bytes_processed += len(packet.payload)
            
            # Move to next sequence number
            self.next_seq_to_play = (self.next_seq_to_play + 1) % 65536
        
        return packets_processed, bytes_processed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Receive RTP audio stream and save to WAV file")
    parser.add_argument("output", help="Path to save the output WAV file")
    parser.add_argument("--ip", default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=12345, help="Port to listen on")
    parser.add_argument("--codec", choices=["opus", "none"], default="opus", 
                        help="Audio codec to use")
    parser.add_argument("--sample-rate", type=int, default=48000, 
                        help="Sample rate of the output WAV file")
    parser.add_argument("--channels", type=int, default=1, 
                        help="Number of audio channels")
    parser.add_argument("--sample-width", type=int, default=2, 
                        help="Sample width in bytes")
    parser.add_argument("--timeout", type=int, default=None, 
                        help="How long to receive for in seconds")
    parser.add_argument("--adaptive", action="store_true", 
                        help="Use adaptive receiver with jitter buffer")
    parser.add_argument("--debug", action="store_true", 
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Create codec based on arguments
    if args.codec == "opus":
        from voip_benchmark.codecs.opus import OpusCodec
        codec = OpusCodec(sample_rate=args.sample_rate, channels=args.channels)
    else:
        codec = None
    
    # Create receiver based on arguments
    if args.adaptive:
        receiver = AdaptiveRTPReceiver(args.ip, args.port)
    else:
        receiver = RTPReceiver(args.ip, args.port)
    
    # Start receiving
    receiver.start_receiving()
    
    try:
        # Wait for packets and save to file
        if args.adaptive:
            receiver.save_audio(
                args.output, codec, args.sample_width, args.channels, 
                args.sample_rate, args.timeout, debug_log=args.debug
            )
        else:
            receiver.save_audio(
                args.output, codec, args.sample_width, args.channels, 
                args.sample_rate, args.timeout
            )
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        receiver.stop()
        print("Receiver stopped") 