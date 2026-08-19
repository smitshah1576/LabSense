"""Pydantic v2 data validation schemas for LabSense backend API."""

from datetime import date, datetime, time
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

from .enums import DamageReportStatus, PCState, UserRole


# --- Authentication & User Schemas ---

class UserCreate(BaseModel):
    """Schema for registering a new user."""

    email: str
    password: str
    full_name: str
    role: UserRole


class UserLogin(BaseModel):
    """Schema for user login credentials."""

    email: str
    password: str


class UserResponse(BaseModel):
    """Schema for user details in API responses."""

    user_id: int
    email: str
    full_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for JWT authentication token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Lab & PC Schemas ---

class LabResponse(BaseModel):
    """Schema for lab details response."""

    lab_id: str
    lab_name: str
    operating_start_time: time
    operating_end_time: time
    state: Optional[str] = None


class PCResponse(BaseModel):
    """Schema for PC status and metrics response."""

    pc_id: str
    lab_id: str
    current_state: PCState
    is_maintenance: bool
    last_heartbeat_at: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    idle_seconds: Optional[int] = None
    session_active: Optional[bool] = None
    screen_locked: Optional[bool] = None


class PCMaintenanceToggle(BaseModel):
    """Schema for toggling maintenance mode on a PC."""

    is_maintenance: bool


# --- Timetable Schemas ---

class TimetableEntry(BaseModel):
    """Schema representing a timetable schedule entry."""

    timetable_id: Optional[int] = None
    lab_id: str
    day_of_week: int
    start_time: time
    end_time: time
    course_code: Optional[str] = None


class TimetableCreate(BaseModel):
    """Schema for creating a new timetable slot."""

    lab_id: str
    day_of_week: int
    start_time: time
    end_time: time
    course_code: Optional[str] = None


class SlotCancellation(BaseModel):
    """Schema representing a cancelled schedule slot."""

    cancellation_id: Optional[int] = None
    timetable_id: int
    cancelled_for_date: date
    cancelled_by: Optional[int] = None


class SlotCancellationCreate(BaseModel):
    """Schema for creating a slot cancellation request."""

    timetable_id: int
    cancelled_for_date: date


# --- Damage Report Schemas ---

class DamageReportCreate(BaseModel):
    """Schema for submitting a PC damage report."""

    pc_id: str
    issue_description: str


class DamageReportResponse(BaseModel):
    """Schema for damage report details."""

    report_id: int
    pc_id: str
    reported_by: int
    issue_description: str
    status: DamageReportStatus
    created_at: datetime
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DamageReportResolve(BaseModel):
    """Schema for updating/resolving a damage report status."""

    status: DamageReportStatus


# --- Software Search & WebSocket Schemas ---

class SoftwareSearchResult(BaseModel):
    """Schema for software search query results."""

    pc_id: str
    lab_id: str
    lab_name: str
    matching_packages: list[str]


class WSMessage(BaseModel):
    """Schema for WebSocket broadcast messages."""

    type: str
    data: dict[str, Any]
