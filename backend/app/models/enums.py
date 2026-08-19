"""Enumeration types matching PostgreSQL schema enums for LabSense."""

from enum import Enum


class PCState(str, Enum):
    """PC operational states."""

    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    AVAILABLE_SLEEP = "AVAILABLE_SLEEP"
    MAINTENANCE = "MAINTENANCE"


class LabState(str, Enum):
    """Overall lab status."""

    OPEN = "OPEN"
    OCCUPIED = "OCCUPIED"
    CLOSED = "CLOSED"


class UserRole(str, Enum):
    """User account roles."""

    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    ADMIN = "ADMIN"


class DamageReportStatus(str, Enum):
    """Status of PC hardware/software damage reports."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"
