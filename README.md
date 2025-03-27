# VoIP Benchmark

A comprehensive benchmarking tool for evaluating VoIP (Voice over IP) quality under various network conditions.

## Features

- Test VoIP quality across different network conditions (packet loss, latency, jitter)
- Compare multiple audio codecs at various bitrates
- Calculate standard VoIP quality metrics (MOS, PSNR, PESQ)
- Generate detailed reports and statistics
- Simulate network impairments
- Support for Opus codec (extensible to other codecs)
- Cross-platform support (Windows, macOS, Linux)

## Installation

### Prerequisites

- Python 3.7 or higher
- pip package manager

### Basic Installation

```bash
# Clone the repository
git clone https://github.com/voipbenchmark/voip_benchmark.git
cd voip_benchmark

# Install the package
pip install .
```

### Installation with Extra Features

```bash
# Install with Opus codec support
pip install ".[opus]"

# Install with PESQ quality metric support
pip install ".[pesq]"

# Install with all features
pip install ".[opus,pesq]"

# Install with development tools
pip install ".[dev]"
```

## Usage

VoIP Benchmark provides a command-line interface with several commands:

### Basic Benchmark

Run a basic benchmark with default settings:

```bash
voip-benchmark run -i input.wav
```

### Compare Codecs

Compare different codecs and bitrates:

```bash
voip-benchmark compare -i input.wav --codecs opus --bitrates 64,32,16
```

### Generate Default Configuration

Generate a default configuration file:

```bash
voip-benchmark config -o config.json
```

### Command-Line Options

Common options:

- `-c, --config`: Path to configuration file
- `-v, --verbose`: Increase output verbosity
- `-i, --input`: Path to input WAV file
- `-o, --output`: Directory for output files

Run-specific options:

- `--network-condition`: Specific network condition to test

Compare-specific options:

- `--codecs`: Comma-separated list of codecs to compare
- `--bitrates`: Comma-separated list of bitrates to test (in kbps)

Config-specific options:

- `--format`: Output file format (json or yaml)

### Using a Configuration File

You can customize the benchmark by providing a configuration file:

```bash
voip-benchmark -c my_config.json run -i input.wav
```

## Configuration

VoIP Benchmark can be configured using JSON or YAML files. Here's an example configuration:

```json
{
  "general": {
    "log_level": "info",
    "log_dir": "./logs",
    "result_dir": "./results",
    "temp_dir": "./tmp"
  },
  "audio": {
    "sample_rate": 48000,
    "channels": 1,
    "sample_width": 2,
    "frame_size": 960,
    "input_device": null,
    "output_device": null
  },
  "codec": {
    "type": "opus",
    "bitrate": 64000,
    "complexity": 10,
    "adaptive_bitrate": true,
    "fec": true,
    "dtx": false
  },
  "network": {
    "local_ip": "0.0.0.0",
    "remote_ip": "127.0.0.1",
    "port": 50000,
    "jitter_buffer_size": 50
  },
  "benchmark": {
    "duration": 30,
    "warm_up": 5,
    "cool_down": 2,
    "repeat": 1,
    "network_conditions": [
      {
        "name": "perfect",
        "packet_loss": 0.0,
        "latency": 0,
        "jitter": 0
      },
      {
        "name": "good",
        "packet_loss": 0.01,
        "latency": 20,
        "jitter": 5
      },
      {
        "name": "poor",
        "packet_loss": 0.05,
        "latency": 100,
        "jitter": 30
      }
    ]
  }
}
```

## Output and Reports

VoIP Benchmark generates several output files:

- JSON reports with detailed metrics and statistics
- Decoded audio files for each test case
- Text reports with human-readable summaries
- Log files containing execution details

Example text report:

```
VoIP Quality Report
=================

MOS Score: 4.15 (Good)
Packet Loss: 1.00% (Good)
Latency: 20.0 ms (Good)
Jitter: 5.0 ms (Good)

Network Metrics
--------------
Network Bandwidth: 80.0 kbps
Effective Bitrate: 63.4 kbps
Protocol Overhead: 20.0%

Detailed Statistics
------------------
Jitter (ms): min=0.0, avg=5.0, max=15.2, p95=12.3
Latency (ms): min=18.2, avg=20.0, max=25.6, p95=24.2
Audio: RMS=0.124, Peak=0.857, Dynamics=16.8 dB
Silence: 12.5% of samples
```

## Architecture

VoIP Benchmark consists of several components:

1. **Codecs**: Audio encoding/decoding (Opus with adaptive bitrate)
2. **RTP**: Real-time Transport Protocol implementation
3. **Network Simulator**: Simulates network conditions and impairments
4. **Benchmark Engine**: Orchestrates tests and collects metrics
5. **Statistics**: Calculates quality metrics and generates reports
6. **CLI**: Command-line interface for running benchmarks

## Development

### Project Structure

```
voip_benchmark/
├── codecs/              # Audio codec implementations
│   ├── base.py          # Abstract base codec class
│   ├── opus.py          # Opus codec implementation
│   └── adaptive_bitrate.py # Adaptive bitrate control
├── rtp/                 # RTP implementation
│   ├── packet.py        # RTP packet handling
│   ├── session.py       # RTP session management
│   └── stream.py        # Audio streaming over RTP
├── utils/               # Utility modules
│   ├── audio.py         # Audio processing utilities
│   ├── config.py        # Configuration management
│   ├── logging.py       # Logging utilities
│   ├── network.py       # Network utilities
│   └── statistics.py    # Statistical analysis
├── benchmark.py         # Main benchmarking functionality
└── __main__.py          # CLI entry point
```

### Running Tests

```bash
# Install development dependencies
pip install ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=voip_benchmark
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ITU-T for standardized VoIP quality metrics
- The Opus codec community for their excellent audio codec
- Open-source RTP implementations that inspired this project

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 