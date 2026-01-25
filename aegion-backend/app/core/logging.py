"""
Aegion Structured Logging (Audit-First).

Doctrine: "Audit is not a side effect; it is a first-class citizen."
Every log entry must be structured JSON and contain provenance metadata 
(session_id, actor, intent).
"""

import logging
import json
import sys
from typing import Any, Dict, Optional
from .time import TimeAuthority

class AuditLogger:
    """
    Structured logger that enforces the AuditEvent schema in logs.
    """
    
    def __init__(self, service_name: str = "aegion-backend"):
        self.service_name = service_name
        
        # Configure standard python logger
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
        
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def audit(self, action: str, actor: str, target: str, justification: str, 
              session_id: Optional[str] = None, metadata: Dict[str, Any] = None):
        """
        Explicit Audit Event.
        Builds an AuditEvent, seals it through AuditChain for tamper-resistance,
        then emits the sealed payload.
        """
        import uuid
        from ..contracts.audit_event import (
            AuditEvent, AuditAction, AuditCategory, AuditSeverity
        )
        from ..services.archon.audit_chain import get_audit_chain

        # Try to map the action string to the enum, fallback to SYSTEM
        try:
            action_enum = AuditAction(action)
        except ValueError:
            action_enum = AuditAction.CONFIG_CHANGED  # safe fallback

        # Infer category from action prefix
        prefix = action_enum.value.split('.')[0]
        category_map = {
            'session': AuditCategory.SESSION,
            'decision': AuditCategory.DECISION,
            'governance': AuditCategory.GOVERNANCE,
            'ai': AuditCategory.AI,
            'security': AuditCategory.SECURITY,
            'system': AuditCategory.SYSTEM,
        }
        category = category_map.get(prefix, AuditCategory.SYSTEM)

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            category=category,
            action=action_enum,
            severity=AuditSeverity.INFO,
            actor_id=actor,
            target_type=target.split("/")[0] if "/" in target else "resource",
            target_id=target,
            session_id=session_id,
            justification=justification,
            metadata=metadata or {},
        )

        # Seal into hash chain
        sealed = get_audit_chain().append(event)

        payload = {
            "type": "AUDIT_EVENT",
            "event_id": sealed.event_id,
            "action": sealed.action.value,
            "actor": sealed.actor_id,
            "target": sealed.target_id,
            "justification": sealed.justification,
            "session_id": sealed.session_id,
            "event_hash": sealed.event_hash,
            "signature": sealed.signature,
            "prev_hash": sealed.prev_hash,
        }
        if metadata:
            payload["metadata"] = metadata
            
        self._log(logging.INFO, f"AUDIT: {action} on {target}", **payload)

    def _log(self, level: int, message: str, **kwargs):
        """Internal structured log emitter."""
        # Enforce UTC timestamp from TimeAuthority
        timestamp = TimeAuthority.now()
        
        entry = {
            "timestamp": timestamp,
            "service": self.service_name,
            "message": message,
            **kwargs
        }
        
        self.logger.log(level, entry) # Formatter will handle JSON conversion

class JsonFormatter(logging.Formatter):
    """Custom formatter to output JSON strings."""
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg)
        # Verify if msg was passed as dict or regular string
        # In our _log method we pass the dict as the message effectively if we bypassed standard logging
        # But here _log calls logger.log(level, entry) where entry is a dict. 
        # So record.msg IS the dict.
        return json.dumps(record.msg)

# Global Logger Instance
logger = AuditLogger()
