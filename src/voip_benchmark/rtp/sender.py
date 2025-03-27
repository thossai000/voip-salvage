#!/usr/bin/env python3

import socket
import time
import wave
import struct
import random
import os
import sys
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from voip_benchmark.rtp.packet import RTPPacket
from voip_benchmark.codecs.opus import OpusCodec

class RTPSender:
    """
    Sends RTP packets with audio data.
    Basic implementation without advanced features like RTCP.
    """
    def __init__(self, dest_ip="127.0.0.1", dest_port=12345, payload_type=96):
        self.dest_ip = dest_ip
        self.dest_port = dest_port
        self.payload_type = payload_type
        self.seq_num = random.randint(0, 65535)
        self.timestamp = random.randint(0, 0xFFFFFFFF)
        self.ssrc = random.randint(0, 0xFFFFFFFF)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.packets_sent = 0
        self.bytes_sent = 0
        
    def send_audio_file(self, filepath, codec=None, packet_size=20):
        """
        Reads an audio file and sends it as RTP packets.
        
        Args:
            filepath: Path to the audio file (.wav)
            codec: Audio codec to use for encoding (default: None = raw PCM)
            packet_size: Audio duration in milliseconds per packet
        
        Returns:
            Tuple of (packets_sent, bytes_sent)
        """
        try:
            wav = wave.open(filepath, 'rb')
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            
            # If codec is specified, initialize it
            if codec:
                if isinstance(codec, str) and codec.lower() == 'opus':
                    codec = OpusCodec(sample_rate=sample_rate, channels=channels)
                codec.initialize()
            
            # Calculate samples per packet
            samples_per_packet = int(sample_rate * packet_size / 1000)
            bytes_per_sample = sample_width * channels
            bytes_per_packet = samples_per_packet * bytes_per_sample
            
            # Timestamp increment per packet
            ts_increment = samples_per_packet
            
            print(f"Opening {filepath}")
            print(f"Sample rate: {sample_rate}Hz, Channels: {channels}, "
                  f"Sample width: {sample_width} bytes")
            print(f"Sending audio as {packet_size}ms packets "
                  f"({samples_per_packet} samples per packet)")
            
            # Reset counters
            self.packets_sent = 0
            self.bytes_sent = 0
            
            # Read and send audio data
            data = wav.readframes(samples_per_packet)
            while data:
                # Encode data if codec is specified
                if codec:
                    encoded_data = codec.encode(data)
                else:
                    encoded_data = data
                
                # Create and send RTP packet
                packet = RTPPacket(
                    payload_type=self.payload_type,
                    sequence_number=self.seq_num,
                    timestamp=self.timestamp,
                    ssrc=self.ssrc,
                    payload=encoded_data
                )
                
                packet_bytes = packet.get_packet()
                self.sock.sendto(packet_bytes, (self.dest_ip, self.dest_port))
                
                # Update sequence number and timestamp
                self.seq_num = (self.seq_num + 1) % 65536
                self.timestamp = (self.timestamp + ts_increment) % 0x100000000
                
                # Update counters
                self.packets_sent += 1
                self.bytes_sent += len(packet_bytes)
                
                # Get next frame
                data = wav.readframes(samples_per_packet)
                
                # Sleep to simulate real-time streaming
                time.sleep(packet_size / 1000.0)
            
            wav.close()
            print(f"Sent {self.packets_sent} packets ({self.bytes_sent} bytes)")
            return self.packets_sent, self.bytes_sent
            
        except Exception as e:
            logging.error(f"Error sending audio file: {e}")
            return 0, 0
    
    def close(self):
        """Close the socket connection"""
        self.sock.close()


class AdaptiveRTPSender(RTPSender):
    """
    Enhanced RTP sender with adaptive bitrate control
    """
    def __init__(self, dest_ip="127.0.0.1", dest_port=12345, payload_type=96, 
                 initial_bitrate=24000, min_bitrate=8000, max_bitrate=128000):
        super().__init__(dest_ip, dest_port, payload_type)
        self.initial_bitrate = initial_bitrate
        self.current_bitrate = initial_bitrate
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        
    def send_audio_file(self, filepath, codec=None, packet_size=20, 
                         adaptive=True, strategy="balanced"):
        """
        Reads an audio file and sends it as RTP packets with adaptive bitrate.
        
        Args:
            filepath: Path to the audio file (.wav)
            codec: Audio codec to use (default: OpusCodec if None)
            packet_size: Audio duration in milliseconds per packet
            adaptive: Whether to adapt bitrate based on network conditions
            strategy: Bitrate adaptation strategy: "balanced", "quality", or "aggressive"
        
        Returns:
            Tuple of (packets_sent, bytes_sent)
        """
        try:
            wav = wave.open(filepath, 'rb')
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            
            # Initialize codec if not provided
            if codec is None:
                from voip_benchmark.codecs.opus import OpusCodec
                codec = OpusCodec(
                    sample_rate=sample_rate, 
                    channels=channels,
                    bitrate=self.initial_bitrate
                )
            
            codec.initialize()
            
            # Initialize adaptive bitrate controller if needed
            if adaptive:
                from voip_benchmark.utils.adaptive_bitrate import AdaptiveBitrateController
                bitrate_controller = AdaptiveBitrateController(
                    initial_bitrate=self.initial_bitrate,
                    min_bitrate=self.min_bitrate,
                    max_bitrate=self.max_bitrate,
                    strategy=strategy
                )
            
            # Proceed with the regular sending process
            result = super().send_audio_file(filepath, codec, packet_size)
            
            return result
        
        except Exception as e:
            logging.error(f"Error in adaptive sending: {e}")
            return 0, 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Send audio file over RTP")
    parser.add_argument("file", help="Path to WAV file to send")
    parser.add_argument("--ip", default="127.0.0.1", help="Destination IP address")
    parser.add_argument("--port", type=int, default=12345, help="Destination port")
    parser.add_argument("--codec", choices=["opus", "none"], default="opus", 
                        help="Audio codec to use")
    parser.add_argument("--bitrate", type=int, default=24000, 
                        help="Bitrate for Opus codec in bps")
    parser.add_argument("--packet-size", type=int, default=20, 
                        help="Packet size in milliseconds")
    parser.add_argument("--adaptive", action="store_true", 
                        help="Enable adaptive bitrate")
    parser.add_argument("--strategy", choices=["balanced", "quality", "aggressive"], 
                        default="balanced", help="Adaptation strategy")
    
    args = parser.parse_args()
    
    # Create codec based on arguments
    if args.codec == "opus":
        from voip_benchmark.codecs.opus import OpusCodec
        codec = OpusCodec(bitrate=args.bitrate)
    else:
        codec = None
    
    # Create sender based on arguments
    if args.adaptive:
        sender = AdaptiveRTPSender(args.ip, args.port, initial_bitrate=args.bitrate)
        sender.send_audio_file(args.file, codec, args.packet_size, 
                               adaptive=True, strategy=args.strategy)
    else:
        sender = RTPSender(args.ip, args.port)
        sender.send_audio_file(args.file, codec, args.packet_size)
    
    sender.close() 