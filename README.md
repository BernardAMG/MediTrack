# MediTrack

A medication reminder and management app built to help patients (and eventually caregivers) keep track of medications, schedules, doses, and history, built in Python with a real database, authentication, and background notifications.

## Why I built this

During my vacation, I was caring for a family member who needed regular medication. Even wanting to do it right, it was easy to lose track, I once realized an expensive medication had expired because I'd repeatedly forgotten to administer it. I started with a simple Apple Shortcuts reminder for myself, and that small workaround eventually became the idea for building a proper application.

## Features

- **User accounts** — registration and login with bcrypt password hashing
- **Medication management** — add, edit, and delete medications with dosage, schedule time, and frequency
- **Dose tracking** — mark each dose as taken or skipped, with a full timestamped history
- **Reminders** — a background watcher checks scheduled times and fires a desktop notification (via `plyer`) when a dose is due
- **Real navigation** — separate login/register and dashboard screens using Flet's routing
- **Relational database** — SQLite with proper foreign key relationships between users, medications, and dose records

## Architecture
```
Flet UI (login/register screen, dashboard screen)
        │
Application logic (in app.py — event handlers, session state)
        │
Data layer (database.py — sqlite3 functions)
        │
SQLite database (meditrack.db)
        │
Notification layer (plyer, triggered by a background thread)
```


## Database schema

**users**
| column | type | notes |
|---|---|---|
| id | INTEGER | primary key |
| name | TEXT | |
| email | TEXT | unique |
| password_hash | TEXT | bcrypt hash, never plain text |
| created_at | TEXT | timestamp |

**medications**
| column | type | notes |
|---|---|---|
| id | INTEGER | primary key |
| user_id | INTEGER | foreign key → users.id |
| name, dosage, time, frequency | TEXT | |
| created_at | TEXT | timestamp |

**dose_records**
| column | type | notes |
|---|---|---|
| id | INTEGER | primary key |
| medication_id | INTEGER | foreign key → medications.id |
| status | TEXT | "taken" or "skipped" |
| taken_at | TEXT | timestamp |

## Tech stack

- **Python 3** — all application logic
- **Flet** — UI framework (Python-only, no HTML/CSS/JS)
- **SQLite** (`sqlite3`, standard library) — database
- **bcrypt** — password hashing
- **plyer** — cross-platform desktop notifications
- 100% free and open-source tools — no paid services required

## How to run

```bash
git clone https://github.com/BernardAMG/MediTrack.git
cd MediTrack
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

## Roadmap

- [x] Authentication (registration, login, password hashing)
- [x] Medication CRUD
- [x] Dose tracking + history
- [x] Background reminders with desktop notifications
- [x] Multi-screen navigation
- [x] Caregiver mode (manage medications for a care recipient)
- [x] Low-stock and expiry warnings
- [x] Adherence percentage / statistics
- [ ] UI redesign (in progress — card-based medication list and warnings card done)
- [ ] Automated tests

## Important note

MediTrack is a reminder and management tool only. It does not diagnose conditions, prescribe medication, or offer medical advice, it manages information and schedules that the user has entered themselves. Always consult a doctor or pharmacist for medical decisions.

git add README.md
git commit -m "Add README with project overview, architecture, and setup instructions"
git push
