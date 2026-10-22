from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clinic.models import Appointment, Doctor, Patient, WorkingHour


def as_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc)


def _working_window(db: Session, doctor: Doctor, starts_at: datetime) -> tuple[datetime, datetime]:
    local_start = starts_at.astimezone(ZoneInfo(doctor.timezone))
    hours = db.scalar(
        select(WorkingHour).where(
            WorkingHour.doctor_id == doctor.id,
            WorkingHour.weekday == local_start.weekday(),
        )
    )
    if hours is None:
        raise HTTPException(status_code=422, detail="Doctor does not work on this day")

    local_open = datetime.combine(local_start.date(), hours.starts_at, ZoneInfo(doctor.timezone))
    local_close = datetime.combine(local_start.date(), hours.ends_at, ZoneInfo(doctor.timezone))
    return as_utc_naive(local_open), as_utc_naive(local_close)


def validate_slot(
    db: Session,
    doctor_id: int,
    starts_at: datetime,
    *,
    exclude_appointment_id: int | None = None,
) -> tuple[Doctor, datetime]:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    slot = as_utc_naive(starts_at)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if slot < now:
        raise HTTPException(status_code=422, detail="Appointment cannot be in the past")
    if slot < now + timedelta(hours=1):
        raise HTTPException(status_code=422, detail="Appointments must be booked at least 1 hour ahead")

    window_start, window_end = _working_window(db, doctor, starts_at)
    if slot < window_start or slot + timedelta(minutes=30) > window_end:
        raise HTTPException(status_code=422, detail="Slot must fall within the doctor's working hours")
    if (slot - window_start).total_seconds() % (30 * 60) != 0:
        raise HTTPException(status_code=422, detail="Slot must start on a 30-minute boundary")

    query = select(Appointment.id).where(
        Appointment.doctor_id == doctor_id,
        Appointment.starts_at == slot,
        Appointment.status == "booked",
    )
    if exclude_appointment_id is not None:
        query = query.where(Appointment.id != exclude_appointment_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="This appointment slot is already booked")
    return doctor, slot


def create_appointment(db: Session, doctor_id: int, patient_id: int, starts_at: datetime) -> Appointment:
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    _, slot = validate_slot(db, doctor_id, starts_at)
    appointment = Appointment(
        doctor_id=doctor_id,
        patient_id=patient_id,
        starts_at=slot,
        status="booked",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This appointment slot is already booked")
    db.refresh(appointment)
    return appointment


def available_slots(db: Session, doctor: Doctor, day: date) -> list[datetime]:
    zone = ZoneInfo(doctor.timezone)
    hours = db.scalar(
        select(WorkingHour).where(
            WorkingHour.doctor_id == doctor.id,
            WorkingHour.weekday == day.weekday(),
        )
    )
    if hours is None:
        return []

    current = datetime.combine(day, hours.starts_at, zone)
    close = datetime.combine(day, hours.ends_at, zone)
    slots: list[datetime] = []
    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    while current + timedelta(minutes=30) <= close:
        current_utc = current.astimezone(timezone.utc)
        slot_naive = as_utc_naive(current_utc)
        if current_utc >= cutoff and db.scalar(
            select(Appointment.id).where(
                Appointment.doctor_id == doctor.id,
                Appointment.starts_at == slot_naive,
                Appointment.status == "booked",
            )
        ) is None:
            slots.append(current_utc)
        current += timedelta(minutes=30)
    return slots


def reschedule_appointment(db: Session, appointment: Appointment, starts_at: datetime) -> Appointment:
    if appointment.status == "cancelled":
        raise HTTPException(status_code=409, detail="A cancelled appointment cannot be rescheduled")
    _, slot = validate_slot(
        db,
        appointment.doctor_id,
        starts_at,
        exclude_appointment_id=appointment.id,
    )
    appointment.starts_at = slot
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This appointment slot is already booked")
    db.refresh(appointment)
    return appointment