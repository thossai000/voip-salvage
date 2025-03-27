"""
Configuration Utilities

This module provides utilities for loading, validating, and managing configuration.
"""

import os
import sys
import json
import yaml
import argparse
import copy
from typing import Dict, List, Any, Optional, Union, Set, Callable, TypeVar, cast
from pathlib import Path

# Type for configuration dictionaries
ConfigDict = Dict[str, Any]
T = TypeVar('T')

# Default configuration
DEFAULT_CONFIG = {
    # General settings
    'general': {
        'log_level': 'info',
        'log_dir': './logs',
        'result_dir': './results',
        'temp_dir': './tmp',
    },
    
    # Audio settings
    'audio': {
        'sample_rate': 48000,
        'channels': 1,
        'sample_width': 2,  # bytes (16-bit)
        'frame_size': 960,  # samples (20ms @ 48kHz)
        'input_device': None,
        'output_device': None,
    },
    
    # Codec settings
    'codec': {
        'type': 'opus',
        'bitrate': 64000,  # bits per second
        'complexity': 10,
        'adaptive_bitrate': True,
        'fec': True,
        'dtx': False,
    },
    
    # Network settings
    'network': {
        'local_ip': '0.0.0.0',
        'remote_ip': '127.0.0.1',
        'port': 50000,
        'jitter_buffer_size': 50,  # ms
    },
    
    # Benchmark settings
    'benchmark': {
        'duration': 30,  # seconds
        'warm_up': 5,  # seconds
        'cool_down': 2,  # seconds
        'repeat': 1,
        'network_conditions': [
            {
                'name': 'perfect',
                'packet_loss': 0.0,
                'latency': 0,
                'jitter': 0,
            },
            {
                'name': 'good',
                'packet_loss': 0.01,
                'latency': 20,
                'jitter': 5,
            },
            {
                'name': 'poor',
                'packet_loss': 0.05,
                'latency': 100,
                'jitter': 30,
            },
        ],
    },
}


def load_config_file(config_path: Union[str, Path]) -> ConfigDict:
    """Load configuration from a file.
    
    Supports JSON, YAML, and Python files.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If the configuration file does not exist
        ValueError: If the configuration file has an unsupported format
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load based on file extension
    suffix = config_path.suffix.lower()
    
    if suffix == '.json':
        with open(config_path, 'r') as f:
            return json.load(f)
    elif suffix in ('.yaml', '.yml'):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    elif suffix == '.py':
        # Load Python file as a module
        import importlib.util
        spec = importlib.util.spec_from_file_location("config_module", config_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load Python configuration file: {config_path}")
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        # Extract configuration from module
        config = {}
        for key in dir(config_module):
            if not key.startswith('_'):
                value = getattr(config_module, key)
                if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    config[key] = value
        
        return config
    else:
        raise ValueError(f"Unsupported configuration file format: {suffix}")


def merge_configs(base_config: ConfigDict, override_config: ConfigDict) -> ConfigDict:
    """Merge two configuration dictionaries.
    
    The override_config values take precedence over base_config values.
    
    Args:
        base_config: Base configuration dictionary
        override_config: Override configuration dictionary
        
    Returns:
        Merged configuration dictionary
    """
    # Make a deep copy of the base configuration
    result = copy.deepcopy(base_config)
    
    # Recursively merge dictionaries
    for key, value in override_config.items():
        if (
            key in result and
            isinstance(result[key], dict) and
            isinstance(value, dict)
        ):
            # Recursively merge nested dictionaries
            result[key] = merge_configs(result[key], value)
        else:
            # Override or add value
            result[key] = copy.deepcopy(value)
    
    return result


def get_default_config() -> ConfigDict:
    """Get the default configuration.
    
    Returns:
        Default configuration dictionary
    """
    return copy.deepcopy(DEFAULT_CONFIG)


def validate_config(config: ConfigDict, schema: Optional[Dict[str, Any]] = None) -> List[str]:
    """Validate a configuration dictionary against a schema.
    
    Args:
        config: Configuration dictionary to validate
        schema: Schema dictionary (if None, no validation is performed)
        
    Returns:
        List of validation error messages (empty if validation passed)
    """
    if schema is None:
        return []
    
    # Try to use jsonschema for validation
    try:
        import jsonschema
        
        errors = []
        try:
            jsonschema.validate(config, schema)
        except jsonschema.exceptions.ValidationError as e:
            errors.append(str(e))
        
        return errors
    except ImportError:
        # Fall back to basic validation
        return _basic_validate_config(config, schema)


def _basic_validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Basic validation of configuration against a schema.
    
    This is a fallback when jsonschema is not available.
    
    Args:
        config: Configuration dictionary to validate
        schema: Schema dictionary
        
    Returns:
        List of validation error messages (empty if validation passed)
    """
    errors = []
    
    # Check required properties
    if 'required' in schema:
        for key in schema['required']:
            if key not in config:
                errors.append(f"Required property '{key}' is missing")
    
    # Check property types
    if 'properties' in schema:
        for key, prop_schema in schema['properties'].items():
            if key in config:
                value = config[key]
                
                # Check type
                if 'type' in prop_schema:
                    type_name = prop_schema['type']
                    
                    if type_name == 'object' and not isinstance(value, dict):
                        errors.append(f"Property '{key}' should be an object")
                    elif type_name == 'array' and not isinstance(value, list):
                        errors.append(f"Property '{key}' should be an array")
                    elif type_name == 'string' and not isinstance(value, str):
                        errors.append(f"Property '{key}' should be a string")
                    elif type_name == 'number' and not isinstance(value, (int, float)):
                        errors.append(f"Property '{key}' should be a number")
                    elif type_name == 'integer' and not isinstance(value, int):
                        errors.append(f"Property '{key}' should be an integer")
                    elif type_name == 'boolean' and not isinstance(value, bool):
                        errors.append(f"Property '{key}' should be a boolean")
                
                # Recursively validate nested objects
                if isinstance(value, dict) and 'properties' in prop_schema:
                    nested_errors = _basic_validate_config(value, prop_schema)
                    for error in nested_errors:
                        errors.append(f"{key}.{error}")
                
                # Validate array items
                if isinstance(value, list) and 'items' in prop_schema:
                    item_schema = prop_schema['items']
                    for i, item in enumerate(value):
                        if isinstance(item, dict) and 'properties' in item_schema:
                            nested_errors = _basic_validate_config(item, item_schema)
                            for error in nested_errors:
                                errors.append(f"{key}[{i}].{error}")
    
    return errors


def save_config(config: ConfigDict, file_path: Union[str, Path], format: str = 'json') -> None:
    """Save a configuration dictionary to a file.
    
    Args:
        config: Configuration dictionary
        file_path: Path to save the configuration file
        format: File format ('json' or 'yaml')
        
    Raises:
        ValueError: If the format is not supported
    """
    file_path = Path(file_path)
    
    # Create parent directory if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save based on format
    format = format.lower()
    
    if format == 'json':
        with open(file_path, 'w') as f:
            json.dump(config, f, indent=2)
    elif format in ('yaml', 'yml'):
        with open(file_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    else:
        raise ValueError(f"Unsupported configuration format: {format}")


def get_config_value(
    config: ConfigDict,
    path: str,
    default: Optional[T] = None
) -> Optional[T]:
    """Get a value from a configuration dictionary using a dot-notation path.
    
    Args:
        config: Configuration dictionary
        path: Dot-notation path (e.g., 'general.log_level')
        default: Default value to return if the path is not found
        
    Returns:
        Configuration value or default if not found
    """
    # Split path into components
    parts = path.split('.')
    
    # Traverse the configuration dictionary
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    
    return cast(T, current)


def set_config_value(config: ConfigDict, path: str, value: Any) -> None:
    """Set a value in a configuration dictionary using a dot-notation path.
    
    Creates intermediate dictionaries if they don't exist.
    
    Args:
        config: Configuration dictionary
        path: Dot-notation path (e.g., 'general.log_level')
        value: Value to set
    """
    # Split path into components
    parts = path.split('.')
    
    # Traverse the configuration dictionary
    current = config
    for i, part in enumerate(parts[:-1]):
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    
    # Set the value
    current[parts[-1]] = value


def create_argument_parser(
    description: str = "VoIP Benchmark",
    config_help: str = "Path to configuration file"
) -> argparse.ArgumentParser:
    """Create an argument parser for command-line arguments.
    
    Args:
        description: Description of the program
        config_help: Help text for the configuration file argument
        
    Returns:
        Argument parser
    """
    parser = argparse.ArgumentParser(description=description)
    
    # Add common arguments
    parser.add_argument(
        '-c', '--config',
        help=config_help,
        type=str
    )
    
    parser.add_argument(
        '-v', '--verbose',
        help="Increase output verbosity",
        action='store_true'
    )
    
    parser.add_argument(
        '--log-level',
        help="Set log level",
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        type=str
    )
    
    parser.add_argument(
        '--log-dir',
        help="Directory for log files",
        type=str
    )
    
    return parser


def load_config_from_args(args: argparse.Namespace) -> ConfigDict:
    """Load configuration from command-line arguments.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Configuration dictionary
    """
    # Start with default configuration
    config = get_default_config()
    
    # Load configuration file if specified
    if hasattr(args, 'config') and args.config:
        file_config = load_config_file(args.config)
        config = merge_configs(config, file_config)
    
    # Apply command-line overrides
    cli_config: ConfigDict = {}
    
    # Handle --verbose
    if hasattr(args, 'verbose') and args.verbose:
        set_config_value(cli_config, 'general.log_level', 'debug')
    
    # Handle --log-level
    if hasattr(args, 'log_level') and args.log_level:
        set_config_value(cli_config, 'general.log_level', args.log_level)
    
    # Handle --log-dir
    if hasattr(args, 'log_dir') and args.log_dir:
        set_config_value(cli_config, 'general.log_dir', args.log_dir)
    
    # Merge CLI config
    config = merge_configs(config, cli_config)
    
    return config


def get_config_schema() -> Dict[str, Any]:
    """Get the JSON schema for configuration validation.
    
    Returns:
        JSON schema dictionary
    """
    return {
        "type": "object",
        "required": ["general", "audio", "codec", "network", "benchmark"],
        "properties": {
            "general": {
                "type": "object",
                "properties": {
                    "log_level": {"type": "string", "enum": ["debug", "info", "warning", "error", "critical"]},
                    "log_dir": {"type": "string"},
                    "result_dir": {"type": "string"},
                    "temp_dir": {"type": "string"}
                }
            },
            "audio": {
                "type": "object",
                "properties": {
                    "sample_rate": {"type": "integer", "minimum": 8000},
                    "channels": {"type": "integer", "minimum": 1, "maximum": 2},
                    "sample_width": {"type": "integer", "minimum": 1, "maximum": 4},
                    "frame_size": {"type": "integer", "minimum": 1},
                    "input_device": {"type": ["string", "integer", "null"]},
                    "output_device": {"type": ["string", "integer", "null"]}
                }
            },
            "codec": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "bitrate": {"type": "integer", "minimum": 8000},
                    "complexity": {"type": "integer", "minimum": 0, "maximum": 10},
                    "adaptive_bitrate": {"type": "boolean"},
                    "fec": {"type": "boolean"},
                    "dtx": {"type": "boolean"}
                }
            },
            "network": {
                "type": "object",
                "properties": {
                    "local_ip": {"type": "string"},
                    "remote_ip": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1024, "maximum": 65535},
                    "jitter_buffer_size": {"type": "integer", "minimum": 0}
                }
            },
            "benchmark": {
                "type": "object",
                "properties": {
                    "duration": {"type": "number", "minimum": 0},
                    "warm_up": {"type": "number", "minimum": 0},
                    "cool_down": {"type": "number", "minimum": 0},
                    "repeat": {"type": "integer", "minimum": 1},
                    "network_conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "packet_loss": {"type": "number", "minimum": 0, "maximum": 1},
                                "latency": {"type": "number", "minimum": 0},
                                "jitter": {"type": "number", "minimum": 0}
                            }
                        }
                    }
                }
            }
        }
    } 