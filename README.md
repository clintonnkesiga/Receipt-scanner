# Receipt Scanner

Scan supermarket and fuel-station receipts and store them in a searchable digital archive.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | SvelteKit (Svelte 5) + Tailwind CSS |
| Backend | Python 3.12 + FastAPI |
| OCR | Tesseract + OpenCV preprocessing (local, no cloud required) |
| Database | PostgreSQL 16 (SQLAlchemy ORM) |
| File storage | [SeaweedFS](https://github.com/seaweedfs/seaweedfs) distributed object store |

## Quick Start (Docker Compose)

```bash
git clone https://github.com/your-org/receipt-scanner.git
cd receipt-scanner

cp backend/.env.example backend/.env
# Edit backend/.env — set SECRET_KEY and SUPERADMIN_* credentials at minimum

docker compose up -d
```

| Service | URL |
|---|---|
| Web UI | http://localhost:5179 |
| API (Swagger) | http://localhost:8000/docs |
| SeaweedFS master | http://localhost:9333 |
| SeaweedFS filer | http://localhost:8888 |

Create the super-admin account on first run:

```bash
docker compose exec backend python -m app.seed
```

Then sign in at http://localhost:5179/login.

## Architecture

```
Browser
  │
  ├─ SvelteKit frontend  (port 5179 in Docker / 5173 local dev)
  │      │  /api/* proxied to backend
  │
  └─ FastAPI backend  (port 8000)
         │
         ├─ PostgreSQL  — receipt metadata, users, categories
         │
         └─ SeaweedFS filer  (port 8888)
                │
                └─ SeaweedFS volume server  (port 8080)
                        │  actual file bytes
                └─ SeaweedFS master  (port 9333)
                        │  cluster coordination
```

### Upload & OCR flow

1. Browser posts receipt image/PDF to `POST /api/receipts/scan`.
2. Backend writes a **temp file**, runs Tesseract OCR with OpenCV preprocessing, then deletes it.
3. File bytes are uploaded to **SeaweedFS filer** at `/receipts/{user_id}/{uuid}.{ext}`.
4. The filer path is returned to the browser along with OCR-extracted fields.
5. User reviews and corrects fields, then saves — metadata written to PostgreSQL, filer path stored as `image_path`.

### File storage

Uploaded receipt images are stored in SeaweedFS under:

```
/receipts/{owner_user_id}/{uuid}.{ext}
```

The filer path (e.g. `/receipts/3/abc123.jpg`) is the value kept in the `image_path` column of the `receipts` table. The `GET /api/receipts/{id}/image` endpoint proxies the file back from the filer so the browser never connects to SeaweedFS directly.

SeaweedFS volume data is persisted in the `seaweedfs_volume` named Docker volume. The filer metadata index uses LevelDB (embedded — no extra database required).

## Local Development Setup

### Prerequisites

```bash
# macOS
brew install tesseract

# Python 3.12+, Node 18+
```

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in credentials
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

### Backend Tests

The backend tests run against a **real PostgreSQL** spun up on the fly with
[Testcontainers](https://testcontainers.com/) — the app's schema patches use
Postgres-only SQL, so SQLite isn't a substitute. A running **Docker daemon** is
the only prerequisite; the first run pulls the `postgres:16` image.

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Each test gets a clean database (every table is truncated between tests). Shared
fixtures — the container, a `TestClient`, and user/login helpers — live in
[`tests/conftest.py`](backend/tests/conftest.py).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173. The Vite dev server proxies `/api` to the backend.

### Running SeaweedFS locally (outside Docker)

If you run the backend outside Docker, point it at a local SeaweedFS filer:

```bash
# Download SeaweedFS binary from https://github.com/seaweedfs/seaweedfs/releases
weed master &
weed volume -mserver=localhost:9333 -dir=/tmp/seaweed-vol &
weed filer -master=localhost:9333 &
```

Then set in `backend/.env`:

```
SEAWEEDFS_FILER_URL=http://localhost:8888
```

## Configuration Reference

All backend settings are loaded from `backend/.env` (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string (required) |
| `SECRET_KEY` | — | JWT signing secret (required — generate a strong value) |
| `SEAWEEDFS_FILER_URL` | `http://localhost:8888` | SeaweedFS filer base URL |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allowed origin |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime (1 day) |
| `SUPERADMIN_EMAIL` | — | Seed super-admin email |
| `SUPERADMIN_PASSWORD` | — | Seed super-admin password |
| `TESSERACT_CMD` | (PATH) | Explicit path to tesseract binary |

## Migrating Existing Files to SeaweedFS

If you have receipts stored in the old local `backend/uploads/` folder (before SeaweedFS was introduced), run the one-time migration script after bringing up the full stack:

```bash
docker compose exec backend python migrate_to_seaweedfs.py
```

The script reads each receipt's `image_path` from the database, uploads the file to SeaweedFS, and updates the stored path. It is safe to run multiple times — already-migrated paths are skipped.

## Authentication & Roles

All `/api/receipts/*` endpoints require a JWT bearer token. Tokens are issued by `POST /api/auth/login`.

| Role | Capabilities |
|---|---|
| `superadmin` | Full access; manage all users and all receipts |
| `admin` | View and manage all receipts; cannot manage users |
| `user` | View and manage own receipts only |

**User management** — UI at `/users`, API under `/api/users`: create, change role, enable/disable, delete. A super-admin cannot demote or delete their own account.

**Change password** — any user, UI at `/account` or `POST /api/auth/change-password`.

## API Reference

Interactive docs with a try-it-out interface: http://localhost:8000/docs

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Issue JWT |
| `POST` | `/api/receipts/scan` | Upload image, run OCR, return parsed fields |
| `POST` | `/api/receipts` | Save a reviewed receipt |
| `GET` | `/api/receipts` | List receipts (scoped to role) |
| `GET` | `/api/receipts/{id}/image` | Serve receipt image |
| `PATCH` | `/api/receipts/{id}` | Update receipt fields |
| `DELETE` | `/api/receipts/{id}` | Delete receipt and image |
| `GET` | `/api/receipts/stats` | Spend aggregates for dashboard |
| `GET` | `/api/receipts/export.csv` | Export receipts as CSV |

## Project Structure

```
receipt-scanner/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, middleware, startup
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   ├── storage.py       # SeaweedFS filer client (upload/stream/delete)
│   │   ├── ocr.py           # Tesseract + OpenCV preprocessing
│   │   ├── parser.py        # Receipt field extraction
│   │   ├── security.py      # JWT auth
│   │   ├── database.py      # SQLAlchemy engine & session
│   │   └── routers/
│   │       ├── receipts.py  # Core receipt endpoints
│   │       ├── auth.py      # Login, password change
│   │       ├── users.py     # User management (admin)
│   │       └── categories.py
│   ├── migrate_to_seaweedfs.py  # One-time migration from local uploads/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── lib/
│       │   ├── api.js        # Fetch wrapper + all API calls
│       │   └── components/
│       └── routes/           # SvelteKit file-based routes
├── docker-compose.yml
└── README.md
```

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/your-feature`.
3. Commit your changes with clear messages.
4. Open a pull request against `main`.

## OCR Accuracy

Tesseract on thermal receipts is hit-or-miss. Results improve with good lighting and sharp focus. If accuracy is consistently poor on your receipts, consider:

- **PaddleOCR / EasyOCR** — still local, often more accurate on dense text.
- **Cloud vision fallback** — call a cloud API only when Tesseract confidence is below a threshold.

## License

MIT — see [LICENSE](LICENSE).
