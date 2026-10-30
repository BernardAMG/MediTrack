# MediTrack Architecture, Maintenance & Quality Assurance Framework

This document outlines the architectural principles, maintenance protocols, redevelopment roadmap, and Quality Assurance (QA) framework for **MediTrack**.

---

## 1. System Architecture Overview

MediTrack follows a structured layered design separating persistent storage, business logic, background services, and graphical presentation.

```
┌────────────────────────────────────────────────────────┐
│               Presentation Layer (Flet UI)             │
│   - AuthView (Register/Login)                          │
│   - DashboardView (Medications, Badges, History, Chips)│
│   - Modals & Dialogs (Refill, Edit, Batch Add)         │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Services Layer                      │
│   - Watcher Daemon Service (15-min catch-up window)   │
│   - Notification Service (win11toast reminders)        │
│   - Adherence & Metrics Calculator                     │
│   - CSV Export & Reporting Service                     │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│              Data & Persistence Layer                  │
│   - Connection Manager (PRAGMA foreign_keys = ON)      │
│   - Migration Engine (schema_migrations versioning)    │
│   - Health & Integrity Checkers (PRAGMA integrity_check│
│   - Database Maintenance (VACUUM, Snapshot Backups)    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│               Operating System & Storage               │
│   - %APPDATA%\MediTrack\meditrack.db                   │
│   - %APPDATA%\MediTrack\backups\                       │
│   - %APPDATA%\MediTrack\logs\meditrack.log             │
└────────────────────────────────────────────────────────┘
```

---

## 2. Maintenance & Update Provisions

### 2.1 Database Location & Multi-Version Persistence
* **AppData Storage**: The SQLite database is stored in `%APPDATA%\MediTrack\meditrack.db`. This guarantees data persists across `.exe` updates, re-packaging (`flet pack`), or launcher directory changes.
* **Automatic Pre-Migration Backups**: During startup, `prepare_database_location()` verifies if an existing database is present and creates an immutable baseline copy (`meditrack.pre-migration.bak`) before any migrations run.
* **Rolling Backup Snapshots**: `create_database_backup(tag=None)` enables on-demand and automated timestamped backups in `%APPDATA%\MediTrack\backups\`.

### 2.2 Versioned Schema Migration Framework
Schema evolution is managed sequentially via the `schema_migrations` table:
```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```
* **Migration 1 (`create_base_tables`)**: Instantiates `users`, `medications`, `dose_records`, and `care_recipients`.
* **Migration 2 (`add_recipient_and_stock_columns`)**: Adds `recipient_id`, `quantity_remaining`, and `expiry_date`.
* **Migration 3 (`normalize_schedules_table_1nf`)**: Creates normalized `medication_schedules`, links `dose_records.schedule_id`, and safely migrates legacy comma-separated times with zero data loss.

#### Adding New Migrations (Protocol for Future Developers):
1. In `database.py`, increment the version number in `run_all_migrations()`.
2. Wrap DDL statements in `if N not in applied:`.
3. Call `record_migration(N, "migration_description")`.

### 2.3 Automated Database Diagnostics & Health Checks
* **Integrity Validation**: `check_database_integrity()` executes `PRAGMA integrity_check` on startup. If database corruption is detected, it logs warnings and alerts maintenance.
* **Compaction (`VACUUM`)**: `vacuum_database()` defragments the SQLite B-tree pages and reclaims unallocated space after extensive dose logging.

### 2.4 Production Logging System
Bare `print()` calls are replaced with standard Python `logging`:
* **Rotating Log File**: Stored at `%APPDATA%\MediTrack\logs\meditrack.log` (1MB limit, 3 rotating backups).
* **Dual Output**: Formatted console stream for development debugging, and persistent log files for diagnostics and post-mortem analysis.

---

## 3. Future Redevelopment & Remodeling Roadmap

### 3.1 Modular Decomposition Blueprint
To scale the application, `app.py` (~1,000 lines) can be decomposed into domain modules:

```text
MediTrak/
├── config.py                 # Centralized configuration & logging
├── database.py               # Database engine & connection management
├── domain/                   # Business entities & dataclasses
│   ├── user.py
│   ├── medication.py
│   └── dose.py
├── repositories/             # SQL query isolation (Repository Pattern)
│   ├── user_repository.py
│   ├── medication_repository.py
│   └── dose_repository.py
├── services/                 # Domain business logic
│   ├── watcher_service.py    # Background reminder daemon
│   ├── adherence_service.py  # Adherence math & statistics
│   └── export_service.py     # CSV report generation
├── ui/                       # Flet View components
│   ├── views/
│   │   ├── auth_view.py
│   │   └── dashboard_view.py
│   └── components/
│       ├── medication_card.py
│       ├── filter_chips.py
│       └── refill_dialog.py
└── test_database.py          # Automated test suite
```

### 3.2 Web & Mobile Redevelopment Path
The core business rules (`should_alert`, `normalize_time`, `calculate_adherence`, and SQL repositories) are completely independent of Flet. This allows:
1. **REST API Backend**: Wrapping `services/` with **FastAPI** to expose endpoints (`GET /medications`, `POST /doses`).
2. **Mobile Client**: Connecting a Flutter or React Native mobile client to the FastAPI backend.
3. **Cloud Synchronization**: Swapping the local SQLite connection in `get_connection()` for PostgreSQL (e.g. Supabase) without rewriting business validation logic.

---

## 4. Quality Assurance (QA) Framework

### 4.1 Testing Pyramid
MediTrack employs a 3-tier testing strategy:
1. **Unit Tests (Fast & Pure)**:
   - Tests pure deterministic algorithms (`should_alert()`, `normalize_time()`).
   - Boundary tests for exact-minute matching, catch-up window expirations (+16 min), and edge cases.
2. **Database Integration Tests**:
   - In-memory/temporary database testing for transactional integrity.
   - Verifies cascade deletes (`ON DELETE CASCADE`), foreign key enforcement (`PRAGMA foreign_keys = ON`), and migration idempotency.
   - Validates CSV file generation and schema formatting.
3. **End-to-End & Smoke Tests**:
   - Application startup smoke tests verifying that AppData directories and health checks succeed.

### 4.2 Automated CI/CD Pipeline (GitHub Actions)
Continuous Integration runs on every push and pull request via `.github/workflows/ci.yml`:
* **Matrix Testing**: Validates compatibility across Python 3.11 and 3.12 on `windows-latest`.
* **Bytecode Compilation**: Runs `py_compile` to catch syntax errors or broken imports before execution.
* **Automated Test Suite**: Executes `unittest test_database.py -v`. Pull requests cannot be merged if any test fails.

### 4.3 Pre-Release Quality Checklist
Before building a standalone executable (`flet pack`):
- [ ] Run test suite: `python -m unittest test_database.py` (Must report 100% OK).
- [ ] Verify integrity check: `python -c "import database; print(database.check_database_integrity())"`
- [ ] Verify clean compilation: `python -m py_compile config.py database.py app.py test_database.py`
- [ ] Check logs: Inspect `%APPDATA%\MediTrack\logs\meditrack.log` for warnings or errors.
- [ ] Test standalone package on a clean Windows machine without Python installed.
