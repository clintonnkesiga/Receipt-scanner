# Receipt Scanner

Scan supermarket & fuel-station receipts and store them in a digital, searchable format.

- **Frontend:** SvelteKit (Svelte 5) + Tailwind (upload, review/correct, browse, export CSV)
- **Backend:** Python + FastAPI
- **OCR:** Tesseract + OpenCV preprocessing (free, local)
- **Database:** PostgreSQL (via SQLAlchemy)
- **Image storage:** local `backend/uploads/` folder

## Prerequisites

```bash
# macOS
brew install tesseract        # the OCR engine itself (required)
# Python 3.10+ and Node 18+
```

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill in your Postgres credentials
uvicorn app.main:app --reload
```

API docs (Swagger UI) will be at http://localhost:8000/docs

### Database credentials

Set `DATABASE_URL` in `backend/.env`, e.g.:

```
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/receipts
```

Tables are created automatically on startup. (For schema migrations later,
add Alembic — see comment in `app/database.py`.)

### Authentication

The receipt API is protected with JWT bearer auth. Configure these in `backend/.env`:

```
SECRET_KEY=<long random string>          # python -c "import secrets; print(secrets.token_hex(32))"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
SUPERADMIN_EMAIL=you@example.com
SUPERADMIN_PASSWORD=<strong password>
SUPERADMIN_NAME=Super Admin
```

Create the super-admin (idempotent):

```bash
python -m app.seed
```

Then sign in at the web UI's `/login` page. All `/api/receipts/*` endpoints
require a valid token; `/api/auth/login` issues one. Swagger's **Authorize**
button works too (uses the same OAuth2 password flow).

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173 and proxies `/api` to the backend.

## How it works

1. Upload a receipt photo in the web UI.
2. Backend preprocesses the image (OpenCV: grayscale, deskew, threshold) and runs Tesseract.
3. A rules-based parser extracts merchant, date, total, and line items.
4. You review/correct the parsed fields and save — original image + data go to Postgres.
5. Browse history and export to CSV.

> **Accuracy note:** Tesseract on thermal receipts is hit-or-miss; image
> preprocessing and per-merchant parsing rules matter most. If accuracy is poor,
> consider swapping in PaddleOCR/EasyOCR (still local) or adding an optional
> cloud-vision fallback for failed parses.
