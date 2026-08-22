# Project Overview

E-learning platform focused on Chinese language education.
**Important Architecture Note:** The project is currently transitioning from a Flask/Jinja frontend to a Next.js frontend. Flask will eventually become a purely backend API.

# Tech Stack

- **Backend:** Python (Flask)
- **Frontend (Current):** HTML, CSS, JavaScript (Jinja templating)
- **Frontend (Future):** Next.js (Ignore Next.js specific directories unless explicitly instructed to work on them)
- **Database:** PostgreSQL (using SQLAlchemy)

# Global Execution Rules

When processing requests, strictly adhere to the following workflow and communication constraints:

## 1. Pre-Execution & Strategy

Do not blindly write code. Analyze the request and ask for clarification if:

- The requested feature's implementation strategy is ambiguous.
- The feature conflicts with or duplicates existing functionality.
- The implementation requires third-party services, subscriptions, or manual human setup.

## 2. Communication Constraints

- **No conversational filler:** Do not explain every action, provide summaries for each item, or narrate your thought process.
- **Output only code:** Execute the task directly. Only provide explanations if explicitly asked to do so.
- **No Git operations:** Do not commit code after completing a task.

## 3. Coding Standards

- **Performance:** Prioritize optimal performance and readability in all code structures.
- **Database Queries:** The existing codebase contains a mix of SQLAlchemy and standard SQL. For all **new** code or updates, use SQLAlchemy ORM methods exclusively. Avoid raw SQL strings.
- **Testing:** Always write unit tests for **new** code and ensure the functions execute successfully. For **old/existing** code, only write or update tests if explicitly requested.
- **Housekeeping:** When modifying files in a directory, clean up unused imports, dead code, or unneeded items within that specific scope.

# Project Structure

```text
Learning/
├── app.py                     # Main application entry point
├── db.py                      # Database connection and queries
├── competition_socket.py      # WebSocket setup
├── number_part.py             # Hardcoded lesson render (HSK 1 - Lesson 5)
├── requirements.txt           # Python dependencies
├── env.example                # Environment variables template
├── schema_sql_file/
│   └── schema.sql
├── scripts/
│   ├── run-dev.bat            # Local dev runner (Windows)
│   ├── run-dev.ps1            # Local dev runner (PowerShell)
│   ├── run-pre-dev.ps1        # Pre-dev setup (PowerShell)
│   ├── run-pre-dev.bat        # Run when requirements.txt changes (Windows)
│   ├── run-pre-prod.sh        # Pre-production setup (Shell)
│   └── run-prod.sh            # Run when requirements.txt changes (Production)
└── web_app/
    ├── routes/                # Python routing files
    ├── service/               # Shared services (e.g., i18n_service, gcs_service)
    ├── static/                # JS and CSS assets
    ├── template/              # HTML/Jinja templates
    ├── entity/                # Refactor target: Grouped per model (entity/<model>/ containing entity.py, repository.py, service.py)
    ├── models/                # Speech-to-text transcription models
    └── tests/                 # Dedicated testing directory
```
