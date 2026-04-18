"""
Error Resolver Component for Kingdom AI.

Categorises errors by type, suggests fixes based on common patterns,
and can auto-resolve simple issues (missing imports, connection retries).
"""

import logging
import re
import traceback
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("KingdomAI.ErrorResolver")

_IMPORT_PATTERN = re.compile(
    r"(?:ModuleNotFoundError|ImportError): (?:No module named |cannot import name )['\"]?(\S+)['\"]?"
)
_SYNTAX_PATTERN = re.compile(r"SyntaxError:")
_CONNECTION_PATTERN = re.compile(
    r"(?:ConnectionError|ConnectionRefusedError|TimeoutError|"
    r"ConnectionResetError|BrokenPipeError|OSError.*Connection refused)"
)
_ATTRIBUTE_PATTERN = re.compile(r"AttributeError: .+ has no attribute ['\"](\w+)['\"]")
_TYPE_PATTERN = re.compile(r"TypeError:")
_KEY_PATTERN = re.compile(r"KeyError: ['\"](\w+)['\"]")
_FILE_NOT_FOUND_PATTERN = re.compile(r"FileNotFoundError:")
_PERMISSION_PATTERN = re.compile(r"PermissionError:")
_VALUE_PATTERN = re.compile(r"ValueError:")


class ErrorCategory:
    IMPORT = "import"
    SYNTAX = "syntax"
    CONNECTION = "connection"
    RUNTIME = "runtime"
    ATTRIBUTE = "attribute"
    TYPE = "type"
    KEY = "key"
    FILE = "file"
    PERMISSION = "permission"
    VALUE = "value"
    UNKNOWN = "unknown"


class ErrorResolver:
    """Categorises, suggests fixes for, and optionally auto-resolves errors."""

    MAX_AUTO_RETRIES = 3

    def __init__(self):
        self.error_count = 0
        self.resolved_count = 0
        self.error_history: List[Dict[str, Any]] = []
        self._retry_tracker: Dict[str, int] = {}

    def categorize(self, exception: BaseException) -> str:
        """Return the ErrorCategory string for *exception*."""
        msg = str(exception)
        exc_type = type(exception).__name__
        combined = f"{exc_type}: {msg}"

        if _IMPORT_PATTERN.search(combined):
            return ErrorCategory.IMPORT
        if _SYNTAX_PATTERN.search(combined):
            return ErrorCategory.SYNTAX
        if _CONNECTION_PATTERN.search(combined):
            return ErrorCategory.CONNECTION
        if _ATTRIBUTE_PATTERN.search(combined):
            return ErrorCategory.ATTRIBUTE
        if _TYPE_PATTERN.search(combined):
            return ErrorCategory.TYPE
        if _KEY_PATTERN.search(combined):
            return ErrorCategory.KEY
        if _FILE_NOT_FOUND_PATTERN.search(combined):
            return ErrorCategory.FILE
        if _PERMISSION_PATTERN.search(combined):
            return ErrorCategory.PERMISSION
        if _VALUE_PATTERN.search(combined):
            return ErrorCategory.VALUE
        return ErrorCategory.RUNTIME

    def suggest_fixes(self, exception: BaseException) -> List[str]:
        """Return a list of human-readable fix suggestions."""
        category = self.categorize(exception)
        msg = str(exception)
        suggestions: List[str] = []

        if category == ErrorCategory.IMPORT:
            m = _IMPORT_PATTERN.search(f"{type(exception).__name__}: {msg}")
            module = m.group(1) if m else "unknown"
            suggestions.append(f"Install the missing module: pip install {module}")
            suggestions.append(f"Check spelling of import: {module}")
            suggestions.append("Verify virtual environment is activated")

        elif category == ErrorCategory.SYNTAX:
            suggestions.append("Check for mismatched parentheses/brackets")
            suggestions.append("Verify indentation is consistent (spaces vs tabs)")
            suggestions.append("Look for missing colons after if/for/def/class")

        elif category == ErrorCategory.CONNECTION:
            suggestions.append("Verify the remote service is running")
            suggestions.append("Check firewall rules and network connectivity")
            suggestions.append("Retry with exponential backoff")
            suggestions.append("Confirm host/port settings in config")

        elif category == ErrorCategory.ATTRIBUTE:
            m = _ATTRIBUTE_PATTERN.search(f"{type(exception).__name__}: {msg}")
            attr = m.group(1) if m else "?"
            suggestions.append(f"Verify attribute '{attr}' exists on the object")
            suggestions.append("Check for typos in the attribute name")
            suggestions.append("Object may not be initialised yet; check init order")

        elif category == ErrorCategory.KEY:
            m = _KEY_PATTERN.search(f"{type(exception).__name__}: {msg}")
            key = m.group(1) if m else "?"
            suggestions.append(f"Use .get('{key}', default) instead of direct access")
            suggestions.append("Check that the data source includes the expected keys")

        elif category == ErrorCategory.FILE:
            suggestions.append("Verify the file path is correct")
            suggestions.append("Ensure the directory exists (os.makedirs)")
            suggestions.append("Check for platform-specific path separators")

        elif category == ErrorCategory.PERMISSION:
            suggestions.append("Run with appropriate permissions / elevated privileges")
            suggestions.append("Check file ownership and chmod/acl settings")

        elif category == ErrorCategory.TYPE:
            suggestions.append("Verify argument types match the function signature")
            suggestions.append("Add type checks or casts before the call")

        elif category == ErrorCategory.VALUE:
            suggestions.append("Validate input ranges before processing")
            suggestions.append("Add try/except with informative messages")

        else:
            suggestions.append("Inspect the full traceback for root cause")
            suggestions.append("Add logging around the failing code path")

        return suggestions

    def resolve_exception(self, exception: BaseException) -> bool:
        """Try to auto-resolve *exception*. Returns True if resolved."""
        self.error_count += 1
        category = self.categorize(exception)
        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)

        entry: Dict[str, Any] = {
            "category": category,
            "message": str(exception),
            "type": type(exception).__name__,
            "traceback": "".join(tb[-3:]),
            "suggestions": self.suggest_fixes(exception),
            "auto_resolved": False,
        }

        resolved = False

        if category == ErrorCategory.CONNECTION:
            key = str(exception)[:120]
            retries = self._retry_tracker.get(key, 0)
            if retries < self.MAX_AUTO_RETRIES:
                self._retry_tracker[key] = retries + 1
                entry["auto_resolved"] = True
                entry["resolution"] = f"Scheduled retry #{retries + 1}"
                resolved = True
                logger.info("Auto-resolve: connection retry %d for %s", retries + 1, key[:80])
            else:
                logger.warning("Max retries reached for connection error: %s", key[:80])

        elif category == ErrorCategory.IMPORT:
            m = _IMPORT_PATTERN.search(f"{type(exception).__name__}: {str(exception)}")
            if m:
                module = m.group(1)
                entry["auto_resolved"] = False
                entry["resolution"] = f"Suggest: pip install {module}"
                logger.info("Import error for '%s' - user action required", module)

        elif category == ErrorCategory.KEY:
            entry["auto_resolved"] = False
            entry["resolution"] = "Use .get() with a default value"

        if resolved:
            self.resolved_count += 1

        self.error_history.append(entry)
        if len(self.error_history) > 500:
            self.error_history = self.error_history[-250:]

        logger.debug(
            "ErrorResolver [%s] %s – resolved=%s",
            category, str(exception)[:100], resolved,
        )
        return resolved

    def get_stats(self) -> Dict[str, Any]:
        """Return resolver statistics."""
        category_counts: Dict[str, int] = {}
        for e in self.error_history:
            cat = e.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_errors": self.error_count,
            "auto_resolved": self.resolved_count,
            "resolution_rate": (
                round(self.resolved_count / self.error_count * 100, 1)
                if self.error_count else 0.0
            ),
            "by_category": category_counts,
            "recent_errors": self.error_history[-10:],
        }

    def reset(self):
        """Reset counters and history."""
        self.error_count = 0
        self.resolved_count = 0
        self.error_history.clear()
        self._retry_tracker.clear()


def get_error_resolver() -> ErrorResolver:
    """Factory function returning a new ErrorResolver instance."""
    return ErrorResolver()
