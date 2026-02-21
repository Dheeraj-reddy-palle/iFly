# iFly - Flight Price Intelligence System

iFly is a scalable backend architecture for flight price tracking, analytics, and intelligent predictions. 
This is the foundational setup using FastAPI, SQLAlchemy, and PostgreSQL.

## Prerequisites
- Python 3.11+
- PostgreSQL server running locally or remotely

## Setup Instructions

1. **Navigate to the core project directory:**
   ```bash
   cd ifly
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # .\venv\Scripts\activate   # On Windows
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables Config:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Update the `.env` file with your PostgreSQL credentials in `DATABASE_URL`.

5. **Start the FastAPI Server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Verification

Ping the health endpoint to verify the service is running successfully:
```bash
curl http://localhost:8000/health
```
You should see: `{"status":"ok","environment":"development"}`

## Project Structure Overview
- `app/main.py`: Application entry point and configuration routes.
- `app/config.py`: Environment variable loading.
- `app/database.py`: PostgreSQL connection and SQLAlchemy declarative base definitions.
- `app/models/`: Database ORM models (e.g. `FlightOffer`).
- `app/schemas/`: Pydantic models for request/response validation.
- `app/services/`: Isolated business logic layer (API integrations, ML features).
