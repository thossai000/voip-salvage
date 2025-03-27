"""
Command-line interface for VoIP benchmarking tool.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

from .benchmark import VoIPBenchmark
from .utils.config import (
    load_config_file, get_default_config, merge_configs,
    save_config, get_config_schema, validate_config
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="VoIP Benchmarking Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Add common arguments
    parser.add_argument(
        '-c', '--config',
        help="Path to configuration file",
        type=str
    )
    
    parser.add_argument(
        '-v', '--verbose',
        help="Increase output verbosity",
        action='store_true'
    )
    
    # Add subparsers for commands
    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        help='Command to run'
    )
    
    # Run benchmark command
    run_parser = subparsers.add_parser(
        'run',
        help='Run benchmark'
    )
    
    run_parser.add_argument(
        '-i', '--input',
        help="Path to input WAV file",
        type=str,
        required=True
    )
    
    run_parser.add_argument(
        '-o', '--output',
        help="Directory for output files",
        type=str
    )
    
    run_parser.add_argument(
        '--network-condition',
        help="Specific network condition to test",
        type=str
    )
    
    # Compare codecs command
    compare_parser = subparsers.add_parser(
        'compare',
        help='Compare different codecs'
    )
    
    compare_parser.add_argument(
        '-i', '--input',
        help="Path to input WAV file",
        type=str,
        required=True
    )
    
    compare_parser.add_argument(
        '-o', '--output',
        help="Directory for output files",
        type=str
    )
    
    compare_parser.add_argument(
        '--network-condition',
        help="Specific network condition to test",
        type=str
    )
    
    compare_parser.add_argument(
        '--codecs',
        help="Comma-separated list of codecs to compare",
        type=str,
        default='opus'
    )
    
    compare_parser.add_argument(
        '--bitrates',
        help="Comma-separated list of bitrates to test (in kbps)",
        type=str,
        default='64,32,16'
    )
    
    # Generate config command
    config_parser = subparsers.add_parser(
        'config',
        help='Generate default configuration file'
    )
    
    config_parser.add_argument(
        '-o', '--output',
        help="Output file path",
        type=str,
        required=True
    )
    
    config_parser.add_argument(
        '--format',
        help="Output file format",
        choices=['json', 'yaml'],
        default='json'
    )
    
    return parser.parse_args()


def load_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Load configuration from command-line arguments.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Configuration dictionary
    """
    # Start with default configuration
    config = get_default_config()
    
    # Load configuration file if specified
    if args.config:
        try:
            file_config = load_config_file(args.config)
            config = merge_configs(config, file_config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)
    
    # Apply command-line overrides
    if args.verbose:
        config['general']['log_level'] = 'debug'
    
    # Validate configuration
    schema = get_config_schema()
    errors = validate_config(config, schema)
    if errors:
        print("Configuration validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    return config


def get_network_condition(config: Dict[str, Any], name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Get a specific network condition from configuration.
    
    Args:
        config: Configuration dictionary
        name: Name of the network condition (if None, returns None)
        
    Returns:
        Network condition dictionary or None
    """
    if name is None:
        return None
    
    conditions = config['benchmark']['network_conditions']
    for condition in conditions:
        if condition['name'] == name:
            return condition
    
    print(f"Network condition '{name}' not found")
    print("Available conditions:")
    for condition in conditions:
        print(f"  - {condition['name']}")
    
    sys.exit(1)


def run_benchmark(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Run benchmark command.
    
    Args:
        args: Command-line arguments
        config: Configuration dictionary
    """
    # Get network condition
    network_condition = get_network_condition(config, args.network_condition)
    network_conditions = [network_condition] if network_condition else None
    
    # Create benchmark
    benchmark = VoIPBenchmark(config)
    
    # Run benchmark
    try:
        benchmark.run_benchmark(
            input_file=args.input,
            output_dir=args.output,
            network_conditions=network_conditions
        )
        print("Benchmark completed successfully")
    except Exception as e:
        print(f"Error running benchmark: {e}")
        sys.exit(1)


def run_compare(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Run codec comparison command.
    
    Args:
        args: Command-line arguments
        config: Configuration dictionary
    """
    # Get network condition
    network_condition = get_network_condition(config, args.network_condition)
    
    # Parse codecs and bitrates
    codec_names = [name.strip() for name in args.codecs.split(',')]
    bitrates = [int(rate.strip()) * 1000 for rate in args.bitrates.split(',')]
    
    # Build codec configurations
    codecs = []
    for codec_name in codec_names:
        # Get default config for this codec
        if codec_name in config['codec']:
            codec_config = config['codec']
        else:
            codec_config = {'type': codec_name}
        
        # Create a configuration for each bitrate
        for bitrate in bitrates:
            codec_copy = codec_config.copy()
            codec_copy['bitrate'] = bitrate
            codecs.append(codec_copy)
    
    # Create benchmark
    benchmark = VoIPBenchmark(config)
    
    # Run comparison
    try:
        benchmark.compare_codecs(
            input_file=args.input,
            codecs=codecs,
            network_condition=network_condition,
            output_dir=args.output
        )
        print("Codec comparison completed successfully")
    except Exception as e:
        print(f"Error running codec comparison: {e}")
        sys.exit(1)


def generate_config(args: argparse.Namespace) -> None:
    """Generate default configuration file.
    
    Args:
        args: Command-line arguments
    """
    config = get_default_config()
    
    try:
        save_config(config, args.output, args.format)
        print(f"Default configuration saved to {args.output}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Parse arguments
    args = parse_args()
    
    # Check if command is specified
    if args.command is None:
        print("No command specified")
        print("Use --help for command usage")
        sys.exit(1)
    
    # Handle config command
    if args.command == 'config':
        generate_config(args)
        return
    
    # Load configuration
    config = load_config_from_args(args)
    
    # Dispatch command
    if args.command == 'run':
        run_benchmark(args, config)
    elif args.command == 'compare':
        run_compare(args, config)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main() 