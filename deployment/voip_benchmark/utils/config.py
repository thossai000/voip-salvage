"""
Configuration Utilities

This module provides utility functions for working with configuration
settings in the VoIP benchmarking framework.
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, Union, List

# Default configuration paths
DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, 'default_config.yaml')


def get_default_config() -> Dict[str, Any]:
    """Get default configuration settings.
    
    Returns:
        Dictionary with default configuration
    """
    # Default VoIP benchmark configuration
    default_config = {
        # Audio settings
        'audio': {
            'sample_rate': 48000,
            'channels': 1,
            'sample_width': 2,
            'voip_sample_rate': 8000,  # Common VoIP sample rate
        },
        
        # Codec settings
        'codec': {
            'name': 'opus',
            'bitrate': 24000,  # 24 kbps, good for voice
            'complexity': 10,  # Maximum quality
            'application': 'voip',  # VOIP, AUDIO, or RESTRICTED_LOWDELAY
            'frame_size': 960,  # 20ms at 48kHz
        },
        
        # RTP settings
        'rtp': {
            'local_address': '0.0.0.0',
            'local_port': 12345,
            'remote_address': '127.0.0.1',
            'remote_port': 12346,
            'payload_type': 111,  # Opus (dynamic payload type)
            'packet_count': 1500,  # ~30s of audio at 20ms frames
            'jitter_buffer_size': 3,  # 3 frames = 60ms
        },
        
        # Network simulation settings
        'network': {
            'enabled': False,
            'packet_loss': 0.0,  # 0% loss by default
            'jitter': 0.0,  # 0ms jitter by default
            'latency': 0.0,  # 0ms added latency
            'duplicate': 0.0,  # 0% duplicated packets
            'bandwidth': 0,  # Unlimited bandwidth (in bps)
        },
        
        # Adaptive bitrate settings
        'adaptive_bitrate': {
            'enabled': False,
            'min_bitrate': 8000,  # 8 kbps
            'max_bitrate': 128000,  # 128 kbps
            'strategy': 'balanced',  # balanced, quality, or aggressive
        },
        
        # Test settings
        'test': {
            'output_dir': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'results'),
            'log_level': 'INFO',
        }
    }
    
    return default_config


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from a file.
    
    Args:
        config_file: Path to configuration file (YAML or JSON)
        
    Returns:
        Dictionary with configuration settings
        
    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If the config file format is invalid
    """
    # Start with default configuration
    config = get_default_config()
    
    # If no config file specified, return defaults
    if not config_file:
        return config
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        # Determine file format from extension
        ext = os.path.splitext(config_file)[1].lower()
        
        if ext in ['.yaml', '.yml']:
            with open(config_file, 'r') as f:
                user_config = yaml.safe_load(f)
        elif ext in ['.json']:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
        else:
            raise ValueError(f"Unsupported configuration file format: {ext}")
        
        # Update config with user settings
        update_config(config, user_config)
        
        return config
    except Exception as e:
        logging.error(f"Error loading configuration from {config_file}: {e}")
        raise ValueError(f"Invalid configuration file: {e}")


def save_config(config: Dict[str, Any], config_file: str) -> bool:
    """Save configuration to a file.
    
    Args:
        config: Configuration dictionary
        config_file: Path to output configuration file
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(config_file)), exist_ok=True)
        
        # Determine file format from extension
        ext = os.path.splitext(config_file)[1].lower()
        
        if ext in ['.yaml', '.yml']:
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
        elif ext in ['.json']:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        else:
            logging.error(f"Unsupported configuration file format: {ext}")
            return False
        
        return True
    except Exception as e:
        logging.error(f"Error saving configuration to {config_file}: {e}")
        return False


def update_config(config: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update configuration with new values.
    
    Args:
        config: Base configuration dictionary
        updates: Updates to apply
        
    Returns:
        Updated configuration dictionary
    """
    for key, value in updates.items():
        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
            update_config(config[key], value)
        else:
            config[key] = value
    
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration settings.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check for required sections
    required_sections = ['audio', 'codec', 'rtp', 'network', 'adaptive_bitrate', 'test']
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")
    
    # Audio section validation
    if 'audio' in config:
        audio = config['audio']
        if not isinstance(audio.get('sample_rate'), int) or audio.get('sample_rate') <= 0:
            errors.append("Audio sample_rate must be a positive integer")
        if not isinstance(audio.get('channels'), int) or audio.get('channels') <= 0:
            errors.append("Audio channels must be a positive integer")
        if not isinstance(audio.get('sample_width'), int) or audio.get('sample_width') <= 0:
            errors.append("Audio sample_width must be a positive integer")
    
    # Codec section validation
    if 'codec' in config:
        codec = config['codec']
        if not isinstance(codec.get('bitrate'), int) or codec.get('bitrate') <= 0:
            errors.append("Codec bitrate must be a positive integer")
    
    # RTP section validation
    if 'rtp' in config:
        rtp = config['rtp']
        if not isinstance(rtp.get('local_port'), int) or not (0 <= rtp.get('local_port') <= 65535):
            errors.append("RTP local_port must be an integer between 0 and 65535")
        if not isinstance(rtp.get('remote_port'), int) or not (0 <= rtp.get('remote_port') <= 65535):
            errors.append("RTP remote_port must be an integer between 0 and 65535")
    
    # Network section validation
    if 'network' in config:
        network = config['network']
        if not isinstance(network.get('packet_loss'), (int, float)) or not (0 <= network.get('packet_loss') <= 1):
            errors.append("Network packet_loss must be a number between 0 and 1")
        if not isinstance(network.get('jitter'), (int, float)) or network.get('jitter') < 0:
            errors.append("Network jitter must be a non-negative number")
    
    return errors


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Get a value from the config using a dot-separated path.
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated path to the value (e.g., 'codec.bitrate')
        default: Default value to return if not found
        
    Returns:
        Value from the config, or default if not found
    """
    keys = key_path.split('.')
    current = config
    
    try:
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    except Exception:
        return default 