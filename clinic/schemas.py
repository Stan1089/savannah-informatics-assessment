from datetime import date, datetime, time, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class DoctorOut(BaseModel):
    id: int
    name: str
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr


class PatientOut(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class AppointmentReschedule(BaseModel):
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")
        return value


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def require_nonblank_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cancellation reason cannot be blank")
        return value


class AppointmentOut(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    starts_at: datetime
    status: str
    cancellation_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class AvailableSlot(BaseModel):
    starts_at: datetime


class AvailabilityOut(BaseModel):
    doctor_id: int
    date: date
    slots: list[AvailableSlot]


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)