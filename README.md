# Clinic Booking API

A small REST API for booking 30-minute clinic appointments. The implementation uses FastAPI, SQLAlchemy, and PostgreSQL in production (SQLite by default for local development and tests).

## System Design

### Models

- `Doctor` has a name and IANA timezone. `WorkingHour` records one opening and closing interval per weekday, in the doctor's local time.
- `Patient` has a name and unique email address.
- `Appointment` links a doctor and patient to a UTC start time and a `booked` or `cancelled` status. Cancellation reason and appointment history are retained.

### Components and decisions

- The API validates working hours, 30-minute alignment, the one-hour booking cutoff, and appointment state in a booking service rather than duplicating those rules across routes.
- Appointment timestamps must include an offset. They are normalized to UTC for storage and returned as UTC timestamps; working hours and availability dates use the doctor's timezone (`Africa/Nairobi` for the five seeded doctors).
- A partial unique index on `(doctor_id, starts_at)` for `status = 'booked'` is the final protection against concurrent double booking. It also lets cancelled slots be booked again without discarding cancellation history. The database enforces this even if two requests pass the initial availability check at the same time.
- Rescheduling updates the existing appointment in one transaction. If the target slot is invalid or already taken, the update fails and the original booking remains intact.
- The app seeds five sample doctors, each working Monday to Friday, 09:00-17:00 East Africa Time. This is deliberately simple sample data; a real clinic would manage schedules and exceptions administratively.
- SQLite keeps local setup lightweight. Production uses Render PostgreSQL; this avoids relying on an ephemeral filesystem for appointment data. Authentication, authorization, migrations, schedule exceptions, and patient privacy controls are outside this assessment's scope.

### Trade-offs

- Retaining cancelled appointment rows improves auditability, but requires queries and the partial index to distinguish active bookings.
- A weekday opening-hours table is enough for the stated scenario, but does not represent holidays, breaks, one-off schedule changes, or multiple shifts in a day.
- The one-hour cutoff is applied consistently to booking, rescheduling, and availability. This bonus behavior means patients will not see slots that are too soon to book.

## API

- `GET /health`
- `GET /doctors`
- `POST /patients`
- `POST /appointments`
- `GET /doctors/{id}/availability?date=YYYY-MM-DD`
- `PATCH /appointments/{id}/cancel`
- `PATCH /appointments/{id}/reschedule`
- `GET /patients/{id}/appointments`
- Interactive API docs: `/docs`

Appointment examples use an explicit timezone offset:

```json
{
  "doctor_id": 1,
  "patient_id": 1,
  "starts_at": "2027-01-04T10:00:00+03:00"
}
```

## Run Locally

Requires Python 3.12 or newer.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn clinic.main:app --reload
```

The app creates `clinic.db` and seeds five sample doctors on startup. Create a patient with `POST /patients`, then book with `POST /appointments`. Run tests with `pytest -q`.

Set `DATABASE_URL` to use a different database. For PostgreSQL, use a SQLAlchemy URL such as `postgresql+psycopg://user:password@host:5432/database`.

## Deployment and CI/CD

The Render blueprint in `render.yaml` provisions the Docker web service and PostgreSQL database. The public application URL is assigned by Render after deployment; add it here before submission: **[deployment URL pending]**.

GitHub Actions runs the test suite on every pull request. Merges to `main` run the tests and then trigger Render deployment using the repository secret `RENDER_DEPLOY_HOOK_URL`. Create the Render service from the blueprint, create a deploy hook for it, then add that hook URL as a GitHub Actions secret. Do not commit the hook URL.
