import pytest
from fastapi import HTTPException
from app.core.validation.input_validator import InputValidator


class TestInputValidator:
    """Test suite for InputValidator class."""
    
    def test_validate_symbol_valid(self):
        """Test validation of valid symbols."""
        assert InputValidator.validate_symbol("XAUUSD") == "XAUUSD"
        assert InputValidator.validate_symbol("GBPUSD") == "GBPUSD"
        assert InputValidator.validate_symbol("EUR") == "EUR"
        assert InputValidator.validate_symbol("xauusd") == "XAUUSD"  # Should uppercase
    
    def test_validate_symbol_invalid(self):
        """Test validation of invalid symbols."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_symbol("")
        assert "required" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_symbol("TOOLONG")
        assert "Invalid symbol format" in str(exc_info.value.detail)
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_symbol("123")
        assert "Invalid symbol format" in str(exc_info.value.detail)
    
    def test_validate_string_valid(self):
        """Test validation of valid strings."""
        result = InputValidator.validate_string("test", "field_name")
        assert result == "test"
        
        result = InputValidator.validate_string("  test  ", "field_name")
        assert result == "test"  # Should strip whitespace
    
    def test_validate_string_invalid(self):
        """Test validation of invalid strings."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string(None, "field_name")
        assert "required" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("", "field_name", allow_empty=False)
        assert "cannot be empty" in str(exc_info.value.detail).lower()
    
    def test_validate_string_sql_injection(self):
        """Test SQL injection detection."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("test' OR '1'='1", "field_name")
        assert "invalid characters" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("test; DROP TABLE users", "field_name")
        assert "invalid characters" in str(exc_info.value.detail).lower()
    
    def test_validate_string_xss(self):
        """Test XSS detection."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("<script>alert('xss')</script>", "field_name")
        # XSS detection is caught by invalid characters check (contains < and >)
        assert "invalid" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("javascript:alert('xss')", "field_name")
        # javascript: is caught by invalid characters (contains :)
        assert "invalid" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_string("<img onload=alert('xss')>", "field_name")
        assert "invalid" in str(exc_info.value.detail).lower()
    
    def test_validate_integer_valid(self):
        """Test validation of valid integers."""
        assert InputValidator.validate_integer(42, "field_name") == 42
        assert InputValidator.validate_integer("42", "field_name") == 42
    
    def test_validate_integer_invalid(self):
        """Test validation of invalid integers."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_integer(None, "field_name")
        assert "required" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_integer("not_a_number", "field_name")
        assert "must be an integer" in str(exc_info.value.detail).lower()
    
    def test_validate_integer_bounds(self):
        """Test integer bounds validation."""
        assert InputValidator.validate_integer(5, "field_name", min_value=0, max_value=10) == 5
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_integer(-1, "field_name", min_value=0)
        assert "at least" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_integer(11, "field_name", max_value=10)
        assert "at most" in str(exc_info.value.detail).lower()
    
    def test_validate_float_valid(self):
        """Test validation of valid floats."""
        assert InputValidator.validate_float(3.14, "field_name") == 3.14
        assert InputValidator.validate_float("3.14", "field_name") == 3.14
    
    def test_validate_float_invalid(self):
        """Test validation of invalid floats."""
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_float(None, "field_name")
        assert "required" in str(exc_info.value.detail).lower()
        
        with pytest.raises(HTTPException) as exc_info:
            InputValidator.validate_float("not_a_number", "field_name")
        assert "must be a number" in str(exc_info.value.detail).lower()
    
    def test_sanitize_html(self):
        """Test HTML sanitization."""
        assert InputValidator.sanitize_html("<p>test</p>") == "test"
        assert InputValidator.sanitize_html("<script>alert('xss')</script>test") == "test"
        assert InputValidator.sanitize_html("normal text") == "normal text"