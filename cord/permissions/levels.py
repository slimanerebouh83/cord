"""
CORD Permissions - Permission and Risk Levels
Defines permission tiers: READ_ONLY, SAFE, MODIFY, EXECUTE, ADMIN
and risk classifications: LOW, MEDIUM, HIGH, CRITICAL.
"""

from __future__ import annotations
from enum import Enum


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    SAFE = "SAFE"
    MODIFY = "MODIFY"
    EXECUTE = "EXECUTE"
    ADMIN = "ADMIN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Hierarchy mapping: Lower index requires less privilege
PERMISSION_HIERARCHY = {
    PermissionLevel.READ_ONLY: 1,
    PermissionLevel.SAFE: 2,
    PermissionLevel.MODIFY: 3,
    PermissionLevel.EXECUTE: 4,
    PermissionLevel.ADMIN: 5,
}
