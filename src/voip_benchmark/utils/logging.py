"""
Logging Utilities

This module provides standardized logging configuration for VoIP benchmarking.
"""

import os
import sys
import time
import json
import logging
import logging.handlers
from typing import Dict, List, Any, Optional, Union, Set, Callable
from datetime import datetime


# Default log format
DEFAULT_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Log levels dictionary for easier configuration
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


def setup_logger(
    name: str,
    log_level: Union[str, int] = 'info',
    log_file: Optional[str] = None,
    console: bool = True,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    file_size_limit: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """Set up a logger with file and/or console handlers.
    
    Args:
        name: Logger name
        log_level: Logging level ('debug', 'info', 'warning', 'error', 'critical')
        log_file: Path to log file (if None, file logging is disabled)
        console: Whether to enable console logging
        log_format: Log format string
        date_format: Date format string
        file_size_limit: Maximum log file size in bytes before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    
    # Convert string log level to numeric value if necessary
    if isinstance(log_level, str):
        level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    else:
        level = log_level
    
    # Set logger level
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(log_format, date_format)
    
    # Add file handler if log_file is specified
    if log_file:
        # Make sure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Use rotating file handler to limit log file size
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=file_size_limit,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    # Add console handler if console is True
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    return logger


class BenchmarkLogger:
    """Logger for VoIP benchmark results.
    
    This class provides methods for logging benchmark results in a structured way.
    """
    
    def __init__(
        self,
        log_dir: str,
        benchmark_name: str,
        include_timestamp: bool = True,
        auto_create_dir: bool = True
    ):
        """Initialize the benchmark logger.
        
        Args:
            log_dir: Directory to store logs
            benchmark_name: Name of the benchmark
            include_timestamp: Whether to include timestamp in log file names
            auto_create_dir: Whether to automatically create the log directory
        """
        self.log_dir = log_dir
        self.benchmark_name = benchmark_name
        self.include_timestamp = include_timestamp
        
        # Create log directory if it doesn't exist
        if auto_create_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Initialize logger
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.logger = setup_logger(
            f'benchmark.{benchmark_name}',
            log_level='info',
            log_file=self._get_log_file_path('log'),
            console=True
        )
        
        # Initialize data storage
        self.results = []
        self.configuration = {}
        self.metadata = {
            'benchmark_name': benchmark_name,
            'start_time': time.time(),
            'end_time': None,
            'duration': None
        }
        
        # Log start
        self.logger.info(f"Starting benchmark: {benchmark_name}")
    
    def _get_log_file_path(self, extension: str) -> str:
        """Get the full path for a log file.
        
        Args:
            extension: File extension (without dot)
            
        Returns:
            Full path to the log file
        """
        if self.include_timestamp:
            filename = f"{self.benchmark_name}_{self.timestamp}.{extension}"
        else:
            filename = f"{self.benchmark_name}.{extension}"
        
        return os.path.join(self.log_dir, filename)
    
    def set_configuration(self, config: Dict[str, Any]) -> None:
        """Set benchmark configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.configuration = config
        self.logger.info(f"Configuration: {json.dumps(config, indent=2)}")
    
    def log_result(self, result: Dict[str, Any]) -> None:
        """Log a benchmark result.
        
        Args:
            result: Result dictionary
        """
        # Add timestamp if not present
        if 'timestamp' not in result:
            result['timestamp'] = time.time()
        
        # Append to results
        self.results.append(result)
        
        # Log to logger
        level = result.get('level', 'info')
        message = result.get('message', '')
        
        if level == 'debug':
            self.logger.debug(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'critical':
            self.logger.critical(message)
        else:
            self.logger.info(message)
    
    def log_metric(
        self,
        name: str,
        value: Union[float, int, str],
        category: str = 'metrics',
        description: Optional[str] = None
    ) -> None:
        """Log a benchmark metric.
        
        Args:
            name: Metric name
            value: Metric value
            category: Metric category
            description: Optional description
        """
        result = {
            'type': 'metric',
            'name': name,
            'value': value,
            'category': category,
            'timestamp': time.time()
        }
        
        if description:
            result['description'] = description
        
        self.log_result(result)
        self.logger.info(f"Metric {name}: {value}")
    
    def log_error(self, error: Union[str, Exception], context: Optional[Dict[str, Any]] = None) -> None:
        """Log an error.
        
        Args:
            error: Error message or exception
            context: Optional context information
        """
        if isinstance(error, Exception):
            error_message = str(error)
            error_type = error.__class__.__name__
        else:
            error_message = error
            error_type = 'Error'
        
        result = {
            'type': 'error',
            'error_type': error_type,
            'message': error_message,
            'timestamp': time.time(),
            'level': 'error'
        }
        
        if context:
            result['context'] = context
        
        self.log_result(result)
        self.logger.error(f"{error_type}: {error_message}")
    
    def log_event(
        self,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = 'info'
    ) -> None:
        """Log an event.
        
        Args:
            event_type: Event type
            message: Event message
            data: Optional event data
            level: Log level
        """
        result = {
            'type': 'event',
            'event_type': event_type,
            'message': message,
            'timestamp': time.time(),
            'level': level
        }
        
        if data:
            result['data'] = data
        
        self.log_result(result)
        
        if level == 'debug':
            self.logger.debug(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'critical':
            self.logger.critical(message)
        else:
            self.logger.info(message)
    
    def finish(self) -> Dict[str, Any]:
        """Finish the benchmark and save results.
        
        Returns:
            Dictionary containing benchmark summary
        """
        # Update metadata
        self.metadata['end_time'] = time.time()
        self.metadata['duration'] = self.metadata['end_time'] - self.metadata['start_time']
        
        # Create summary
        summary = {
            'metadata': self.metadata,
            'configuration': self.configuration,
            'results': self.results
        }
        
        # Save results to JSON file
        results_file = self._get_log_file_path('json')
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Log finish
        self.logger.info(f"Benchmark completed in {self.metadata['duration']:.2f} seconds")
        self.logger.info(f"Results saved to {results_file}")
        
        return summary


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(
        self,
        include_timestamp: bool = True,
        include_logger_name: bool = True,
        include_level: bool = True,
        include_path: bool = False,
        include_function: bool = False,
        include_line: bool = False,
        additional_fields: Optional[Dict[str, Any]] = None
    ):
        """Initialize the JSON formatter.
        
        Args:
            include_timestamp: Whether to include timestamp in JSON log
            include_logger_name: Whether to include logger name in JSON log
            include_level: Whether to include log level in JSON log
            include_path: Whether to include file path in JSON log
            include_function: Whether to include function name in JSON log
            include_line: Whether to include line number in JSON log
            additional_fields: Additional fields to include in JSON log
        """
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_logger_name = include_logger_name
        self.include_level = include_level
        self.include_path = include_path
        self.include_function = include_function
        self.include_line = include_line
        self.additional_fields = additional_fields or {}
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.
        
        Args:
            record: Log record
            
        Returns:
            JSON formatted log entry
        """
        log_data = {}
        
        # Add message
        log_data['message'] = record.getMessage()
        
        # Add timestamp
        if self.include_timestamp:
            log_data['timestamp'] = int(record.created * 1000)  # milliseconds
            log_data['time'] = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Add log level
        if self.include_level:
            log_data['level'] = record.levelname
            log_data['level_no'] = record.levelno
        
        # Add logger name
        if self.include_logger_name:
            log_data['logger'] = record.name
        
        # Add source location
        if self.include_path:
            log_data['path'] = record.pathname
        
        if self.include_function:
            log_data['function'] = record.funcName
        
        if self.include_line:
            log_data['line'] = record.lineno
        
        # Add additional fields
        for key, value in self.additional_fields.items():
            log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        # Return JSON string
        return json.dumps(log_data)


def setup_json_logger(
    name: str,
    log_level: Union[str, int] = 'info',
    log_file: Optional[str] = None,
    console: bool = True,
    additional_fields: Optional[Dict[str, Any]] = None,
    include_path: bool = False,
    include_function: bool = False,
    include_line: bool = False,
    file_size_limit: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """Set up a logger with JSON formatting.
    
    Args:
        name: Logger name
        log_level: Logging level ('debug', 'info', 'warning', 'error', 'critical')
        log_file: Path to log file (if None, file logging is disabled)
        console: Whether to enable console logging
        additional_fields: Additional fields to include in JSON log
        include_path: Whether to include file path in JSON log
        include_function: Whether to include function name in JSON log
        include_line: Whether to include line number in JSON log
        file_size_limit: Maximum log file size in bytes before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    
    # Convert string log level to numeric value if necessary
    if isinstance(log_level, str):
        level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    else:
        level = log_level
    
    # Set logger level
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = JsonFormatter(
        include_path=include_path,
        include_function=include_function,
        include_line=include_line,
        additional_fields=additional_fields
    )
    
    # Add file handler if log_file is specified
    if log_file:
        # Make sure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Use rotating file handler to limit log file size
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=file_size_limit,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    # Add console handler if console is True
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    return logger


def get_default_logger() -> logging.Logger:
    """Get the default logger.
    
    Returns:
        Default logger instance
    """
    return setup_logger('voip_benchmark', log_level='info', console=True)


# Default logger instance for convenience
default_logger = get_default_logger() 