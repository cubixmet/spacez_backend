# Space Z Django backend

REST API for the Space Z coworking product. The React app in `space-z-launchpad` remains the UI source of truth; this project exposes matching JSON endpoints.

## Stack

- Django 4.2
- Django REST Framework
- SimpleJWT
- PostgreSQL
- django-cors-headers
- Pillow (profile photos)

There is no payment gateway and no geolocation. Payments are recorded manually by an admin.

## Setup

```bash
cd spacez_backend
python -m venv ../venv          # already present in this workspace
source ../venv/bin/activate     # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit PostgreSQL credentials if needed
createdb spacez                 # if the database does not exist yet
python manage.py migrate
python manage.py seed_dev
python manage.py runserver
```

API base URL: `http://127.0.0.1:8000/api/`

Django admin: `http://127.0.0.1:8000/admin/`

Media files (DEBUG): `http://127.0.0.1:8000/media/`

Full endpoint list: [API.md](API.md)

## Development accounts (after `seed_dev`)

| Role | Email | Password |
| --- | --- | --- |
| Super admin | `admin@spacez.in` | `spacez@admin` |
| Member (ACTIVE + billing DUE) | `john@spacez.in` | `spacez123` |
| Member (first-time onboarding) | `new@spacez.in` | `spacez123` |

Rebuild seed data with `python manage.py seed_dev --reset`.

Optional load data (extra members for performance checks):

```bash
python manage.py seed_load --count 60
```

### Tests

```bash
pip install -r requirements-dev.txt
EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend pytest tests/ -q
python scripts/measure_queries.py   # requires DEBUG query logging / running against seeded DB
```

QA + performance write-up: see root `FINAL_REPORT.md`.

## React connection

1. Point the frontend at `VITE_API_URL=http://127.0.0.1:8000/api`.
2. Replace the bodies of `src/services/memberApi.ts` and `src/services/adminApi.ts` with `fetch` calls.
3. Send `Authorization: Bearer <access>` on authenticated routes.
4. Refresh via `POST /api/auth/refresh/` with `{ "refresh": "<token>" }`.
5. Upload photos/proofs as `multipart/form-data`.

Do not change the React workflow or screens unless an API field name requires it. Payloads already use the same camelCase keys as the mock types.
# spacez_backend
