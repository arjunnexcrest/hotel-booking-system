# Hotel Booking System — Backend (Django REST Framework)

Repo: https://github.com/arjunnexcrest/hotel-booking-system.git

## Quick start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # or use the provided .env
python manage.py migrate
python manage.py runserver
```

API docs: http://127.0.0.1:8000/api/docs/

## Folder structure

```
backend/
├── config/                 # Project settings, root URLs, ASGI/WSGI
├── accounts/               # Auth, users, roles (FR-001–006)
├── hotels/                 # Hotel registration & approval (FR-007–015)
├── restaurants/            # Restaurants & operating hours (FR-021–022)
├── tables/                 # Tables & operational status (FR-023–028)
├── bookings/               # Reservations (FR-029–040)
├── staff/                  # Staff, assignments, cleaning tasks
├── ai_monitoring/          # Cameras, AI events, alerts (FR-041–063)
├── notifications/          # Email/SMS/in-app notifications
├── audit/                  # Audit / activity logs
├── core/                   # Shared utils, permissions, platform config
├── media/                  # Uploaded files (gitignored)
├── staticfiles/            # Collected static (gitignored)
├── templates/
├── manage.py
├── requirements.txt
├── .env
└── .env.example
```

Each app follows:

```
app/
├── models.py
├── views.py
├── serializers.py
├── urls.py
├── admin.py
├── services/               # Business logic
├── permissions/
├── filters/
└── migrations/
```
