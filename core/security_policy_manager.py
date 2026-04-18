#!/usr/bin/env python3
"""
Security Policy Manager - Manages security levels and routing policies

This module provides security policy management for the unified brain router,
allowing fine-grained control over which backend is used based on task type,
sensitivity, and security requirements.
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger('kingdom_ai.security_policy_manager')

class SecurityLevel(Enum):
    """Security levels for AI requests"""
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"

class TaskCategory(Enum):
    """Categories of tasks for security classification"""
    CHAT = "chat"
    CODE_EXECUTION = "code_execution"
    FILE_OPERATIONS = "file_operations"
    NETWORK_REQUESTS = "network_requests"
    SYSTEM_COMMANDS = "system_commands"
    DATA_PROCESSING = "data_processing"
    ANALYSIS = "analysis"
    FINANCIAL = "financial"
    PERSONAL_DATA = "personal_data"
    MEDICAL = "medical"
    LEGAL = "legal"

@dataclass
class SecurityPolicy:
    """Security policy for a task category"""
    category: TaskCategory
    required_level: SecurityLevel
    description: str
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    enabled: bool = True

class SecurityPolicyManager:
    """
    Manages security policies for AI routing decisions
    
    This manager:
    - Defines security policies for different task categories
    - Analyzes prompts to determine appropriate security level
    - Manages policy updates and overrides
    - Provides audit logging for security decisions
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize security policy manager
        
        Args:
            config_path: Path to custom policy configuration file
        """
        self.policies: Dict[TaskCategory, SecurityPolicy] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.config_path = config_path
        
        # Initialize default policies
        self._initialize_default_policies()
        
        # Load custom policies if config path provided
        if config_path:
            self.load_policies_from_file(config_path)
        
        logger.info(f"Security Policy Manager initialized with {len(self.policies)} policies")
    
    def _initialize_default_policies(self):
        """Initialize default security policies"""
        default_policies = [
            SecurityPolicy(
                category=TaskCategory.CHAT,
                required_level=SecurityLevel.STANDARD,
                description="General conversation and chat",
                keywords=["hello", "hi", "how are you", "explain", "tell me"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.CODE_EXECUTION,
                required_level=SecurityLevel.CRITICAL,
                description="Executing code or scripts",
                keywords=["execute", "run", "compile", "exec", "eval"],
                patterns=[r"```.*?```", r"`.*?`"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.FILE_OPERATIONS,
                required_level=SecurityLevel.HIGH,
                description="File system operations",
                keywords=["read", "write", "delete", "create", "modify", "file"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.NETWORK_REQUESTS,
                required_level=SecurityLevel.HIGH,
                description="Network requests and API calls",
                keywords=["download", "upload", "fetch", "request", "api", "http"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.SYSTEM_COMMANDS,
                required_level=SecurityLevel.CRITICAL,
                description="System-level commands",
                keywords=["sudo", "chmod", "chown", "systemctl", "service"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.DATA_PROCESSING,
                required_level=SecurityLevel.STANDARD,
                description="Data analysis and processing",
                keywords=["analyze", "process", "transform", "calculate"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.ANALYSIS,
                required_level=SecurityLevel.STANDARD,
                description="General analysis tasks",
                keywords=["analyze", "examine", "study", "review"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.FINANCIAL,
                required_level=SecurityLevel.HIGH,
                description="Financial transactions and data",
                keywords=["money", "payment", "transaction", "bank", "financial"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.PERSONAL_DATA,
                required_level=SecurityLevel.HIGH,
                description="Personal and sensitive data",
                keywords=["password", "ssn", "personal", "private", "confidential"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.MEDICAL,
                required_level=SecurityLevel.CRITICAL,
                description="Medical and health information",
                keywords=["medical", "health", "diagnosis", "patient", "treatment"],
                enabled=True
            ),
            SecurityPolicy(
                category=TaskCategory.LEGAL,
                required_level=SecurityLevel.HIGH,
                description="Legal documents and advice",
                keywords=["legal", "contract", "law", "lawsuit", "attorney"],
                enabled=True
            ),
        ]
        
        for policy in default_policies:
            self.policies[policy.category] = policy
    
    def analyze_prompt_security(self, prompt: str) -> tuple[SecurityLevel, TaskCategory]:
        """
        Analyze a prompt to determine required security level
        
        Args:
            prompt: User prompt to analyze
            
        Returns:
            Tuple of (SecurityLevel, TaskCategory)
        """
        prompt_lower = prompt.lower()
        
        max_security = SecurityLevel.STANDARD
        detected_category = TaskCategory.CHAT
        
        for category, policy in self.policies.items():
            if not policy.enabled:
                continue
            
            # Check keywords
            for keyword in policy.keywords:
                if keyword.lower() in prompt_lower:
                    if policy.required_level.value > max_security.value:
                        max_security = policy.required_level
                        detected_category = category
            
            # Check patterns (if regex available)
            # This would require import re, keeping simple for now
        
        # Log the decision
        self._log_audit(prompt, max_security, detected_category)
        
        return max_security, detected_category
    
    def _log_audit(self, prompt: str, security_level: SecurityLevel, category: TaskCategory):
        """Log security decision for audit trail"""
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "security_level": security_level.value,
            "category": category.value,
            "policy_used": self.policies[category].description if category in self.policies else "default"
        })
        
        # Keep audit log manageable
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    def get_security_level(self, task_type: str) -> SecurityLevel:
        """
        Get required security level for task type
        
        Args:
            task_type: Task type string
            
        Returns:
            SecurityLevel for the task type
        """
        try:
            category = TaskCategory(task_type)
            if category in self.policies and self.policies[category].enabled:
                return self.policies[category].required_level
        except ValueError:
            # Task type not in enum, use default
            pass
        
        return SecurityLevel.STANDARD
    
    def set_policy(self, category: TaskCategory, level: SecurityLevel, 
                   enabled: bool = True):
        """
        Set security policy for a task category
        
        Args:
            category: Task category
            level: Required security level
            enabled: Whether policy is enabled
        """
        if category in self.policies:
            self.policies[category].required_level = level
            self.policies[category].enabled = enabled
            logger.info(f"Policy updated: {category.value} -> {level.value} (enabled: {enabled})")
        else:
            logger.warning(f"Unknown task category: {category}")
    
    def add_custom_policy(self, policy: SecurityPolicy):
        """
        Add a custom security policy
        
        Args:
            policy: SecurityPolicy to add
        """
        self.policies[policy.category] = policy
        logger.info(f"Custom policy added: {policy.category.value}")
    
    def enable_policy(self, category: TaskCategory):
        """Enable a security policy"""
        if category in self.policies:
            self.policies[category].enabled = True
            logger.info(f"Policy enabled: {category.value}")
    
    def disable_policy(self, category: TaskCategory):
        """Disable a security policy"""
        if category in self.policies:
            self.policies[category].enabled = False
            logger.info(f"Policy disabled: {category.value}")
    
    def get_policies(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all current policies
        
        Returns:
            Dict of policy information
        """
        return {
            category.value: {
                "required_level": policy.required_level.value,
                "description": policy.description,
                "keywords": policy.keywords,
                "enabled": policy.enabled
            }
            for category, policy in self.policies.items()
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit log entries
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        return self.audit_log[-limit:]
    
    def save_policies_to_file(self, file_path: str):
        """
        Save current policies to file
        
        Args:
            file_path: Path to save policies
        """
        policies_data = {
            category.value: {
                "required_level": policy.required_level.value,
                "description": policy.description,
                "keywords": policy.keywords,
                "patterns": policy.patterns,
                "enabled": policy.enabled
            }
            for category, policy in self.policies.items()
        }
        
        with open(file_path, 'w') as f:
            json.dump(policies_data, f, indent=2)
        
        logger.info(f"Policies saved to {file_path}")
    
    def load_policies_from_file(self, file_path: str):
        """
        Load policies from file
        
        Args:
            file_path: Path to load policies from
        """
        try:
            with open(file_path, 'r') as f:
                policies_data = json.load(f)
            
            for category_str, policy_data in policies_data.items():
                try:
                    category = TaskCategory(category_str)
                    self.policies[category] = SecurityPolicy(
                        category=category,
                        required_level=SecurityLevel(policy_data["required_level"]),
                        description=policy_data.get("description", ""),
                        keywords=policy_data.get("keywords", []),
                        patterns=policy_data.get("patterns", []),
                        enabled=policy_data.get("enabled", True)
                    )
                except ValueError:
                    logger.warning(f"Invalid category in config: {category_str}")
            
            logger.info(f"Policies loaded from {file_path}")
            
        except FileNotFoundError:
            logger.warning(f"Policy file not found: {file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid policy file JSON: {e}")
    
    def reset_to_defaults(self):
        """Reset all policies to default values"""
        self._initialize_default_policies()
        logger.info("Policies reset to defaults")
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """
        Get summary of current policy state
        
        Returns:
            Dict with policy summary statistics
        """
        enabled_count = sum(1 for p in self.policies.values() if p.enabled)
        critical_count = sum(1 for p in self.policies.values() 
                           if p.enabled and p.required_level == SecurityLevel.CRITICAL)
        high_count = sum(1 for p in self.policies.values() 
                        if p.enabled and p.required_level == SecurityLevel.HIGH)
        standard_count = sum(1 for p in self.policies.values() 
                            if p.enabled and p.required_level == SecurityLevel.STANDARD)
        
        return {
            "total_policies": len(self.policies),
            "enabled_policies": enabled_count,
            "disabled_policies": len(self.policies) - enabled_count,
            "critical_policies": critical_count,
            "high_policies": high_count,
            "standard_policies": standard_count,
            "audit_log_entries": len(self.audit_log),
            "timestamp": datetime.now().isoformat()
        }
