# AI Project Audit Platform — Backend

Production-ready FastAPI backend for an AI-powered Project Audit Platform.

## Tech Stack

- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **Database**: SQLite
- **Auth**: JWT (python-jose + passlib/bcrypt)
- **Validation**: Pydantic v2

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your own SECRET_KEY for production
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

The server starts at **http://127.0.0.1:8000**

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 5. Default admin credentials

```
Email:    admin@audit.com
Password: admin123
```

> ⚠️ Change these in `.env` before deploying to production.

## Architecture

```
app/
├── main.py              # App factory, middleware, startup
├── config.py            # Environment-based settings
├── database.py          # SQLAlchemy engine & session
├── dependencies.py      # Shared FastAPI dependencies
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── repositories/        # Data-access layer
├── services/            # Business-logic layer
├── routers/             # API route handlers
└── utils/               # Security helpers, custom exceptions
```

## API Endpoints

### Authentication (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/login` | Authenticate & get JWT |
| POST | `/register` | Create a new account |
| GET | `/me` | Get current user profile |

### Users (`/api/v1/users`) — Admin only

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all users |
| GET | `/{id}` | Get user by ID |
| PUT | `/{id}` | Update user |
| DELETE | `/{id}` | Delete user |

### Projects (`/api/v1/projects`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List projects |
| POST | `/` | Create project |
| GET | `/{id}` | Get project |
| PUT | `/{id}` | Update project |
| DELETE | `/{id}` | Delete project |
| GET | `/{id}/reports` | List project reports |
| GET | `/{id}/audit-runs` | List project audit runs |

### Reports (`/api/v1/reports`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List reports |
| POST | `/` | Create report |
| GET | `/{id}` | Get report |
| PUT | `/{id}` | Update report |
| DELETE | `/{id}` | Delete report |

### Audit Runs (`/api/v1/audit-runs`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List audit runs |
| POST | `/` | Create audit run |
| GET | `/{id}` | Get audit run |
| PATCH | `/{id}/status` | Update audit run status |

### Audit Run Status Transitions

```
pending  → running  → completed
   ↓         ↓
  failed ← failed
   ↓
 pending  (retry)
```

## Pagination

All list endpoints support pagination:
- `page` (default: 1)
- `page_size` (default: 20, max: 100)

## License

MIT
