#!/usr/bin/env python3

import random
import time
import threading
import queue
import logging
import os
import sys
import wave

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from voip_benchmark.rtp.packet import RTPPacket, create_rtp_packet
from voip_benchmark.rtp.sender import RTPSender
from voip_benchmark.rtp.receiver import RTPReceiver
from voip_benchmark.codecs.opus import OpusCodec

class NetworkCondition:
    """
    Represents network conditions for simulation.
    """
    def __init__(self, packet_loss=0.0, jitter=0.0, out_of_order_prob=0.0, 
                 duplicate_prob=0.0):
        """
        Initialize network conditions.
        
        Args:
            packet_loss: Probability of packet loss (0.0 to 1.0)
            jitter: Maximum jitter in seconds (0.0 = no jitter)
            out_of_order_prob: Probability of packet reordering (0.0 to 1.0)
            duplicate_prob: Probability of packet duplication (0.0 to 1.0)
        """
        self.packet_loss = max(0.0, min(1.0, packet_loss))
        self.jitter = max(0.0, jitter)
        self.out_of_order_prob = max(0.0, min(1.0, out_of_order_prob))
        self.duplicate_prob = max(0.0, min(1.0, duplicate_prob))
        
    def __str__(self):
        return (f"NetworkCondition(packet_loss={self.packet_loss:.2f}, "
                f"jitter={self.jitter*1000:.1f}ms, "
                f"out_of_order_prob={self.out_of_order_prob:.2f}, "
                f"duplicate_prob={self.duplicate_prob:.2f})")


class RTPSimulator:
    """
    Simulates RTP transmission with configurable network conditions.
    """
    def __init__(self, network_condition=None):
        """
        Initialize the RTP simulator.
        
        Args:
            network_condition: NetworkCondition object (None = perfect network)
        """
        self.network_condition = network_condition or NetworkCondition()
        self.packet_queue = queue.PriorityQueue()
        self.is_running = False
        self.stats = {
            'packets_sent': 0,
            'packets_received': 0,
            'packets_lost': 0,
            'packets_reordered': 0,
            'packets_duplicated': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }
        
    def _simulate_network_effects(self, packet_tuple):
        """
        Apply network effects to a packet.
        
        Args:
            packet_tuple: Tuple of (priority, sequence_number, packet_data)
            
        Returns:
            List of modified packet tuples, or empty list if packet is dropped
        """
        priority, seq_num, packet_data = packet_tuple
        result = []
        
        # Simulate packet loss
        if random.random() < self.network_condition.packet_loss:
            self.stats['packets_lost'] += 1
            return result  # Empty list = packet dropped
            
        # Simulate jitter
        if self.network_condition.jitter > 0:
            jitter_ms = random.uniform(0, self.network_condition.jitter * 1000)
            priority += jitter_ms / 1000.0
            
        # Add the packet with modified priority
        result.append((priority, seq_num, packet_data))
        
        # Simulate out-of-order delivery
        if random.random() < self.network_condition.out_of_order_prob:
            # Adjust priority to change delivery order
            priority_shift = random.uniform(0.01, 0.1)  # 10-100ms shift
            result[0] = (priority + priority_shift, seq_num, packet_data)
            self.stats['packets_reordered'] += 1
            
        # Simulate packet duplication
        if random.random() < self.network_condition.duplicate_prob:
            # Add duplicate with slightly higher priority
            result.append((priority + 0.001, seq_num, packet_data))
            self.stats['packets_duplicated'] += 1
            
        return result
        
    def _network_thread(self, receiver_callback):
        """
        Network simulation thread that processes packets in the queue.
        
        Args:
            receiver_callback: Function to call with delivered packets
        """
        while self.is_running or not self.packet_queue.empty():
            try:
                # Get packet from queue with timeout
                packet_tuple = self.packet_queue.get(timeout=0.1)
                
                # Apply network effects
                modified_packets = self._simulate_network_effects(packet_tuple)
                
                # Deliver packets to receiver
                for modified_packet in modified_packets:
                    priority, seq_num, packet_data = modified_packet
                    
                    # Calculate delivery time
                    now = time.time()
                    delay = max(0, priority - now)
                    
                    if delay > 0:
                        time.sleep(delay)
                        
                    # Deliver packet
                    if receiver_callback and self.is_running:
                        receiver_callback(packet_data)
                        self.stats['packets_received'] += 1
                        self.stats['bytes_received'] += len(packet_data)
                        
                self.packet_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in network thread: {e}")
                
    def send_packet(self, packet_data):
        """
        Send a packet through the simulated network.
        
        Args:
            packet_data: RTP packet data as bytes
        """
        if not self.is_running:
            return
            
        # Parse packet to get sequence number
        packet = RTPPacket()
        if packet.parse_packet(packet_data):
            seq_num = packet.sequence_number
            
            # Add packet to queue with current time as priority
            self.packet_queue.put((time.time(), seq_num, packet_data))
            
            self.stats['packets_sent'] += 1
            self.stats['bytes_sent'] += len(packet_data)
        else:
            logging.error("Failed to parse packet for sending")
            
    def start(self, receiver_callback):
        """
        Start the network simulator.
        
        Args:
            receiver_callback: Function to call with delivered packets
        """
        if self.is_running:
            return
            
        self.is_running = True
        self.network_thread = threading.Thread(
            target=self._network_thread, 
            args=(receiver_callback,)
        )
        self.network_thread.daemon = True
        self.network_thread.start()
        
    def stop(self):
        """Stop the network simulator."""
        self.is_running = False
        if hasattr(self, 'network_thread'):
            self.network_thread.join(timeout=1.0)
            
    def get_stats(self):
        """Get statistics about the simulated network."""
        return self.stats


def simulate_rtp_transmission(input_file, output_file, packet_loss=0.0, jitter=0.0,
                               codec=None, bitrate=24000, sample_rate=48000, 
                               channels=1, debug=False):
    """
    Simulate RTP transmission of a WAV file with specified network conditions.
    
    Args:
        input_file: Path to input WAV file
        output_file: Path to output WAV file
        packet_loss: Packet loss probability (0.0 to 1.0)
        jitter: Maximum jitter in seconds
        codec: Codec to use ('opus' or None for no encoding)
        bitrate: Bitrate for Opus codec in bps
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        debug: Enable debug logging
        
    Returns:
        Dict with transmission statistics
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    
    # Create network conditions
    network_condition = NetworkCondition(
        packet_loss=packet_loss,
        jitter=jitter,
        out_of_order_prob=0.01,  # Small chance of reordering
        duplicate_prob=0.005     # Small chance of duplication
    )
    
    # Create simulator
    simulator = RTPSimulator(network_condition)
    
    # Create receiver with a queue for passing packets
    packet_queue = queue.Queue()
    
    # Function to pass packets to the receiver
    def receiver_callback(packet_data):
        packet_queue.put(packet_data)
    
    # Start simulator
    simulator.start(receiver_callback)
    
    # Create codec if specified
    if codec == 'opus':
        codec_obj = OpusCodec(
            sample_rate=sample_rate,
            channels=channels,
            bitrate=bitrate
        )
        codec_obj.initialize()
    else:
        codec_obj = None
    
    # Open input file
    try:
        wav = wave.open(input_file, 'rb')
        in_sample_rate = wav.getframerate()
        in_channels = wav.getnchannels()
        in_sample_width = wav.getsampwidth()
        in_frames = wav.getnframes()
        
        # Calculate audio info
        duration_ms = in_frames / in_sample_rate * 1000
        packet_size_ms = 20  # Standard 20ms RTP packets
        packet_frames = int(in_sample_rate * packet_size_ms / 1000)
        bytes_per_sample = in_sample_width * in_channels
        packet_size_bytes = packet_frames * bytes_per_sample
        
        # Calculate expected number of packets
        expected_packets = int(in_frames / packet_frames) + 1
        
        logging.info(f"Input file: {input_file}")
        logging.info(f"Sample rate: {in_sample_rate}Hz, Channels: {in_channels}")
        logging.info(f"Duration: {duration_ms:.1f}ms, Expected packets: {expected_packets}")
        logging.info(f"Network conditions: {network_condition}")
        
        # Prepare for transmission
        sequence_number = random.randint(0, 65535)
        timestamp = random.randint(0, 0xFFFFFFFF)
        ssrc = random.randint(0, 0xFFFFFFFF)
        
        # Start receiver thread to process incoming packets
        receiver_thread_stop = threading.Event()
        received_packets = []
        
        def receiver_thread_func():
            while not receiver_thread_stop.is_set() or not packet_queue.empty():
                try:
                    packet_data = packet_queue.get(timeout=0.1)
                    packet = RTPPacket()
                    if packet.parse_packet(packet_data):
                        received_packets.append(packet)
                    packet_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"Error in receiver thread: {e}")
        
        receiver_thread = threading.Thread(target=receiver_thread_func)
        receiver_thread.daemon = True
        receiver_thread.start()
        
        # Send packets
        total_bytes = 0
        packets_sent = 0
        
        data = wav.readframes(packet_frames)
        while data:
            # Encode data if codec is specified
            if codec_obj:
                encoded_data = codec_obj.encode(data)
            else:
                encoded_data = data
                
            # Create RTP packet
            packet = create_rtp_packet(
                payload=encoded_data,
                seq_num=sequence_number,
                timestamp=timestamp,
                ssrc=ssrc,
                payload_type=96 if codec_obj else 0
            )
            
            # Send through simulator
            simulator.send_packet(packet.get_packet())
            
            # Update counters
            sequence_number = (sequence_number + 1) % 65536
            timestamp = (timestamp + packet_frames) % 0x100000000
            total_bytes += len(encoded_data)
            packets_sent += 1
            
            # Small delay to simulate real-time transmission
            time.sleep(packet_size_ms / 1000.0)
            
            # Get next frame
            data = wav.readframes(packet_frames)
        
        wav.close()
        
        # Wait for all packets to be processed
        time.sleep(jitter + 0.5)  # Wait at least jitter time plus some margin
        
        # Stop receiver thread
        receiver_thread_stop.set()
        receiver_thread.join()
        
        # Sort received packets by sequence number
        received_packets.sort(key=lambda p: p.sequence_number)
        
        # Create output file
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            out_wav = wave.open(output_file, 'wb')
            out_wav.setnchannels(in_channels)
            out_wav.setsampwidth(in_sample_width)
            out_wav.setframerate(in_sample_rate)
            
            # Process packets
            for packet in received_packets:
                # Decode payload if codec is specified
                if codec_obj:
                    try:
                        decoded_data = codec_obj.decode(packet.payload)
                        out_wav.writeframes(decoded_data)
                    except Exception as e:
                        logging.error(f"Error decoding packet: {e}")
                else:
                    out_wav.writeframes(packet.payload)
            
            out_wav.close()
            
            # Calculate statistics
            input_size = os.path.getsize(input_file)
            output_size = os.path.getsize(output_file)
            compression_ratio = total_bytes / input_size if input_size > 0 else 0
            packet_loss_pct = 100 * (packets_sent - len(received_packets)) / packets_sent if packets_sent > 0 else 0
            
            result = {
                'input_file': input_file,
                'output_file': output_file,
                'input_size': input_size,
                'output_size': output_size,
                'encoded_size': total_bytes,
                'compression_ratio': compression_ratio,
                'packets_sent': packets_sent,
                'packets_received': len(received_packets),
                'packet_loss_pct': packet_loss_pct,
                'network_condition': str(network_condition),
                'codec': codec,
                'bitrate': bitrate if codec == 'opus' else None
            }
            
            logging.info(f"Transmission complete:")
            logging.info(f"Sent {packets_sent} packets, received {len(received_packets)}")
            logging.info(f"Packet loss: {packet_loss_pct:.1f}%")
            logging.info(f"Input size: {input_size} bytes, Encoded size: {total_bytes} bytes")
            logging.info(f"Compression ratio: {compression_ratio:.3f}")
            logging.info(f"Output file: {output_file} ({output_size} bytes)")
            
            return result
            
        except Exception as e:
            logging.error(f"Error creating output file: {e}")
            return {'error': str(e)}
            
    except Exception as e:
        logging.error(f"Error processing input file: {e}")
        return {'error': str(e)}
    finally:
        # Clean up
        simulator.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate RTP transmission with network conditions")
    parser.add_argument("input", help="Path to input WAV file")
    parser.add_argument("output", help="Path to output WAV file")
    parser.add_argument("--packet-loss", type=float, default=0.0, 
                        help="Packet loss probability (0.0 to 1.0)")
    parser.add_argument("--jitter", type=float, default=0.0, 
                        help="Maximum jitter in milliseconds")
    parser.add_argument("--codec", choices=["opus", "none"], default="opus", 
                        help="Audio codec to use")
    parser.add_argument("--bitrate", type=int, default=24000, 
                        help="Bitrate for Opus codec in bps")
    parser.add_argument("--debug", action="store_true", 
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Convert jitter from ms to seconds
    jitter_seconds = args.jitter / 1000.0
    
    # Run simulation
    simulate_rtp_transmission(
        args.input, 
        args.output, 
        packet_loss=args.packet_loss,
        jitter=jitter_seconds,
        codec=args.codec if args.codec != "none" else None,
        bitrate=args.bitrate,
        debug=args.debug
    ) 