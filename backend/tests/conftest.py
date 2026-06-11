"""Shared test fixtures.

The app talks to PostgreSQL and its schema patches use Postgres-only SQL
(``DROP CONSTRAINT IF EXISTS``, partial unique indexes — see
``app/database.py``), so the tests run against a *real* Postgres spun up by
Testcontainers rather than SQLite. A Docker daemon must be running.

Layout:
  * ``postgres_container`` (session) — one Postgres 16 container for the run.
  * ``_bound_engine``      (session) — rebinds the app's engine/session to it
                                       and creates the schema once.
  * ``reset_db``           (autouse) — truncates every table before each test.
  * ``client`` / ``db`` / ``make_user`` / ``login`` — per-test helpers.
"""
import pytest


@pytest.fixture(scope="session")
def postgres_container():
    """Start one PostgreSQL 16 container for the whole test session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def _bound_engine(postgres_container):
    """Point the app's engine/SessionLocal at the container and build the schema.

    ``app.database`` creates its engine at import time from settings, so we
    rebind the module-level ``engine`` and reconfigure ``SessionLocal`` in place
    (the same sessionmaker object the app and seed code already imported), then
    run ``init_db()`` to create tables + apply the migrations once.
    """
    from sqlalchemy import create_engine

    from app import database

    engine = create_engine(postgres_container.get_connection_url(), pool_pre_ping=True)
    database.engine = engine
    database.SessionLocal.configure(bind=engine)
    database.init_db()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def reset_db(_bound_engine):
    """Truncate every table before each test so tests start from a clean slate.

    Runs before the ``client`` fixture (autouse fixtures are set up first), so a
    test that uses ``client`` still gets the default categories re-seeded by the
    app's startup lifespan.
    """
    from sqlalchemy import text

    from app.database import Base

    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with _bound_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db(_bound_engine):
    """A SQLAlchemy session bound to the test database, for direct setup/asserts."""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_bound_engine):
    """A FastAPI TestClient.

    Used as a context manager so the app's lifespan runs (creating tables and
    seeding the default categories). ``get_db`` is overridden explicitly to make
    the test seam obvious, though ``SessionLocal`` already points at the
    container.
    """
    from fastapi.testclient import TestClient

    from app.database import SessionLocal, get_db
    from app.main import app

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    """Factory that inserts a user and returns it. Override any field via kwargs."""
    from app import models
    from app.security import hash_password

    def _make(
        *,
        email="user@example.com",
        password="secret123",
        role="user",
        full_name="Test User",
        is_active=True,
    ):
        user = models.User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def login(client):
    """Log a user in and return an Authorization header dict for them."""

    def _login(email, password):
        resp = client.post(
            "/api/auth/login",
            data={"username": email, "password": password},
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _login
