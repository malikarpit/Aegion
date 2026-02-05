"""
Aegion Cloud Logging - Google Cloud Stackdriver Integration.

Production-grade structured logging with Cloud Logging support.
Falls back to console logging in development.
"""

import logging
import json
import sys
import os
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps

from .time import TimeAuthority
from .config import settings


# Context variables for request tracing
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class CloudLoggingHandler(logging.Handler):
    """
    Google Cloud Logging handler.
    
    Sends structured logs to Stackdriver in production.
    Uses google-cloud-logging library when available.
    """
    
    def __init__(self, project_id: Optional[str] = None):
        super().__init__()
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        self._client = None
        self._cloud_logger = None
        self._initialized = False
    
    def _init_client(self):
        """Lazily initialize Cloud Logging client."""
        if self._initialized:
            return
        
        try:
            from google.cloud import logging as cloud_logging
            self._client = cloud_logging.Client(project=self.project_id)
            self._cloud_logger = self._client.logger('aegion-backend')
            self._initialized = True
        except ImportError:
            # google-cloud-logging not installed
            self._initialized = True
        except Exception as e:
            # Failed to initialize (e.g., no credentials)
            print(f"Cloud Logging init failed: {e}", file=sys.stderr)
            self._initialized = True
    
    def emit(self, record):
        """Emit log record to Cloud Logging."""
        self._init_client()
        
        if self._cloud_logger is None:
            return
        
        try:
            # Build structured payload
            if isinstance(record.msg, dict):
                payload = record.msg
            else:
                payload = {"message": str(record.msg)}
            
            # Add standard fields
            payload.update({
                "severity": record.levelname,
                "logger": record.name,
                "request_id": request_id_var.get(),
                "session_id": session_id_var.get(),
                "user_id": user_id_var.get(),
            })
            
            # Map Python log levels to Cloud Logging severity
            severity_map = {
                'DEBUG': 'DEBUG',
                'INFO': 'INFO',
                'WARNING': 'WARNING',
                'ERROR': 'ERROR',
                'CRITICAL': 'CRITICAL',
            }
            severity = severity_map.get(record.levelname, 'DEFAULT')
            
            # Add OTel Trace Context
            from opentelemetry import trace
            span_context = trace.get_current_span().get_span_context()
            if span_context.is_valid:
                # GCP Trace Format: projects/[PROJECT_ID]/traces/[TRACE_ID]
                trace_id = f"{span_context.trace_id:032x}"
                span_id = f"{span_context.span_id:016x}"
                
                payload["logging.googleapis.com/trace"] = f"projects/{self.project_id}/traces/{trace_id}"
                payload["logging.googleapis.com/spanId"] = span_id
                payload["logging.googleapis.com/trace_sampled"] = span_context.trace_flags.sampled

            self._cloud_logger.log_struct(payload, severity=severity)
            
        except Exception as e:
            # Don't crash on logging errors
            print(f"Cloud Logging error: {e}", file=sys.stderr)


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Outputs Cloud Logging-compatible JSON format.
    """
    
    def format(self, record):
        # Base log entry
        log_entry = {
            "timestamp": TimeAuthority.now(),
            "severity": record.levelname,
            "logger": record.name,
        }
        
        # Add context variables
        if request_id := request_id_var.get():
            log_entry["request_id"] = request_id
        if session_id := session_id_var.get():
            log_entry["session_id"] = session_id
        if user_id := user_id_var.get():
            log_entry["user_id"] = user_id

        # Add OTel Trace Context
        from opentelemetry import trace
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            log_entry["trace_id"] = f"{span_context.trace_id:032x}"
            log_entry["span_id"] = f"{span_context.span_id:016x}"
        
        # Handle message
        if isinstance(record.msg, dict):
            log_entry.update(record.msg)
        else:
            log_entry["message"] = str(record.msg)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class EnhancedAuditLogger:
    """
    Enhanced structured logger with Cloud Logging support.
    
    Features:
    - Automatic context propagation (request_id, session_id, user_id)
    - Cloud Logging integration in production
    - Console JSON output in development
    - Audit trail for compliance
    """
    
    def __init__(self, service_name: str = "aegion-backend"):
        self.service_name = service_name
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')
        
        # Configure logger
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(self._get_log_level())
        self.logger.handlers = []  # Clear existing handlers
        
        # Console handler (always)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredJsonFormatter())
        self.logger.addHandler(console_handler)
        
        # Cloud Logging handler (production only)
        if self.environment in ['production', 'staging']:
            cloud_handler = CloudLoggingHandler()
            self.logger.addHandler(cloud_handler)
    
    def _get_log_level(self) -> int:
        """Get log level from settings."""
        level_str = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _build_entry(self, message: str, **kwargs) -> Dict[str, Any]:
        """Build structured log entry."""
        entry = {
            "timestamp": TimeAuthority.now(),
            "service": self.service_name,
            "environment": self.environment,
            "message": message,
        }
        
        # Add context from context vars
        if request_id := request_id_var.get():
            entry["request_id"] = request_id
        if session_id := session_id_var.get():
            entry["session_id"] = session_id
        if user_id := user_id_var.get():
            entry["user_id"] = user_id
        
        # Add extra fields
        entry.update(kwargs)
        
        return entry
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(self._build_entry(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        self.logger.info(self._build_entry(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(self._build_entry(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        self.logger.error(self._build_entry(message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(self._build_entry(message, **kwargs))
    
    def audit(
        self, 
        action: str, 
        actor: str, 
        target: str, 
        justification: str,
        outcome: str = "success",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Emit audit event for compliance tracking.
        
        Audit events are always INFO level and tagged for easy filtering.
        """
        entry = self._build_entry(
            f"AUDIT: {action} on {target}",
            type="AUDIT_EVENT",
            action=action,
            actor=actor,
            target=target,
            justification=justification,
            outcome=outcome,
        )
        
        if metadata:
            entry["metadata"] = metadata
        
        self.logger.info(entry)
    
    def metric(self, name: str, value: float, unit: str = "", labels: Optional[Dict[str, str]] = None):
        """
        Emit metric event for observability.
        """
        entry = self._build_entry(
            f"METRIC: {name}={value}{unit}",
            type="METRIC",
            metric_name=name,
            metric_value=value,
            metric_unit=unit,
        )
        
        if labels:
            entry["labels"] = labels
        
        self.logger.info(entry)


# Enhanced global logger
cloud_logger = EnhancedAuditLogger()

# Re-export original logger for backwards compatibility
logger = cloud_logger
