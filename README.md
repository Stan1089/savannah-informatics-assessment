
# Clinic Booking API

A REST API for managing clinic appointments, built with FastAPI, SQLAlchemy, and PostgreSQL in production. SQLite is used by default for local development and testing.

The API supports doctor discovery, patient registration, appointment booking, availability checks, cancellation, rescheduling, and retrieval of upcoming patient appointments.

**Live API:** https://savannah-informatics-assessment.onrender.com/

**Interactive API documentation:** https://savannah-informatics-assessment.onrender.com/docs

**Health check:** https://savannah-informatics-assessment.onrender.com/health

## Table of Contents

- [Features](#features)
- [System Design](#system-design)
- [Technology Stack](#technology-stack)
- [API Endpoints](#api-endpoints)
- [Appointment Rules](#appointment-rules)
- [Example Requests](#example-requests)
- [Run Locally](#run-locally)
- [Testing](#testing)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Limitations and Trade-offs](#limitations-and-trade-offs)
- [AI Usage Reflection](#ai-usage-reflection)

## Features

- Register patients with unique email addresses.
- List available doctors.
- Retrieve available appointment slots for a specified date.
- Book 30-minute appointments.
- Prevent conflicting bookings for the same doctor and start time.
- Cancel appointments while retaining cancellation history.
- Reschedule appointments while preserving the original booking if the new slot is invalid.
- Retrieve upcoming booked appointments for a patient.
- Validate appointment timestamps and normalize them to UTC.
- Initialize the database and seed sample doctors on startup.
- Provide interactive API documentation through Swagger UI.
- Run automated tests through GitHub Actions.

## System Design

### Data Models

**Doctor**

Represents a doctor with a name, timezone, and associated working hours.

**WorkingHour**

Defines a doctor's opening and closing times for a particular weekday. Working hours are interpreted in the doctor's local timezone.

**Patient**

Stores a patient's full name and unique email address.

**Appointment**

Associates a patient with a doctor and an appointment start time. Appointments have a status of `booked` or `cancelled`. Cancellation reasons are retained for record keeping.

### Architecture and Components

The application separates HTTP request handling, business logic, database access, and data validation.

- **API layer:** FastAPI exposes REST endpoints and handles request validation, dependency injection, and HTTP responses.
- **Business logic:** The booking service validates appointment slots, working hours, booking cutoffs, and rescheduling rules.
- **Data access:** SQLAlchemy manages database models, queries, and transactions.
- **Database:** SQLite supports local development and testing. PostgreSQL is used in production.
- **Testing:** Pytest runs automated tests.
- **Deployment:** Render hosts the API, while GitHub Actions automates testing and triggers deployment.

### Key Design Decisions

**Timezones and timestamps**

Appointment timestamps must include a timezone offset. The application normalizes appointment times to UTC for storage and API responses. Availability is calculated using the doctor's local timezone.

The seeded doctors use the `Africa/Nairobi` timezone.

**Double-booking prevention**

The database uses a partial unique index on `(doctor_id, starts_at)` for appointments with `status = 'booked'`. This prevents two active appointments from occupying the same doctor's time slot, including when concurrent requests pass the initial availability check.

Cancelled appointments do not occupy the slot, allowing it to be booked again while preserving the previous appointment record.

**Transactional rescheduling**

Rescheduling updates an existing appointment. If the target slot is invalid or unavailable, the operation fails and the original booking is retained.

**Database initialization**

On application startup, the database tables are initialized and five sample doctors are created if no doctors exist. Each sample doctor works Monday to Friday, 09:00–17:00 East Africa Time.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| API framework | FastAPI |
| ASGI server | Uvicorn |
| ORM | SQLAlchemy |
| Production database | PostgreSQL |
| Local and test database | SQLite |
| Data validation | Pydantic |
| Automated testing | Pytest |
| CI/CD | GitHub Actions |
| Hosting | Render |
| Containerization | Docker |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check application health |
| GET | `/doctors` | List doctors |
| POST | `/patients` | Register a patient |
| POST | `/appointments` | Book an appointment |
| GET | `/doctors/{doctor_id}/availability?date=YYYY-MM-DD` | Retrieve available appointment slots |
| PATCH | `/appointments/{appointment_id}/cancel` | Cancel an appointment |
| PATCH | `/appointments/{appointment_id}/reschedule` | Reschedule an appointment |
| GET | `/patients/{patient_id}/appointments` | Retrieve upcoming booked appointments |

Interactive documentation is available at `/docs`, and the OpenAPI schema is available at `/openapi.json`.

## Appointment Rules

The application enforces the following business rules:

1. Appointments last 30 minutes.
2. Appointment start times must align with 30-minute intervals.
3. Appointments must fall within the doctor's working hours.
4. A minimum one-hour booking cutoff applies to booking, rescheduling, and availability.
5. Appointment timestamps must include an explicit timezone offset.
6. Appointment times are normalized to UTC.
7. A doctor cannot have two active appointments at the same start time.
8. Patients cannot register multiple times with the same email address.
9. Cancelled appointments retain their history and cancellation reason.
10. Invalid booking and rescheduling requests are rejected without replacing an existing booking.

## Example Requests

The following examples illustrate the API request formats. They can also be tested through Swagger UI at `/docs`.

### Check API health

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

### List doctors

```http
GET /doctors
```

Returns the available doctor records, including their IDs and timezones.

### Register a patient

```http
POST /patients
Content-Type: application/json
```

Request body:

```json
{
  "full_name": "Jane Doe",
  "email": "jane.doe@example.com"
}
```

A successful request returns the created patient record. Use the returned patient ID when booking an appointment.

### Check appointment availability

```http
GET /doctors/1/availability?date=2027-01-04
```

Returns available appointment slots for doctor `1` on the requested date, subject to working hours, existing bookings, and the booking cutoff.

### Book an appointment

```http
POST /appointments
Content-Type: application/json
```

Request body:

```json
{
  "doctor_id": 1,
  "patient_id": 1,
  "starts_at": "2027-01-04T10:00:00+03:00"
}
```

Use valid doctor and patient IDs and a slot that satisfies the booking rules. The example timestamp uses the East Africa Time offset of `+03:00`.

### Cancel an appointment

```http
PATCH /appointments/1/cancel
Content-Type: application/json
```

Request body:

```json
{
  "reason": "Patient requested cancellation"
}
```

Use an existing appointment ID. The appointment is marked as cancelled, and its cancellation reason is retained.

### Reschedule an appointment

```http
PATCH /appointments/1/reschedule
Content-Type: application/json
```

Request body:

```json
{
  "starts_at": "2027-01-04T11:00:00+03:00"
}
```

The new start time must satisfy the appointment rules and be available for the doctor.

### Retrieve a patient's upcoming appointments

```http
GET /patients/1/appointments
```

Returns the patient's upcoming appointments that remain booked.

**Note:** The IDs and dates in these examples are illustrative. Use existing IDs and dates appropriate to the API's booking rules when testing.

## Run Locally

### Prerequisites

- Python 3.12 or newer
- Git
- A terminal, such as the VS Code PowerShell terminal

### 1. Clone the repository

```bash
git clone https://github.com/Stan1089/savannah-informatics-assessment.git
cd savannah-informatics-assessment
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks virtual-environment activation, use the appropriate Python executable directly or follow your environment's PowerShell execution policy guidance.

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Start the application

```powershell
python -m uvicorn clinic.main:app --reload
```

The API should be available at:

- Homepage: http://127.0.0.1:8000/
- Interactive documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

The application initializes the database and seeds sample doctors on startup.

### 5. Stop the application

Press `Ctrl+C` in the terminal.

## Testing

The project uses Pytest for automated testing. Tests are located in `tests/test_booking.py`.

Run the test suite locally with:

```powershell
python -m pytest -v
```

Alternatively, run:

```powershell
pytest -q
```

The test suite has passed locally and through the configured GitHub Actions workflow.

## Configuration

The application supports database configuration through the `DATABASE_URL` environment variable.

By default, local development uses SQLite.

For PostgreSQL, use a SQLAlchemy connection URL such as:

```text
postgresql+psycopg://user:password@host:5432/database
```

Replace the example credentials and host with your actual database configuration. Do not commit real credentials, passwords, or other secrets to source control.

The Render deployment configuration is defined in `render.yaml`.

## Deployment

The application is deployed on Render.

- **Production API:** https://savannah-informatics-assessment.onrender.com/
- **Swagger documentation:** https://savannah-informatics-assessment.onrender.com/docs
- **Health check:** https://savannah-informatics-assessment.onrender.com/health

The production environment uses PostgreSQL to avoid relying on an ephemeral local filesystem for persistent appointment data.

Render may take a short time to start the service after periods of inactivity, depending on the hosting plan.

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and continuous deployment.

### Continuous Integration

The workflow is defined in `.github/workflows/ci-cd.yml`.

The workflow runs on pull requests and pushes to the `main` branch.

The test job:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Installs dependencies from `requirements.txt`.
4. Runs the automated test suite using `pytest -q`.

### Continuous Deployment

When code is pushed to `main`, the deployment job runs only after the test job succeeds.

The workflow sends a deployment request to Render using the `RENDER_DEPLOY_HOOK_URL` GitHub Actions repository secret.

The deploy hook URL is stored as a secret and must not be committed to the repository.

### Deployment Verification

After deployment, verify the service by:

- Opening the API homepage.
- Opening Swagger UI and inspecting the available endpoints.
- Checking the `/health` endpoint.
- Confirming that the latest GitHub Actions run shows successful `test` and `deploy` jobs.
- Reviewing Render deployment logs if the service does not respond as expected.

## Limitations and Trade-offs

- The application uses five seeded doctors rather than an administrative doctor-management interface.
- Working hours are defined by weekday and do not model holidays, breaks, exceptional closures, or multiple shifts.
- Authentication and authorization are outside the scope of this assessment.
- Database migration management is not included in the current implementation.
- Patient privacy controls and production-grade access policies would need to be added before using the application with real patient information.
- Cancelled appointments are retained for auditability, so queries must distinguish active and cancelled bookings.

These trade-offs keep the implementation focused on the appointment-booking requirements while identifying areas for future improvement.

## AI Usage Reflection

AI tools were used as a development aid to explore implementation approaches, troubleshoot technical errors, and improve project documentation. Suggestions were reviewed and validated through local testing, deployed endpoint checks, and GitHub Actions results.

This process reinforced the importance of understanding generated code, testing business rules, investigating deployment failures, and verifying changes rather than relying on AI-generated output without review.