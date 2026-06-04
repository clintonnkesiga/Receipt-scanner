from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import receipts, auth, users, categories
from .seed import seed_default_categories


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup. Requires DATABASE_URL to be reachable.
    init_db()
    seed_default_categories()  # ensure the starter category list exists
    yield


app = FastAPI(title="Receipt Scanner API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(receipts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
