#!/usr/bin/env python3
"""
Simple VoIP benchmark example

This script demonstrates how to use the voip_benchmark package
to simulate a VoIP call under various network conditions and
measure the audio quality.
"""

import os
import time
import numpy as np
import argparse
from voip_benchmark import (
    get_codec, 
    RTPSession, 
    RTPStream, 
    NetworkSimulator, 
    NetworkConditions,
    AdaptiveBitrateController
)
from voip_benchmark.utils.audio import (
    read_wav_file, 
    write_wav_file, 
    generate_sine_wave, 
    audio_signal_statistics
)
from voip_benchmark.utils.statistics import calculate_mos, calculate_compression_ratio

def main():
    """Run a simple VoIP benchmark with simulated network conditions"""
    
    parser = argparse.ArgumentParser(description="Run a VoIP benchmark simulation")
    parser.add_argument("--input", type=str, help="Input WAV file (if not specified, a test tone will be generated)")
    parser.add_argument("--output", type=str, default="output.wav", help="Output WAV file")
    parser.add_argument("--codec", type=str, default="opus", help="Audio codec to use")
    parser.add_argument("--bitrate", type=int, default=64000, help="Codec bitrate in bps")
    parser.add_argument("--packet-loss", type=float, default=0.0, help="Simulated packet loss (0.0-1.0)")
    parser.add_argument("--jitter", type=float, default=0.0, help="Simulated jitter in ms")
    parser.add_argument("--latency", type=float, default=0.0, help="Simulated latency in ms")
    parser.add_argument("--adaptive", action="store_true", help="Use adaptive bitrate control")
    args = parser.parse_args()
    
    # Generate or load input audio
    if args.input:
        print(f"Reading audio file: {args.input}")
        audio_data, sample_rate = read_wav_file(args.input)
    else:
        print("Generating test tone (3 seconds, 440Hz)")
        duration = 3.0
        sample_rate = 48000
        audio_data = generate_sine_wave(440, duration, sample_rate)
    
    # Initialize codec
    print(f"Using codec: {args.codec} at {args.bitrate/1000} kbps")
    codec = get_codec(args.codec)(sample_rate=sample_rate, channels=1, bitrate=args.bitrate)
    
    # Set up network simulation
    network_conditions = NetworkConditions(
        packet_loss=args.packet_loss,
        jitter=args.jitter,
        latency=args.latency
    )
    network = NetworkSimulator(conditions=network_conditions)
    print(f"Network conditions: packet loss={args.packet_loss*100}%, jitter={args.jitter}ms, latency={args.latency}ms")
    
    # Set up adaptive bitrate controller if needed
    if args.adaptive:
        print("Using adaptive bitrate control")
        adaptive_controller = AdaptiveBitrateController(codec)
        network.set_stats_callback(adaptive_controller.on_network_statistics)
    
    # Create sender and receiver
    print("Setting up RTP streaming...")
    sender = RTPStream(codec, packet_duration=20)
    receiver = RTPStream(codec, packet_duration=20)
    
    # Process the audio
    print("Processing audio...")
    start_time = time.time()
    
    # Encode and create RTP packets
    rtp_packets = sender.prepare_packets(audio_data)
    
    # Simulate network transmission
    received_packets = []
    for packet in rtp_packets:
        # Apply network conditions
        if network.should_transmit(packet):
            # Add network delay if needed
            if network.get_delay() > 0:
                time.sleep(network.get_delay() / 1000.0)  # Convert ms to seconds
            received_packets.append(packet)
    
    # Decode received packets
    received_audio = receiver.process_packets(received_packets)
    
    elapsed_time = time.time() - start_time
    print(f"Processing completed in {elapsed_time:.2f} seconds")
    
    # Calculate statistics
    original_stats = audio_signal_statistics(audio_data)
    received_stats = audio_signal_statistics(received_audio)
    
    # Calculate quality metrics
    packet_loss_rate = 1.0 - (len(received_packets) / len(rtp_packets))
    mos = calculate_mos(packet_loss_rate, args.jitter, codec.bitrate)
    
    print("\nResults:")
    print(f"Original duration: {len(audio_data)/sample_rate:.2f}s, Received duration: {len(received_audio)/sample_rate:.2f}s")
    print(f"Packets sent: {len(rtp_packets)}, Packets received: {len(received_packets)}")
    print(f"Packet loss: {packet_loss_rate*100:.2f}%")
    print(f"Estimated MOS: {mos:.2f}/5.0")
    
    # Write output file
    write_wav_file(args.output, received_audio, sample_rate)
    print(f"Output written to: {args.output}")

if __name__ == "__main__":
    main() 