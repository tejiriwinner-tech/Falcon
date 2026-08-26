import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SecretManager:
    """Securely manage and access sensitive configuration."""
    
    # List of sensitive keys that should never be logged
    SENSITIVE_KEYS = {
        'API_KEY',
        'SECRET',
        'PASSWORD',
        'TOKEN',
        'DATABASE_URL',
        'DB_PASSWORD',
        'FALCON_API_KEY',
        'TWELVEDATA_API_KEY',
        'FMP_API_KEY',
        'ALPHA_VANTAGE_API_KEY'
    }
    
    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable value securely.
        
        Args:
            key: Environment variable name
            default: Default value if not found
            
        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)
    
    @staticmethod
    def sanitize_dict(data: dict) -> dict:
        """
        Sanitize a dictionary by masking sensitive values.
        
        Args:
            data: Dictionary to sanitize
            
        Returns:
            Dictionary with sensitive values masked
        """
        sanitized = {}
        for key, value in data.items():
            if SecretManager._is_sensitive_key(key):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = SecretManager.sanitize_dict(value)
            elif isinstance(value, str) and SecretManager._contains_sensitive_data(value):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized
    
    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Check if a key name indicates sensitive data."""
        key_upper = key.upper()
        for sensitive in SecretManager.SENSITIVE_KEYS:
            if sensitive in key_upper:
                return True
        return False
    
    @staticmethod
    def _contains_sensitive_data(value: str) -> bool:
        """Check if a string value might contain sensitive data."""
        # Check for common patterns that might indicate sensitive data
        if value.startswith(('http://', 'https://')) and '@' in value:
            # URL with credentials
            return True
        if len(value) > 20 and value.isalnum():
            # Might be a token or key
            return True
        return False
    
    @staticmethod
    def log_safe(message: str, **kwargs) -> None:
        """
        Log a message with safe sanitization of any kwargs.
        
        Args:
            message: Log message
            **kwargs: Additional data to log (will be sanitized)
        """
        sanitized_kwargs = SecretManager.sanitize_dict(kwargs)
        logger.info(message, extra=sanitized_kwargs)