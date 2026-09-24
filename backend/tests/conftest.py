"""Pytest configuration and fixtures."""

import asyncio
import os
import threading
from collections.abc import AsyncGenerator

# Set TESTING before importing settings
os.environ["TESTING"] = "true"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import database as app_database
from app.config import settings

# Import all models so SQLAlchemy can configure relationships
from app.core.auth.models import Clinic, ClinicMembership, User  # noqa: F401
from app.core.events.models import EventHandlerFailure  # noqa: F401
from app.core.plugins.loader import load_modules
from app.core.privacy.models import SubjectRequest  # noqa: F401
from app.database import Base, UnitOfWorkSession, get_db
from app.main import app
from app.modules.agenda.models import (  # noqa: F401
    Appointment,
    AppointmentCabinetEvent,
    AppointmentStatusEvent,
    AppointmentTreatment,
    Cabinet,
)
from app.modules.billing.models import (  # noqa: F401
    Invoice,
    InvoiceHistory,
    InvoiceItem,
    InvoicePayment,
    InvoiceSeries,
    InvoiceSeriesHistory,
)
from app.modules.budget.models import (  # noqa: F401
    Budget,
    BudgetHistory,
    BudgetItem,
    BudgetSignature,
)
from app.modules.catalog.models import (  # noqa: F401
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
)
from app.modules.clinical_notes.models import ClinicalNote  # noqa: F401
from app.modules.media.models import Document, MediaAttachment  # noqa: F401
from app.modules.odontogram.models import (  # noqa: F401
    OdontogramHistory,
    ToothRecord,
    Treatment,
    TreatmentTooth,
)
from app.modules.patients.models import Patient  # noqa: F401
from app.modules.payments.models import (  # noqa: F401
    PatientEarnedEntry,
    Payment,
    PaymentAllocation,
    PaymentHistory,
    Refund,
)
from app.modules.periodontogram.models import (  # noqa: F401
    PeriodontogramSite,
    PeriodontogramSnapshot,
    PeriodontogramTooth,
)
from app.modules.recalls.models import (  # noqa: F401
    Recall,
    RecallContactAttempt,
    RecallSettings,
)
from app.modules.schedules.models import (  # noqa: F401
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.treatment_plan.models import (  # noqa: F401
    PlannedTreatmentItem,
    TreatmentPlan,
)
from app.modules.verifactu.models import (  # noqa: F401
    VerifactuCertificate,
    VerifactuRecord,
    VerifactuRecordAttempt,
    VerifactuSettings,
    VerifactuVatClassification,
)

# Load modules manually for tests (normally done in lifespan)
load_modules(app)


@pytest.fixture(autouse=True)
def _restore_event_subscriptions():
    """Put the bus back as ``load_modules`` left it, after every test.

    Tests subscribe spies to real events. One that cleaned up with
    ``_handlers.pop(event)`` dropped ``payments``' subscribers along with
    its spy, and the reopen tests that ran next booked no per-session
    charges — failing only in the full suite, never on their own. The
    subscriptions are session-wide, so no test may leave them changed.
    """
    from app.core.events import event_bus

    saved = {k: list(v) for k, v in event_bus._handlers.items()}
    yield
    event_bus._handlers = saved


@pytest.fixture
def isolated_runtime(tmp_path):
    """Hand a test an empty runtime to mount into, then restore.

    Module mounting writes into three process-wide singletons that
    ``load_modules(app)`` above already filled for the whole session.
    Tests that mount a different subset — or unmount something — must
    put them back, or every later test sees a half-dismantled app.

    The module-layer sync is redirected at ``tmp_path`` for the same
    reason: ``DENTALPIN_FRONTEND_ROOT`` points at the developer's own
    checkout, so a test that drives the lifespan would rewrite the
    repository's ``frontend/modules.json`` from the *test* database's
    install state — dropping layers the dev app is actually serving.
    """
    from app.core.agents.tools.registry import tool_registry
    from app.core.auth.permissions import invalidate_role_permissions_cache
    from app.core.events import event_bus
    from app.core.plugins import frontend_layers
    from app.core.plugins.gate import module_gate
    from app.core.plugins.registry import module_registry

    saved_frontend_root = frontend_layers.DEFAULT_FRONTEND_ROOT
    frontend_layers.DEFAULT_FRONTEND_ROOT = tmp_path

    saved_active = set(module_registry._active)
    saved_handlers = {k: list(v) for k, v in event_bus._handlers.items()}
    saved_tools = dict(tool_registry._tools)
    saved_owners = dict(tool_registry._owners)

    module_registry._active = set()
    event_bus._handlers = {}
    tool_registry.clear()
    module_gate.clear()
    invalidate_role_permissions_cache()

    yield

    frontend_layers.DEFAULT_FRONTEND_ROOT = saved_frontend_root
    module_registry._active = saved_active
    event_bus._handlers = saved_handlers
    tool_registry._tools = saved_tools
    tool_registry._owners = saved_owners
    module_gate.clear()
    invalidate_role_permissions_cache()


def _resolve_test_database_url() -> str:
    """Pick the database the suite is allowed to destroy.

    Every test recreates and drops the whole schema, so this must never be
    the database a running app is using. Resolution order:

    1. An explicit ``TEST_DATABASE_URL`` environment variable.
    2. ``DATABASE_URL`` as-is when it already names a ``*_test`` database
       (this is what CI provides).
    3. Otherwise ``DATABASE_URL`` with ``_test`` appended to the database
       name — so a local ``docker-compose exec backend pytest`` lands on
       ``dental_clinic_test`` instead of the dev database.

    The name must end in ``_test``; anything else aborts the run rather
    than risk wiping real data.
    """
    raw = os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL
    url = make_url(raw)

    if url.database and not url.database.endswith("_test"):
        url = url.set(database=f"{url.database}_test")

    if not url.database or not url.database.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run the suite against database {url.database!r}: the "
            "test database name must end in '_test'. Every test drops all "
            "tables, so pointing this at a live database destroys its data. "
            "Set TEST_DATABASE_URL to a dedicated '*_test' database."
        )

    return url.render_as_string(hide_password=False)


TEST_DATABASE_URL = _resolve_test_database_url()

# Guard against the historical footgun: the suite used to inherit
# DATABASE_URL verbatim, so a local run wiped the dev database (and with it
# the demo login). Keep this assertion even though _resolve_test_database_url
# already enforces the suffix — it is the last line of defence.
if TEST_DATABASE_URL == settings.DATABASE_URL and not settings.DATABASE_URL.endswith("_test"):
    raise RuntimeError("Test database must not be the application database.")

# Redirect *every* reader of DATABASE_URL at the test database.
#
# Overriding `get_db` and the global engine covers code that goes through
# SQLAlchemy. It does not cover the two other ways a test reaches a
# database: `settings.DATABASE_URL` read directly (the roundtrip suites
# build an asyncpg DSN from it), and subprocesses — `alembic upgrade` /
# `downgrade` / `stamp` spawned by `tests/test_alembic_roundtrip.py`,
# `tests/**/test_uninstall_roundtrip.py` and `PendingProcessor`, which
# re-import settings from the environment.
#
# Both used to resolve to the *development* database, so
# `pytest -m alembic_roundtrip` — whose whole job is `downgrade base` —
# dropped every table in `dental_clinic` and took the demo login with
# it. The `*_test` suffix check above is what makes this assignment
# safe.
APP_DATABASE_URL = settings.DATABASE_URL
"""What ``DATABASE_URL`` said before the redirect — the database a running
app uses. Kept so ``test_db_isolation`` can assert we moved off it."""

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
settings.DATABASE_URL = TEST_DATABASE_URL

# Redirect the application's global engine at the test database.
#
# The `client` fixture only overrides `get_db`, which covers request-scoped
# sessions. Nine modules (patient_timeline, payments, recalls, copilot,
# treatment_plan, migration_import, ...) open their own session with
# `async_session_maker` from event handlers and background tasks — those
# bypass the override entirely and follow whatever the module-level import
# is bound to. While the suite shared the app's database that was invisible;
# once it does not, those writes land in the wrong database.
#
# `configure()` mutates the existing sessionmaker in place, so modules that
# already did `from app.database import async_session_maker` pick it up.
# NullPool keeps no idle connections around to block the per-test drop_all.
_global_test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
app_database.engine = _global_test_engine
app_database.async_session_maker.configure(bind=_global_test_engine)


async def _ensure_test_database() -> None:
    """Create the test database if it does not exist yet.

    Keeps ``docker-compose exec backend pytest`` a one-liner: no manual
    ``createdb`` step, and no reason for anyone to point the suite back at
    the dev database to make it run.
    """
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(database="postgres")

    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                # Identifiers cannot be bound as parameters; the name comes
                # from our own URL and is suffix-checked above.
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await engine.dispose()


async def _reset_test_schema() -> None:
    """Start every session from an empty schema.

    ``create_all`` skips tables that already exist, so a run killed before
    its teardown leaves last session's tables in place — and the next run
    fails with "column X does not exist" against a model that clearly has
    it. Dropping the schema once per session costs one statement and makes
    an interrupted run stop being contagious.
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


# --- one session at a time --------------------------------------------
#
# Every test drops and recreates the whole schema, so two pytest sessions
# pointed at the same test database destroy each other's tables mid-run.
# What that looks like is not "two runs collided": it is a duplicate
# ``test@example.com`` in a fixture, or ``table "x" does not exist`` in a
# teardown, landing on whichever test happened to be running. It reads as
# flakiness, and it sent this investigation after an ordering bug that was
# never there.
#
# A Postgres advisory lock is the right shape for the guard: it lives on
# the connection, so it is released the moment the process ends — a killed
# run leaves nothing to clean up, unlike a lock row. It is held on a thread
# of its own because the suite has no synchronous driver, and a connection
# cannot outlive the ``asyncio.run`` that opened it.

_SESSION_LOCK_KEY = 0x44454E54  # "DENT"
_lock_release = threading.Event()
_lock_settled = threading.Event()
_lock_error: list[str] = []


def _asyncpg_dsn() -> str:
    """``postgresql+asyncpg://…`` is SQLAlchemy's spelling; asyncpg wants its own."""
    return (
        make_url(TEST_DATABASE_URL)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )


def _hold_session_lock() -> None:
    import asyncpg

    async def run() -> None:
        try:
            conn = await asyncpg.connect(_asyncpg_dsn())
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            _lock_error.append(f"could not reach the test database to lock it: {exc}")
            _lock_settled.set()
            return
        try:
            if not await conn.fetchval("SELECT pg_try_advisory_lock($1)", _SESSION_LOCK_KEY):
                _lock_error.append(
                    "another pytest session is already using "
                    f"{make_url(TEST_DATABASE_URL).database}. Running two at once "
                    "corrupts both: every test drops and recreates the schema. "
                    "Wait for it to finish, or point this run at another database "
                    "with TEST_DATABASE_URL (the name must end in '_test')."
                )
                _lock_settled.set()
                return
            _lock_settled.set()
            # Hold it until the session ends. The lock goes with the
            # connection, so a killed run releases it on its own.
            await asyncio.get_running_loop().run_in_executor(None, _lock_release.wait)
        finally:
            await conn.close()

    asyncio.run(run())


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    """Provision the dedicated test database before any fixture runs."""
    asyncio.run(_ensure_test_database())

    # Claim the database before touching its schema, so a second session
    # stops here instead of halfway through someone else's run.
    threading.Thread(target=_hold_session_lock, daemon=True).start()
    _lock_settled.wait(timeout=30)
    if _lock_error:
        # `pytest.exit`, not `raise`: this is a usage problem with a clear
        # remedy, and it should read as one rather than as a crash in the
        # test harness.
        pytest.exit(_lock_error[0], returncode=pytest.ExitCode.USAGE_ERROR)

    asyncio.run(_reset_test_schema())
    # Announce the target: the suite drops every table it touches, so which
    # database that is should never be something you have to go and check.
    print(f"\ntest database: {make_url(TEST_DATABASE_URL).render_as_string()}")


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """Release the redirected global engine's connections, and the lock."""
    _lock_release.set()
    asyncio.run(_global_test_engine.dispose())


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create a new engine for each test to avoid connection conflicts
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_maker = async_sessionmaker(
        test_engine, class_=UnitOfWorkSession, expire_on_commit=False
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP client for testing."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        # Commit on the way out, like the real ``get_db`` does. Without
        # it a request's writes stay invisible to the event handlers,
        # which read through their own sessions — the very thing S2 is
        # about. Failures propagate untouched (the session is dropped
        # with the test).
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(db_session: AsyncSession) -> dict[str, str]:
    """Create a test user directly in the DB and return auth headers."""
    from app.core.auth.service import create_access_token, hash_password

    user = User(
        email="test@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, token_version=user.token_version)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_clinic(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> Clinic:
    """Create a test clinic and assign the test user as admin."""
    from uuid import uuid4

    # Get user from /me endpoint
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B12345678",
        address={"street": "Test St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
        account_tier="clinic",
    )
    db_session.add(clinic)
    await db_session.flush()

    # Create admin membership
    membership = ClinicMembership(
        id=uuid4(),
        user_id=user_id,
        clinic_id=clinic.id,
        role="admin",
    )
    db_session.add(membership)

    # Default cabinet so appointment-oriented tests resolve cabinet FK
    # without extra setup.

    db_session.add(
        Cabinet(
            id=uuid4(),
            clinic_id=clinic.id,
            name="Gabinete 1",
            color="#3B82F6",
            display_order=0,
            is_active=True,
        )
    )

    await db_session.commit()

    return clinic


@pytest_asyncio.fixture
async def test_patient(db_session: AsyncSession, test_clinic: Clinic) -> Patient:
    """Create a test patient in the test clinic."""
    from uuid import uuid4

    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Test",
        last_name="Patient",
        email="patient@test.com",
        phone="+34666123456",
    )
    db_session.add(patient)
    await db_session.commit()

    return patient
