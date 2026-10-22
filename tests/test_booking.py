from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from clinic.database import Base, get_db
from clinic.main import app
from clinic.models import Doctor, Patient, WorkingHour


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=test_engine)
    with testing_session() as db:
        doctor = Doctor(name="Dr. Test", timezone="Africa/Nairobi")
        patient = Patient(full_name="Test Patient", email="patient@example.com")
        db.add_all([doctor, patient])
        db.flush()
        db.add(WorkingHour(doctor_id=doctor.id, weekday=0, starts_at=time(9), ends_at=time(17)))
        db.commit()
        doctor_id, patient_id = doctor.id, patient.id

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.doctor_id = doctor_id
        test_client.patient_id = patient_id
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def next_monday_at(hour: int = 10) -> datetime:
    now = datetime.now(timezone.utc)
    days_until_monday = (7 - now.weekday()) % 7
    target_date = now.date() + timedelta(days=days_until_monday)
    if days_until_monday == 0 and now.hour >= hour:
        target_date += timedelta(days=7)
    return datetime.combine(target_date, time(hour), timezone(timedelta(hours=3)))


def book(client: TestClient, starts_at: datetime):
    return client.post(
        "/appointments",
        json={
            "doctor_id": client.doctor_id,
            "patient_id": client.patient_id,
            "starts_at": starts_at.isoformat(),
        },
    )


def test_booking_and_availability(client: TestClient):
    starts_at = next_monday_at()
    response = book(client, starts_at)
    assert response.status_code == 201
    assert response.json()["starts_at"] == starts_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    availability = client.get(
        f"/doctors/{client.doctor_id}/availability",
        params={"date": starts_at.date().isoformat()},
    )
    assert availability.status_code == 200
    assert starts_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") not in {
        slot["starts_at"] for slot in availability.json()["slots"]
    }


def test_rejects_duplicate_and_out_of_hours_booking(client: TestClient):
    starts_at = next_monday_at()
    assert book(client, starts_at).status_code == 201
    duplicate = book(client, starts_at)
    assert duplicate.status_code == 409
    assert "already booked" in duplicate.json()["detail"]

    outside_hours = book(client, starts_at.replace(hour=18))
    assert outside_hours.status_code == 422


def test_cancel_releases_slot_and_cannot_be_cancelled_twice(client: TestClient):
    starts_at = next_monday_at()
    booking = book(client, starts_at).json()
    blank_reason = client.patch(
        f"/appointments/{booking['id']}/cancel", json={"reason": "   "}
    )
    assert blank_reason.status_code == 422
    cancelled = client.patch(
        f"/appointments/{booking['id']}/cancel",
        json={"reason": "Patient request"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancellation_reason"] == "Patient request"
    assert book(client, starts_at).status_code == 201
    assert client.patch(
        f"/appointments/{booking['id']}/cancel", json={"reason": "Again"}
    ).status_code == 409


def test_reschedule_releases_old_slot_and_rejects_cancelled_appointment(client: TestClient):
    original = next_monday_at()
    booking = book(client, original).json()
    replacement = original + timedelta(minutes=30)
    moved = client.patch(
        f"/appointments/{booking['id']}/reschedule",
        json={"starts_at": replacement.isoformat()},
    )
    assert moved.status_code == 200
    assert moved.json()["starts_at"] == replacement.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    assert book(client, original).status_code == 201

    client.patch(f"/appointments/{booking['id']}/cancel", json={"reason": "No longer needed"})
    cancelled_reschedule = client.patch(
        f"/appointments/{booking['id']}/reschedule",
        json={"starts_at": (replacement + timedelta(minutes=30)).isoformat()},
    )
    assert cancelled_reschedule.status_code == 409


def test_rejects_timezone_missing_and_appointments_within_one_hour(client: TestClient):
    missing_timezone = book(client, next_monday_at().replace(tzinfo=None))
    assert missing_timezone.status_code == 422

    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    response = book(client, soon)
    assert response.status_code == 422
    assert "1 hour" in response.json()["detail"]


def test_patient_upcoming_appointments_are_sorted(client: TestClient):
    later = next_monday_at(11)
    earlier = next_monday_at(10)
    assert book(client, later).status_code == 201
    assert book(client, earlier).status_code == 201
    response = client.get(f"/patients/{client.patient_id}/appointments")
    assert response.status_code == 200
    assert [item["starts_at"] for item in response.json()] == [
        earlier.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        later.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    ]