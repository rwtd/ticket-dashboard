#!/usr/bin/env python3
"""
Security Validator for Ticket Dashboard
Provides comprehensive input validation, sanitization, and security checks
"""

import re
import html
import bleach
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from urllib.parse import urlparse
import hashlib
import secrets

from pydantic import BaseModel, validator, ValidationError
from pydantic.types import constr

logger = logging.getLogger(__name__)


# Security Configuration
SECURITY_CONFIG = {
    'max_string_length': 1000,
    'max_array_length': 100,
    'allowed_html_tags': ['b', 'i', 'u', 'em', 'strong', 'p', 'br'],
    'allowed_schemes': ['http', 'https'],
    'sql_injection_patterns': [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|script)\b)",
        r"(\b(or|and)\b.*=.*)",
        r"(--|#|/\*|\*/)",
        r"(\bunion\b.*\bselect\b)",
        r"(\bxp_cmdshell\b|\bsp_executesql\b)",
    ],
    'xss_patterns': [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
    ]
}


class WidgetParams(BaseModel):
    """Validated widget parameters"""
    source: constr(strip_whitespace=True, min_length=1, max_length=50)
    range: Optional[constr(strip_whitespace=True, max_length=10)] = "12w"
    stat: Optional[constr(strip_whitespace=True, max_length=10)] = "median"
    agents: Optional[List[constr(max_length=100)]] = None
    pipelines: Optional[List[constr(max_length=100)]] = None
    include_weekends: Optional[bool] = True
    show_trend: Optional[bool] = True
    
    @validator('source')
    def validate_source(cls, v):
        allowed_sources = ['tickets', 'chats']
        if v not in allowed_sources:
            raise ValueError(f"Source must be one of {allowed_sources}")
        return v
    
    @validator('range')
    def validate_range(cls, v):
        if v is None:
            return v
        allowed_ranges = ['all', '52w', '26w', '12w', '8w', '4w']
        if v not in allowed_ranges:
            raise ValueError(f"Range must be one of {allowed_ranges}")
        return v
    
    @validator('stat')
    def validate_stat(cls, v):
        if v is None:
            return v
        allowed_stats = ['median', 'mean', 'both']
        if v not in allowed_stats:
            raise ValueError(f"Stat must be one of {allowed_stats}")
        return v
    
    @validator('agents', 'pipelines')
    def validate_lists(cls, v):
        if v is not None and len(v) > 100:
            raise ValueError("Maximum 100 items allowed in list")
        return v


class QueryParams(BaseModel):
    """Validated query parameters"""
    question: constr(strip_whitespace=True, min_length=1, max_length=1000)
    api_key: Optional[constr(max_length=200)] = None
    conversation_id: Optional[constr(max_length=100)] = None
    ticket_files: Optional[List[constr(max_length=200)]] = None
    chat_files: Optional[List[constr(max_length=200)]] = None
    
    @validator('question')
    def validate_question(cls, v):
        # Check for SQL injection patterns
        for pattern in SECURITY_CONFIG['sql_injection_patterns']:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Question contains potentially unsafe patterns")
        
        # Check for XSS patterns
        for pattern in SECURITY_CONFIG['xss_patterns']:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Question contains potentially unsafe patterns")
        
        return v


class SecurityValidator:
    """Comprehensive security validation and sanitization"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or SECURITY_CONFIG
    
    def sanitize_string(self, value: str, max_length: int = None) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return str(value)
        
        # Limit length
        max_length = max_length or self.config['max_string_length']
        if len(value) > max_length:
            value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Escape HTML
        value = html.escape(value)
        
        return value.strip()
    
    def sanitize_html(self, value: str) -> str:
        """Sanitize HTML content"""
        if not value:
            return value
        
        # Use bleach for HTML sanitization
        return bleach.clean(
            value,
            tags=self.config['allowed_html_tags'],
            strip=True
        )
    
    def validate_sql_query(self, query: str) -> bool:
        """Validate SQL query for safety"""
        if not query or not isinstance(query, str):
            return False
        
        # Check for dangerous SQL patterns
        for pattern in self.config['sql_injection_patterns']:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return False
        
        # Check for multiple statements (prevent injection)
        if query.count(';') > 1:
            logger.warning("Multiple SQL statements detected")
            return False
        
        return True
    
    def validate_file_path(self, file_path: str, allowed_extensions: List[str] = None) -> bool:
        """Validate file path for safety"""
        if not file_path or not isinstance(file_path, str):
            return False
        
        # Sanitize path
        file_path = os.path.normpath(file_path)
        
        # Check for path traversal
        if '..' in file_path or file_path.startswith('/'):
            return False
        
        # Check extension if provided
        if allowed_extensions:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in allowed_extensions:
                return False
        
        return True
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename"""
        if not filename:
            return "unnamed"
        
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:\"/\\|?*]', '_', filename)
        
        # Limit length
        max_length = 255
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length-len(ext)] + ext
        
        return filename.strip()
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key format"""
        if not api_key or not isinstance(api_key, str):
            return False
        
        # Check minimum length
        if len(api_key) < 10:
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'script',
            r'javascript',
            r'vbscript',
            r'onload',
            r'onclick',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, api_key, re.IGNORECASE):
                return False
        
        return True
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def hash_sensitive_data(self, data: str, salt: str = None) -> str:
        """Hash sensitive data"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{data}:{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def validate_date_range(self, start_date: Any, end_date: Any) -> bool:
        """Validate date range"""
        try:
            if start_date and end_date:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date)
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date)
                
                return start_date <= end_date
            
            return True
            
        except (ValueError, TypeError):
            return False
    
    def sanitize_dict(self, data: Dict[str, Any], max_depth: int = 5) -> Dict[str, Any]:
        """Recursively sanitize dictionary"""
        if max_depth <= 0:
            return {}
        
        sanitized = {}
        
        for key, value in data.items():
            # Sanitize key
            clean_key = self.sanitize_string(str(key), max_length=100)
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[clean_key] = self.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[clean_key] = self.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                sanitized[clean_key] = self.sanitize_list(value, max_depth - 1)
            elif isinstance(value, (int, float, bool)) or value is None:
                sanitized[clean_key] = value
            else:
                sanitized[clean_key] = self.sanitize_string(str(value))
        
        return sanitized
    
    def sanitize_list(self, data: List[Any], max_depth: int = 5) -> List[Any]:
        """Recursively sanitize list"""
        if max_depth <= 0:
            return []
        
        sanitized = []
        
        for value in data:
            if isinstance(value, str):
                sanitized.append(self.sanitize_string(value))
            elif isinstance(value, dict):
                sanitized.append(self.sanitize_dict(value, max_depth - 1))
            elif isinstance(value, list):
                sanitized.append(self.sanitize_list(value, max_depth - 1))
            elif isinstance(value, (int, float, bool)) or value is None:
                sanitized.append(value)
            else:
                sanitized.append(self.sanitize_string(str(value)))
        
        return sanitized


# Widget-specific validation functions
def validate_widget_params(params: Dict[str, Any]) -> WidgetParams:
    """Validate and sanitize widget parameters"""
    validator = SecurityValidator()
    
    # Sanitize input
    sanitized_params = validator.sanitize_dict(params)
    
    # Validate with Pydantic
    try:
        validated_params = WidgetParams(**sanitized_params)
        return validated_params
    except ValidationError as e:
        logger.error(f"Widget parameter validation failed: {e}")
        raise


def validate_query_params(params: Dict[str, Any]) -> QueryParams:
    """Validate and sanitize query parameters"""
    validator = SecurityValidator()
    
    # Sanitize input
    sanitized_params = validator.sanitize_dict(params)
    
    # Validate with Pydantic
    try:
        validated_params = QueryParams(**sanitized_params)
        return validated_params
    except ValidationError as e:
        logger.error(f"Query parameter validation failed: {e}")
        raise


# SQL injection protection
class SQLInjectionProtector:
    """Protect against SQL injection attacks"""
    
    def __init__(self):
        self.dangerous_keywords = [
            'union', 'select', 'insert', 'update', 'delete', 'drop',
            'create', 'alter', 'exec', 'execute', 'script', 'declare',
            'truncate', 'backup', 'restore', 'load', 'grant', 'revoke'
        ]
        
        self.dangerous_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(from|where|and|or)\b)",
            r"(--|#|/\*|\*/)",
            r"(\bxp_cmdshell\b|\bsp_executesql\b|\bsp_help\b)",
            r"(\bmaster\b\.\.\bdbo\b)",
            r"(\binformation_schema\b|\bsysobjects\b|\bsyscolumns\b)",
        ]
    
    def validate_column_name(self, column_name: str) -> bool:
        """Validate column name is safe"""
        if not column_name or not isinstance(column_name, str):
            return False
        
        # Only allow alphanumeric, underscores, and spaces
        if not re.match(r'^[a-zA-Z0-9_\s]+$', column_name):
            return False
        
        # Check length
        if len(column_name) > 100:
            return False
        
        return True
    
    def validate_table_name(self, table_name: str) -> bool:
        """Validate table name is safe"""
        if not table_name or not isinstance(table_name, str):
            return False
        
        # Only allow alphanumeric and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
            return False
        
        # Check against dangerous keywords
        table_lower = table_name.lower()
        for keyword in self.dangerous_keywords:
            if keyword in table_lower:
                return False
        
        return True
    
    def sanitize_column_name(self, column_name: str) -> str:
        """Sanitize column name"""
        if not self.validate_column_name(column_name):
            return "invalid_column"
        
        # Remove any potentially dangerous characters
        sanitized = re.sub(r'[^\w\s]', '', column_name)
        return sanitized[:100]
    
    def validate_sql_value(self, value: Any) -> bool:
        """Validate SQL value is safe"""
        if value is None:
            return True
        
        if isinstance(value, (int, float)):
            return True
        
        if isinstance(value, str):
            # Check for dangerous patterns
            value_lower = value.lower()
            for pattern in self.dangerous_patterns:
                if re.search(pattern, value_lower):
                    return False
            
            # Check for SQL keywords
            for keyword in self.dangerous_keywords:
                if keyword in value_lower:
                    return False
            
            return True
        
        if isinstance(value, datetime):
            return True
        
        return False


# Rate limiting
class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed"""
        with self._lock:
            now = datetime.now()
            
            # Clean up old entries
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.requests = {
                k: v for k, v in self.requests.items()
                if v[-1] > cutoff
            }
            
            # Check current requests
            if identifier in self.requests:
                # Remove old requests outside window
                self.requests[identifier] = [
                    req_time for req_time in self.requests[identifier]
                    if req_time > cutoff
                ]
                
                # Check if under limit
                if len(self.requests[identifier]) < self.max_requests:
                    self.requests[identifier].append(now)
                    return True
                else:
                    return False
            else:
                # First request
                self.requests[identifier] = [now]
                return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for identifier"""
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            if identifier in self.requests:
                # Count recent requests
                recent_requests = [
                    req_time for req_time in self.requests[identifier]
                    if req_time > cutoff
                ]
                return max(0, self.max_requests - len(recent_requests))
            else:
                return self.max_requests


# Global instances
_security_validator = SecurityValidator()
_sql_protector = SQLInjectionProtector()


def get_security_validator() -> SecurityValidator:
    """Get global security validator instance"""
    return _security_validator


def get_sql_protector() -> SQLInjectionProtector:
    """Get global SQL injection protector instance"""
    return _sql_protector


if __name__ == "__main__":
    # Test security validator
    logging.basicConfig(level=logging.INFO)
    
    validator = SecurityValidator()
    
    # Test string sanitization
    test_string = "<script>alert('xss')</script>Hello World!"
    sanitized = validator.sanitize_string(test_string)
    print(f"Original: {test_string}")
    print(f"Sanitized: {sanitized}")
    
    # Test SQL injection detection
    dangerous_sql = "SELECT * FROM users WHERE id = 1 OR 1=1"
    is_safe = validator.validate_sql_query(dangerous_sql)
    print(f"SQL safe: {is_safe}")
    
    # Test widget parameter validation
    widget_params = {
        'source': 'tickets',
        'range': '12w',
        'agents': ['Nova', 'Girly'],
        'include_weekends': True
    }
    
    try:
        validated = validate_widget_params(widget_params)
        print(f"Validated widget params: {validated}")
    except ValidationError as e:
        print(f"Validation error: {e}")
    
    print("✅ Security validator tested successfully!")