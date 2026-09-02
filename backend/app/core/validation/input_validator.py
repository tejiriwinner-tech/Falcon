import re
from typing import Optional, Any
from fastapi import HTTPException, status

class InputValidator:
    """Input validation and sanitization utilities."""
    
    # Common patterns
    SYMBOL_PATTERN = re.compile(r'^[A-Z]{1,6}$')  # Updated to allow 6 characters for XAUUSD
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,@:()]+$', re.UNICODE)
    SQL_INJECTION_PATTERN = re.compile(r'(\b(union|select|insert|update|delete|drop|alter|create|exec|execute)\b|\'|;|--|\/\*|\*\/)', re.IGNORECASE)
    XSS_PATTERN = re.compile(r'<script[^>]*>.*?</script>|javascript:|on\w+\s*=', re.IGNORECASE)
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate and sanitize stock symbol."""
        if not symbol or not isinstance(symbol, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symbol is required and must be a string"
            )
        
        symbol = symbol.strip().upper()
        
        if not InputValidator.SYMBOL_PATTERN.match(symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid symbol format: {symbol}. Must be 1-5 uppercase letters"
            )
        
        return symbol
    
    @staticmethod
    def validate_string(
        value: Optional[str],
        field_name: str,
        max_length: int = 1000,
        allow_empty: bool = False
    ) -> str:
        """Validate and sanitize string input."""
        if value is None:
            if allow_empty:
                return ""
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required"
            )
        
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a string"
            )
        
        value = value.strip()
        
        if not value and not allow_empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} cannot be empty"
            )
        
        if len(value) > max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} exceeds maximum length of {max_length}"
            )
        
        # Check for SQL injection patterns
        if InputValidator.SQL_INJECTION_PATTERN.search(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} contains invalid characters"
            )
        
        # Check for XSS patterns
        if InputValidator.XSS_PATTERN.search(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} contains potentially dangerous content"
            )
        
        return value
    
    @staticmethod
    def validate_integer(
        value: Optional[Any],
        field_name: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> int:
        """Validate integer input."""
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required"
            )
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be an integer"
            )
        
        if min_value is not None and int_value < min_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be at least {min_value}"
            )
        
        if max_value is not None and int_value > max_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be at most {max_value}"
            )
        
        return int_value
    
    @staticmethod
    def validate_float(
        value: Optional[Any],
        field_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> float:
        """Validate float input."""
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required"
            )
        
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a number"
            )
        
        if min_value is not None and float_value < min_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be at least {min_value}"
            )
        
        if max_value is not None and float_value > max_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be at most {max_value}"
            )
        
        return float_value
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Basic HTML sanitization - remove HTML tags."""
        # Remove script tags and their content
        text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        # Remove other HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text