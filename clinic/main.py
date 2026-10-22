from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clinic.booking import available_slots, create_appointment, reschedule_appointment
from clinic.database import Base, SessionLocal, engine, get_db
from clinic.models import Appointment, Doctor, Patient, WorkingHour
from clinic.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
    AvailabilityOut,
    AvailableSlot,
    DoctorOut,
    PatientCreate,
    PatientOut,
    utc_datetime,
)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(Doctor.id).limit(1)) is not None:
            return
        for number in range(1, 6):
            doctor = Doctor(name=f"Doctor {number}", timezone="Africa/Nairobi")
            doctor.working_hours = [
                WorkingHour(
                    weekday=weekday,
                    starts_at=datetime.strptime("09:00", "%H:%M").time(),
                    ends_at=datetime.strptime("17:00", "%H:%M").time(),
                )
                for weekday in range(5)
            ]
            db.add(doctor)
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Clinic Booking API", version="1.0.0", lifespan=lifespan)

@app.get("/")
def home():
    return {
        "message": "Welcome to the Clinic Booking API",
        "status": "running",
        "health": "/health",
        "documentation": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/doctors", response_model=list[DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    return db.scalars(select(Doctor).order_by(Doctor.id)).all()


@app.post("/patients", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    patient = Patient(full_name=payload.full_name, email=str(payload.email).lower())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A patient with this email already exists")
    db.refresh(patient)
    return patient


@app.post("/appointments", response_model=AppointmentOut, status_code=201)
def book_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    appointment = create_appointment(db, payload.doctor_id, payload.patient_id, payload.starts_at)
    appointment.starts_at = utc_datetime(appointment.starts_at)
    appointment.created_at = utc_datetime(appointment.created_at)
    return appointment


@app.get("/doctors/{doctor_id}/availability", response_model=AvailabilityOut)
def doctor_availability(
    doctor_id: int,
    day: date = Query(alias="date"),
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    slots = available_slots(db, doctor, day)
    return AvailabilityOut(doctor_id=doctor_id, date=day, slots=[AvailableSlot(starts_at=slot) for slot in slots])


@app.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentCancel,
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.status == "cancelled":
        raise HTTPException(status_code=409, detail="Appointment is already cancelled")
    appointment.status = "cancelled"
    appointment.cancellation_reason = payload.reason.strip()
    db.commit()
    db.refresh(appointment)
    appointment.starts_at = utc_datetime(appointment.starts_at)
    appointment.created_at = utc_datetime(appointment.created_at)
    return appointment


@app.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment = reschedule_appointment(db, appointment, payload.starts_at)
    appointment.starts_at = utc_datetime(appointment.starts_at)
    appointment.created_at = utc_datetime(appointment.created_at)
    return appointment


@app.get("/patients/{patient_id}/appointments", response_model=list[AppointmentOut])
def patient_appointments(patient_id: int, db: Session = Depends(get_db)):
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appointments = db.scalars(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == "booked",
            Appointment.starts_at >= now,
        )
        .order_by(Appointment.starts_at)
    ).all()
    for appointment in appointments:
        appointment.starts_at = utc_datetime(appointment.starts_at)
        appointment.created_at = utc_datetime(appointment.created_at)
    return appointments